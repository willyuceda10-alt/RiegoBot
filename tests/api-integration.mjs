import fs from "node:fs";
import assert from "node:assert/strict";
import { createClient } from "@supabase/supabase-js";
const env = JSON.parse(fs.readFileSync("runtime/local-session.json", "utf8"));
if (!env.url.startsWith("http://127.0.0.1:")) throw Error("Local tests only");
const client = createClient(env.url, env.anon);
const auth = await client.auth.signInWithPassword({
  email: env.email,
  password: env.password,
});
if (auth.error) throw auth.error;
const admin = createClient(env.url, env.service),
  token = auth.data.session.access_token;
async function call(action, data = {}, status = 200) {
  const r = await fetch(env.url + "/functions/v1/api", {
    method: "POST",
    headers: {
      Authorization: "Bearer " + token,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ site_id: env.site_id, action, ...data }),
  });
  const b = await r.json();
  assert.equal(r.status, status, JSON.stringify(b));
  return b;
}
const dashboard = await call("dashboard");
assert.ok(dashboard.incidents.length >= 3);
const r = await call("collector", { name: "API integration" });
const ingest = await fetch(env.url + "/functions/v1/ingest", {
  method: "POST",
  headers: { "Content-Type": "application/json", "x-collector-token": r.token },
  body: JSON.stringify({
    collector_id: r.collector.id,
    batch_id: crypto.randomUUID(),
    rows: [
      {
        dream_id: "11",
        entity: "Reports",
        source_key: "integration-" + crypto.randomUUID(),
        source_at: new Date().toISOString(),
        data: { RepCode: 33, RepCodeStr: "Prueba", Repid2: 999 },
      },
    ],
  }),
});
assert.equal(ingest.status, 200, await ingest.text());
const cases = (await call("dashboard")).incidents;
const i = cases.find((x) => x.source_data?.data?.Repid2 === 999);
assert.ok(i);
await call(
  "transition",
  { incident_id: i.id, act: "submit", note: "Reparación completada" },
  400,
);
await call("transition", { incident_id: i.id, act: "ack" });
const photo =
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jSucAAAAASUVORK5CYII=";
await call("evidence", { incident_id: i.id, base64: photo, mime: "image/png" });
await call("transition", {
  incident_id: i.id,
  act: "submit",
  note: "Reparación completada",
});
await call("transition", { incident_id: i.id, act: "approve" });
const detail = await call("detail", { incident_id: i.id });
assert.equal(detail.incident.status, "resolved");
assert.equal(detail.evidence.length, 1);
assert.equal((await fetch(detail.evidence[0].url)).status, 200);
await call("simulate", { phone: "51900000001", text: "caudal Dream 11" });
const unauthorized = await fetch(env.url + "/functions/v1/api", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ action: "dashboard", site_id: env.site_id }),
});
assert.notEqual(unauthorized.status, 200);
console.log(
  "API integration: ingest, photo Storage, acknowledge, submit, approve, simulation, authorization PASS",
);
