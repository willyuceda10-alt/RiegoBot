import { db, json, error, must, sha } from "../_shared/common.ts";
import { matches, type Rule } from "../../../core/domain.ts";
Deno.serve(async (req) => {
  if (req.method !== "POST") return json({ error: "POST requerido" }, 405);
  try {
    const body = await req.json();
    if (
      !body.collector_id ||
      !body.batch_id ||
      !Array.isArray(body.rows) ||
      body.rows.length > 500
    )
      throw Error("Lote inválido (máximo 500)");
    const c = must(
      await db()
        .from("collectors")
        .select("*")
        .eq("id", body.collector_id)
        .eq("enabled", true)
        .single(),
    );
    if (
      (await sha(req.headers.get("x-collector-token") ?? "")) !== c.token_hash
    )
      return json({ error: "Credencial inválida" }, 401);
    const dreams = must(
      await db()
        .from("dreams")
        .select("dream_id")
        .eq("site_id", c.site_id)
        .eq("enabled", true),
    ).map((x) => x.dream_id);
    const rows = body.rows.map((r: any) => {
      if (
        !dreams.includes(String(r.dream_id)) ||
        !r.entity ||
        !r.source_key ||
        !Number.isFinite(Date.parse(r.source_at)) ||
        !r.data
      )
        throw Error("Observación inválida o Dream no autorizado");
      return { ...r, site_id: c.site_id };
    });
    // Atomic persistence plus batch acknowledgement; alert evaluation is safe to repeat.
    must(
      await db().rpc("ingest_batch", {
        batch: body.batch_id,
        collector: c.id,
        rows: rows,
      }),
    );
    const rules = must(
      await db()
        .from("rules")
        .select("*")
        .eq("site_id", c.site_id)
        .eq("enabled", true),
    ) as Rule[];
    for (const row of rows)
      for (const rule of rules) {
        const asset = [
          row.dream_id,
          row.entity,
          row.data.System ?? "",
          row.data.ObjSubType ?? "",
          row.data.ObjNum ?? row.data.Repid2 ?? row.data.Repid1 ?? "",
        ].join(":");
        if (matches(rule, row))
          must(
            await db().rpc("evaluate_alert", {
              rule: rule.id,
              source: row.revision_key ?? row.source_key,
              dream: row.dream_id,
              asset,
              raw: row,
            }),
          );
        // A normal sample is not an automatic administrative closure.
      }
    return json({ accepted: rows.length, batch_id: body.batch_id });
  } catch (e) {
    return error(e);
  }
});
