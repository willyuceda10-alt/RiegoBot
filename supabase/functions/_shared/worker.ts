import { db, must, queue } from "./common.ts";
import { parseMessage, help, nextRetry } from "../../../core/domain.ts";

async function allowedCase(id: number, contact: any) {
  const i = must(
    await db()
      .from("incidents")
      .select("*")
      .eq("id", id)
      .eq("site_id", contact.site_id)
      .single(),
  );
  const recipients = (i.policy.levels ?? []).flatMap((l: any) => l.contacts);
  if (
    !["supervisor", "jefe", "mantenimiento", "admin"].includes(contact.role) &&
    !recipients.includes(contact.id) &&
    i.assignee_id !== contact.id &&
    i.source_data.requester_phone !== contact.phone
  )
    throw Error("No estás asignado a esta incidencia");
  return i;
}
export async function inbound(message: any) {
  const phone = String(message.from);
  const contacts = must(
    await db()
      .from("contacts")
      .select("*")
      .eq("phone", phone)
      .eq("active", true),
  );
  if (contacts.length !== 1)
    throw Error("El teléfono debe estar activo en un único sitio");
  const contact = contacts[0],
    site = contact.site_id,
    key = "reply:" + message.id;
  must(
    await db()
      .from("conversations")
      .upsert(
        { phone, site_id: site, last_inbound_at: new Date().toISOString() },
        { onConflict: "phone" },
      ),
  );
  const text = message.text?.body ?? message.image?.caption ?? "";
  must(
    await db()
      .from("messages")
      .upsert(
        {
          external_id: message.id,
          site_id: site,
          phone,
          direction: "in",
          body: text || "[foto]",
        },
        { onConflict: "external_id" },
      ),
  );
  const conv = must(
    await db().from("conversations").select("*").eq("phone", phone).single(),
  );
  try {
    if (message.type === "image") {
      const captionCase = text.match(/(?:caso\s*)?#(\d+)/i)?.[1];
      const id = captionCase ? Number(captionCase) : conv.incident_id;
      if (!id) {
        await queue(
          phone,
          site,
          "Primero selecciona CASO número y vuelve a enviar la foto.",
          key,
        );
        return;
      }
      const i = await allowedCase(id, contact);
      if (i.status === "resolved") throw Error("El caso está cerrado");
      const token = Deno.env.get("WHATSAPP_TOKEN")!;
      const version = Deno.env.get("WHATSAPP_API_VERSION") ?? "v23.0";
      const metadata = await fetch(
        "https://graph.facebook.com/" +
          version +
          "/" +
          encodeURIComponent(message.image.id),
        { headers: { Authorization: "Bearer " + token } },
      );
      if (!metadata.ok) throw Error("No se pudo obtener la foto");
      const meta = await metadata.json();
      const url = new URL(meta.url);
      if (
        url.protocol !== "https:" ||
        !/(^|\.)(facebook\.com|fbcdn\.net|fbsbx\.com)$/.test(url.hostname)
      )
        throw Error("Origen de foto inválido");
      if (meta.file_size > 10 * 1024 * 1024)
        throw Error("Foto demasiado grande");
      const media = await fetch(url, {
        headers: { Authorization: "Bearer " + token },
        redirect: "error",
      });
      if (!media.ok) throw Error("Descarga de foto fallida");
      const bytes = new Uint8Array(await media.arrayBuffer());
      await saveEvidence(
        id,
        site,
        bytes,
        meta.mime_type,
        text,
        phone,
        message.id,
      );
      await queue(
        phone,
        site,
        "Foto registrada en #" +
          id +
          ". Para finalizar: SUBSANAR " +
          id +
          " descripción.",
        key,
        id,
      );
      return;
    }
    const intent = parseMessage(text);
    if (intent.id) {
      const i = await allowedCase(intent.id, contact);
      if (intent.kind === "select") {
        must(
          await db()
            .from("conversations")
            .update({ incident_id: i.id })
            .eq("phone", phone),
        );
        await queue(
          phone,
          site,
          "Seleccionada incidencia #" +
            i.id +
            ". Envía las fotos o indica la acción.",
          key,
          i.id,
        );
        return;
      }
      const approve = ["supervisor", "jefe", "admin"].includes(contact.role);
      const result = must(
        await db().rpc("act_incident", {
          case_id: i.id,
          actor_text: phone,
          act: intent.kind,
          note: intent.note ?? "",
          can_approve: approve,
          command_key: message.id,
        }),
      );
      await queue(
        phone,
        site,
        "Incidencia #" +
          i.id +
          ": " +
          result.status +
          (result.source_active
            ? " · La señal de origen requiere comprobación."
            : ""),
        key,
        i.id,
      );
      return;
    }
    if (intent.kind === "support") {
      const rules = must(
        await db()
          .from("rules")
          .select("*")
          .eq("site_id", site)
          .eq("enabled", true)
          .eq("kind", "support")
          .limit(1),
      );
      if (!rules.length)
        throw Error("No hay responsables de soporte configurados");
      const id = must(
        await db().rpc("open_incident", {
          s: site,
          r: rules[0].id,
          d: intent.dream ?? null,
          title_text: intent.note ?? "Soporte solicitado",
          asset: "manual:" + message.id,
          policy_data: rules[0],
          raw: { message_id: message.id, requester_phone: phone },
        }),
      );
      must(
        await db()
          .from("conversations")
          .update({ incident_id: id, mode: "human" })
          .eq("phone", phone),
      );
      await queue(
        phone,
        site,
        "Caso #" +
          id +
          " derivado a soporte. Tus mensajes quedan registrados para el equipo.",
        key,
        id,
      );
      return;
    }
    if (conv.mode === "human" && conv.incident_id) {
      await allowedCase(conv.incident_id, contact);
      must(
        await db()
          .from("messages")
          .update({ incident_id: conv.incident_id })
          .eq("external_id", message.id),
      );
      await queue(
        phone,
        site,
        "Mensaje incorporado al caso #" + conv.incident_id + ".",
        key,
        conv.incident_id,
      );
      return;
    }
    if (intent.kind === "incidents") {
      const cases = must(
        await db()
          .from("incidents")
          .select("*")
          .eq("site_id", site)
          .neq("status", "resolved")
          .order("created_at", { ascending: false })
          .limit(50),
      );
      const visible = cases.filter(
        (i: any) =>
          ["supervisor", "jefe", "admin", "mantenimiento"].includes(
            contact.role,
          ) ||
          (i.policy.levels ?? []).some((l: any) =>
            l.contacts.includes(contact.id),
          ),
      );
      await queue(
        phone,
        site,
        visible.length
          ? visible
              .slice(0, 15)
              .map((i: any) => "#" + i.id + " · " + i.title + " · " + i.status)
              .join("\n")
          : "No tienes incidencias pendientes asignadas.",
        key,
      );
      return;
    }
    if (intent.kind === "live_state") {
      await queue(
        phone,
        site,
        "No hay una fuente validada de válvulas o riegos activos. Puedo mostrar eventos y últimas lecturas con su fecha; no confirmar el estado actual.",
        key,
      );
      return;
    }
    if (intent.kind === "status") {
      const collectors = must(
        await db()
          .from("collectors")
          .select("name,last_seen")
          .eq("site_id", site),
      );
      await queue(
        phone,
        site,
        "Sincronización:\n" +
          collectors
            .map((c: any) => c.name + ": " + (c.last_seen ?? "sin datos"))
            .join("\n") +
          "\nLa conexión del lector no confirma la salud del controlador.",
        key,
      );
      return;
    }
    if (intent.kind === "query") {
      const rows = must(
        await db().rpc("query_readings", {
          s: site,
          e: intent.entity!,
          d: intent.dream ?? null,
          today_only: intent.today ?? false,
        }),
      );
      const timezone = must(
        await db().from("sites").select("timezone").eq("id", site).single(),
      ).timezone;
      const mapping = must(
        await db()
          .from("metric_mappings")
          .select("*")
          .eq("site_id", site)
          .eq("entity", intent.entity!)
          .maybeSingle(),
      );
      const rendered = rows.slice(0, 10).map((r: any) => {
        const raw = mapping?.verified
          ? r.data[mapping.field]
          : (r.data.ValueA ?? r.data.ValueF);
        const value =
          mapping?.verified && raw !== null && raw !== undefined
            ? Number(raw) * Number(mapping.scale) + " " + mapping.unit
            : raw;
        return (
          "Dream " +
          r.dream_id +
          " · " +
          new Date(r.source_at).toLocaleString("es", { timeZone: timezone }) +
          " · " +
          (r.data.RepCodeStr ??
            value ??
            r.data.ProgNameStr ??
            JSON.stringify(r.data).slice(0, 200))
        );
      });
      await queue(
        phone,
        site,
        rows.length
          ? rendered.join("\n") +
              "\nMostrando " +
              Math.min(10, rows.length) +
              " de " +
              rows.length +
              " observaciones" +
              (rows.length === 1000 ? " (consulta limitada)" : "") +
              ". " +
              (mapping?.verified
                ? "Unidad validada; consulta la fecha del dato."
                : "Valores crudos; unidades y estado actual sin validar.")
          : "No hay datos para esa consulta. No equivale a cero consumo ni ausencia de alarmas.",
        key,
      );
      return;
    }
    await queue(phone, site, help, key);
  } catch (e) {
    await queue(
      phone,
      site,
      e instanceof Error ? e.message : "No se pudo procesar. Intenta de nuevo.",
      key,
    );
  }
}
export async function saveEvidence(
  id: number,
  site: string,
  bytes: Uint8Array,
  mime: string,
  caption: string,
  actor: string,
  externalId = crypto.randomUUID(),
) {
  if (bytes.length > 10 * 1024 * 1024) throw Error("Foto supera 10 MB");
  const magic =
    mime === "image/jpeg"
      ? bytes[0] === 255 && bytes[1] === 216
      : mime === "image/png"
        ? bytes[0] === 137 && bytes[1] === 80
        : mime === "image/webp"
          ? new TextDecoder().decode(bytes.slice(0, 4)) === "RIFF" &&
            new TextDecoder().decode(bytes.slice(8, 12)) === "WEBP"
          : false;
  if (!magic) throw Error("Formato de imagen inválido");
  const path =
    site + "/" + id + "/" + externalId.replace(/[^a-zA-Z0-9_-]/g, "_");
  must(
    await db()
      .storage.from("evidence")
      .upload(path, bytes, { contentType: mime, upsert: true }),
  );
  must(
    await db()
      .from("evidence")
      .upsert(
        { incident_id: id, path, mime, caption, actor },
        { onConflict: "path" },
      ),
  );
}
async function outbound(p: any) {
  if (p.notification_kind === "incident") {
    const current = must(
      await db()
        .from("incidents")
        .select("status")
        .eq("id", p.incident_id)
        .single(),
    );
    if (current.status === "resolved" && p.case_status !== "resolved") return;
  }

  const active = must(
    await db()
      .from("contacts")
      .select("id")
      .eq("site_id", p.site_id)
      .eq("phone", p.phone)
      .eq("active", true)
      .maybeSingle(),
  );
  if (!active) return;

  if (Deno.env.get("DRY_RUN") === "true") {
    must(
      await db().from("messages").insert({
        site_id: p.site_id,
        phone: p.phone,
        direction: "out",
        body: p.text,
        incident_id: p.incident_id,
        delivery_status: "simulated",
      }),
    );
    return;
  }
  const phoneId = Deno.env.get("WHATSAPP_PHONE_NUMBER_ID"),
    token = Deno.env.get("WHATSAPP_TOKEN");
  if (!phoneId || !token) throw Error("WhatsApp no configurado");
  const conv = must(
    await db()
      .from("conversations")
      .select("last_inbound_at")
      .eq("phone", p.phone)
      .maybeSingle(),
  );
  const inWindow =
    conv?.last_inbound_at &&
    Date.now() - Date.parse(conv.last_inbound_at) < 24 * 3600000;
  const template = Deno.env.get("WHATSAPP_ALERT_TEMPLATE");
  if (!inWindow && !template)
    throw Error("Falta plantilla aprobada para avisos fuera de ventana");
  const body = inWindow
    ? { type: "text", text: { body: p.text } }
    : {
        type: "template",
        template: {
          name: template,
          language: {
            code: Deno.env.get("WHATSAPP_TEMPLATE_LANGUAGE") ?? "es",
          },
          components: [
            { type: "body", parameters: [{ type: "text", text: p.text }] },
          ],
        },
      };
  let response: Response;
  try {
    response = await fetch(
      "https://graph.facebook.com/" +
        (Deno.env.get("WHATSAPP_API_VERSION") ?? "v23.0") +
        "/" +
        phoneId +
        "/messages",
      {
        method: "POST",
        headers: {
          Authorization: "Bearer " + token,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          messaging_product: "whatsapp",
          to: p.phone,
          ...body,
        }),
        signal: AbortSignal.timeout(20000),
      },
    );
  } catch {
    throw Error(
      "UNCERTAIN: Resultado de envío desconocido; reconciliar antes de reenviar",
    );
  }
  const result = await response.json();
  if (!response.ok)
    throw Error(
      "Meta rechazó envío: " +
        response.status +
        " " +
        (result.error?.code ?? ""),
    );
  const id = result.messages?.[0]?.id;
  if (!id) throw Error("UNCERTAIN: Meta no devolvió identificador");
  const saved = await db().from("messages").insert({
    external_id: id,
    site_id: p.site_id,
    phone: p.phone,
    direction: "out",
    body: p.text,
    incident_id: p.incident_id,
    delivery_status: "sent",
  });
  if (saved.error)
    throw Error("UNCERTAIN: Enviado a Meta pero persistencia falló");
}
export async function work() {
  must(await db().rpc("tick_incidents"));
  const jobs = must(await db().rpc("claim_jobs", { n: 10 }));
  for (const j of jobs) {
    try {
      if (j.kind === "inbound") await inbound(j.payload);
      else await outbound(j.payload);
      must(
        await db()
          .from("jobs")
          .update({ status: "done" })
          .eq("id", j.id)
          .eq("lease_id", j.lease_id),
      );
    } catch (e) {
      const message = e instanceof Error ? e.message : String(e);
      const status = message.startsWith("UNCERTAIN")
        ? "uncertain"
        : j.attempts >= 5
          ? "failed"
          : "pending";
      must(
        await db()
          .from("jobs")
          .update({
            status,
            last_error: message,
            available_at: new Date(
              Date.now() + nextRetry(j.attempts) * 1000,
            ).toISOString(),
          })
          .eq("id", j.id)
          .eq("lease_id", j.lease_id),
      );
    }
  }
  return { processed: jobs.length };
}
