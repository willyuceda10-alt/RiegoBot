import { execFileSync } from "node:child_process";
import fs from "node:fs";
import { createClient } from "@supabase/supabase-js";
const output = execFileSync(
  process.platform === "win32" ? "npx.cmd" : "npx",
  ["supabase", "status", "-o", "json"],
  { encoding: "utf8", shell: process.platform === "win32" },
);
const env = JSON.parse(output.slice(output.indexOf("{")));
if (!env.API_URL.includes("127.0.0.1")) throw Error("LOCAL ONLY");
fs.writeFileSync(
  ".env.local",
  "VITE_SUPABASE_URL=" +
    env.API_URL +
    "\nVITE_SUPABASE_ANON_KEY=" +
    env.ANON_KEY +
    "\n",
);
fs.writeFileSync(
  "supabase/functions/.env.local",
  "DRY_RUN=true\nWORKER_SECRET=local-worker-only\nALLOWED_ORIGIN=http://127.0.0.1:5178\nPUBLIC_SUPABASE_URL=http://127.0.0.1:55321\n",
);
const db = createClient(env.API_URL, env.SERVICE_ROLE_KEY);
const email = "operacion@riegobot.local",
  password = "RiegoBot-Local-2026!";
const { data: users } = await db.auth.admin.listUsers();
let user = users.users.find((x) => x.email === email);
if (!user) {
  const { data, error } = await db.auth.admin.createUser({
    email,
    password,
    email_confirm: true,
  });
  if (error) throw error;
  user = data.user;
}
let { data: site } = await db
  .from("sites")
  .select("*")
  .eq("name", "Semilla Lab · Piloto local")
  .maybeSingle();
if (!site) {
  const r = await db
    .from("sites")
    .insert({ name: "Semilla Lab · Piloto local" })
    .select()
    .single();
  if (r.error) throw r.error;
  site = r.data;
}
const check = (r) => {
  if (r.error) throw r.error;
  return r.data;
};
check(
  await db
    .from("memberships")
    .upsert({ user_id: user.id, site_id: site.id, role: "admin" }),
);
check(
  await db
    .from("dreams")
    .upsert(
      [11, 13, 17].map((n) => ({
        site_id: site.id,
        dream_id: String(n),
        name: "Dream " + n,
      })),
    ),
);
for (const [name, phone, role] of [
  ["Regador de prueba", "51900000001", "regador"],
  ["Supervisor de prueba", "51900000002", "supervisor"],
  ["Jefe de prueba", "51900000003", "jefe"],
  ["Mantenimiento de prueba", "51900000004", "mantenimiento"],
]) {
  check(
    await db
      .from("contacts")
      .upsert(
        { site_id: site.id, name, phone, role },
        { onConflict: "site_id,phone" },
      ),
  );
}
const contacts = check(
  await db.from("contacts").select("*").eq("site_id", site.id),
);
const levels = contacts
  .sort((a, b) => a.phone.localeCompare(b.phone))
  .map((c) => ({ name: c.role, contacts: [c.id], after_minutes: 15 }));
let rule = check(
  await db.from("rules").select("*").eq("site_id", site.id).limit(1),
)[0];
if (!rule)
  rule = check(
    await db
      .from("rules")
      .insert({
        site_id: site.id,
        name: "Caudal fuera de condición · simulación",
        kind: "event",
        entity: "Reports",
        field: "RepCode",
        value: 33,
        enabled: true,
        severity: "alta",
        levels,
        ack_minutes: 10,
        resolve_minutes: 30,
        reminder_minutes: 15,
        photo_required: true,
        approval_required: true,
      })
      .select()
      .single(),
  );
const support = check(
  await db
    .from("rules")
    .select("id")
    .eq("site_id", site.id)
    .eq("kind", "support"),
);
if (!support.length)
  check(
    await db
      .from("rules")
      .insert({
        ...rule,
        id: undefined,
        name: "Soporte de riego",
        kind: "support",
      }),
  );
for (const n of [11, 13, 17])
  check(
    await db.rpc("open_incident", {
      s: site.id,
      r: rule.id,
      d: String(n),
      title_text: rule.name,
      asset: "demo:" + n,
      policy_data: rule,
      raw: { simulated: true },
    }),
  );
fs.mkdirSync("runtime", { recursive: true });
fs.writeFileSync(
  "runtime/local-session.json",
  JSON.stringify({
    url: env.API_URL,
    anon: env.ANON_KEY,
    service: env.SERVICE_ROLE_KEY,
    email,
    password,
    site_id: site.id,
  }),
);
console.log(
  "Local demo ready. User:",
  email,
  "Password stored in runtime/local-session.json (local only).",
);
