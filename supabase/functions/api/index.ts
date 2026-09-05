import { db, json, error, must, staff, sha, queue } from "../_shared/common.ts";
import { validateRule } from "../../../core/domain.ts";
import { inbound, work, saveEvidence } from "../_shared/worker.ts";
Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return json({});
  if (req.method !== "POST") return json({ error: "POST requerido" }, 405);
  try {
    const b = await req.json();
    const actor = await staff(req, b.site_id);
    const admin = () => {
      if (actor.role !== "admin") throw Error("Solo administradores");
    };
    if (b.action === "deliveries") {
      admin();
      return json(
        must(
          await db()
            .from("jobs")
            .select("id,status,attempts,last_error,payload,created_at")
            .eq("kind", "outbound")
            .eq("payload->>site_id", b.site_id)
            .order("id", { ascending: false })
            .limit(100),
        ),
      );
    }
    if (b.action === "retry_delivery") {
      admin();
      const j = must(
        await db()
          .from("jobs")
          .select("*")
          .eq("id", b.job_id)
          .eq("payload->>site_id", b.site_id)
          .single(),
      );
      if (!["failed", "uncertain"].includes(j.status))
        throw Error("Entrega no requiere intervención");
      if (j.status === "uncertain" && !b.confirmed_not_sent)
        throw Error("Confirma que no se entregó en Meta antes de reintentar");
      must(
        await db()
          .from("jobs")
          .update({
            status: "pending",
            attempts: 0,
            available_at: new Date().toISOString(),
          })
          .eq("id", j.id),
      );
      must(
        await db()
          .from("audit_log")
          .insert({
            site_id: b.site_id,
            actor: actor.id,
            action: "retry_delivery",
            details: { job_id: j.id, previous_status: j.status },
          }),
      );
      return json({ ok: true });
    }
    if (b.action === "dashboard") {
      const client = db();
      const [incidents, rules, contacts, dreams, collectors, logs] =
        await Promise.all([
          client
            .from("incidents")
            .select("*")
            .eq("site_id", b.site_id)
            .order("id", { ascending: false })
            .limit(200),
          client.from("rules").select("*").eq("site_id", b.site_id),
          client.from("contacts").select("*").eq("site_id", b.site_id),
          client.from("dreams").select("*").eq("site_id", b.site_id),
          client
            .from("collectors")
            .select("id,name,last_seen,enabled")
            .eq("site_id", b.site_id),
          client
            .from("messages")
            .select("*")
            .eq("site_id", b.site_id)
            .order("id", { ascending: false })
            .limit(80),
        ]);
      return json({
        incidents: must(incidents),
        rules: must(rules),
        contacts: must(contacts),
        dreams: must(dreams),
        collectors: must(collectors),
        messages: must(logs),
      });
    }
    if (b.action === "rule") {
      admin();
      const rule = validateRule({ ...b.rule, site_id: b.site_id });
      const ids = [...new Set(rule.levels.flatMap((l) => l.contacts))];
      const contacts = must(
        await db()
          .from("contacts")
          .select("id")
          .eq("site_id", b.site_id)
          .eq("active", true)
          .in("id", ids),
      );
      if (contacts.length !== ids.length)
        throw Error("Destinatarios no válidos");
      if (rule.id) {
        must(
          await db()
            .from("rules")
            .select("id")
            .eq("id", rule.id)
            .eq("site_id", b.site_id)
            .single(),
        );
      }
      must(await db().from("rules").upsert(rule));
      return json({ ok: true });
    }
    if (b.action === "contact") {
      admin();
      const c = b.contact;
      if (!c.name?.trim() || !/^\d{8,15}$/.test(c.phone))
        throw Error("Nombre y teléfono internacional sin + requeridos");
      if (c.id)
        must(
          await db()
            .from("contacts")
            .select("id")
            .eq("id", c.id)
            .eq("site_id", b.site_id)
            .single(),
        );
      must(
        await db()
          .from("contacts")
          .upsert({
            id: c.id,
            site_id: b.site_id,
            name: c.name,
            phone: c.phone,
            role: c.role,
            active: c.active ?? true,
          }),
      );
      return json({ ok: true });
    }
    if (b.action === "dream") {
      admin();
      must(
        await db()
          .from("dreams")
          .upsert({
            site_id: b.site_id,
            dream_id: String(b.dream.dream_id),
            name: b.dream.name,
            enabled: b.dream.enabled ?? true,
          }),
      );
      return json({ ok: true });
    }
    if (b.action === "mapping") {
      admin();
      const m = b.mapping;
      if (!m.entity || !m.field || !m.unit || !Number.isFinite(Number(m.scale)))
        throw Error("Mapping inválido");
      must(
        await db()
          .from("metric_mappings")
          .upsert({
            site_id: b.site_id,
            entity: m.entity,
            field: m.field,
            unit: m.unit,
            scale: Number(m.scale),
            verified: m.verified === true,
          }),
      );
      return json({ ok: true });
    }
    if (b.action === "collector") {
      admin();
      const token = crypto.randomUUID() + crypto.randomUUID();
      const collector = must(
        await db()
          .from("collectors")
          .insert({
            site_id: b.site_id,
            name: b.name,
            token_hash: await sha(token),
          })
          .select("id,name")
          .single(),
      );
      return json({ collector, token });
    }
    if (b.action === "simulate") {
      if (Deno.env.get("DRY_RUN") !== "true")
        throw Error("Simulación deshabilitada");
      must(
        await db()
          .from("contacts")
          .select("id")
          .eq("site_id", b.site_id)
          .eq("phone", b.phone)
          .single(),
      );
      await inbound({
        id: "sim-" + crypto.randomUUID(),
        from: b.phone,
        type: "text",
        text: { body: b.text },
      });
      await work();
      return json({ ok: true });
    }
    if (b.action === "tick") {
      admin();
      return json(await work());
    }
    const i = must(
      await db()
        .from("incidents")
        .select("*")
        .eq("id", b.incident_id)
        .eq("site_id", b.site_id)
        .single(),
    );
    if (b.action === "detail") {
      const events = must(
        await db()
          .from("incident_events")
          .select("*")
          .eq("incident_id", i.id)
          .order("id"),
      );
      const evidence = must(
        await db().from("evidence").select("*").eq("incident_id", i.id),
      );
      for (const e of evidence)
        e.url = must(
          await db().storage.from("evidence").createSignedUrl(e.path, 600),
        ).signedUrl.replace(
          Deno.env.get("SUPABASE_URL")!,
          Deno.env.get("PUBLIC_SUPABASE_URL") ?? Deno.env.get("SUPABASE_URL")!,
        );
      return json({ incident: i, events, evidence });
    }
    if (b.action === "transition") {
      return json(
        must(
          await db().rpc("act_incident", {
            case_id: i.id,
            actor_text: actor.id,
            act: b.act,
            note: b.note ?? "",
            can_approve: ["admin", "supervisor"].includes(actor.role),
          }),
        ),
      );
    }
    if (b.action === "evidence") {
      const bytes = Uint8Array.from(atob(b.base64), (c) => c.charCodeAt(0));
      if (i.status === "resolved") throw Error("Caso cerrado");
      await saveEvidence(
        i.id,
        b.site_id,
        bytes,
        b.mime,
        b.caption ?? "",
        actor.id,
      );
      return json({ ok: true });
    }
    if (b.action === "assign") {
      const c = must(
        await db()
          .from("contacts")
          .select("*")
          .eq("id", b.contact_id)
          .eq("site_id", b.site_id)
          .eq("active", true)
          .single(),
      );
      must(
        await db()
          .from("incidents")
          .update({ assignee_id: c.id, updated_at: new Date().toISOString() })
          .eq("id", i.id),
      );
      must(
        await db()
          .from("incident_events")
          .insert({
            incident_id: i.id,
            actor: actor.id,
            action: "assigned",
            body: c.name,
          }),
      );
      await queue(
        c.phone,
        b.site_id,
        "Se te asignó #" + i.id + ": " + i.title,
        "assign:" + i.id + ":" + crypto.randomUUID(),
        i.id,
      );
      return json({ ok: true });
    }
    if (b.action === "reply") {
      if (!b.text?.trim()) throw Error("Mensaje vacío");
      const conversations = must(
        await db()
          .from("conversations")
          .select("phone")
          .eq("site_id", b.site_id)
          .eq("incident_id", i.id),
      );
      if (!conversations.length) throw Error("No hay conversación asociada");
      for (const c of conversations)
        await queue(
          c.phone,
          b.site_id,
          b.text,
          "staff:" + crypto.randomUUID(),
          i.id,
        );
      return json({ ok: true });
    }
    throw Error("Acción inválida");
  } catch (e) {
    return error(e);
  }
});
