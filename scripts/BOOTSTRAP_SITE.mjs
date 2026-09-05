import { createClient } from "@supabase/supabase-js";
const {
  SUPABASE_URL,
  SUPABASE_SERVICE_ROLE_KEY,
  ADMIN_EMAIL,
  SITE_NAME = "Riego piloto",
} = process.env;
if (!SUPABASE_URL || !SUPABASE_SERVICE_ROLE_KEY || !ADMIN_EMAIL)
  throw Error(
    "Set SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY and ADMIN_EMAIL locally",
  );
const db = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY);
let { data, error } = await db.auth.admin.listUsers();
if (error) throw error;
let user = data.users.find((u) => u.email === ADMIN_EMAIL);
if (!user) {
  const result = await db.auth.admin.inviteUserByEmail(ADMIN_EMAIL);
  if (result.error) throw result.error;
  user = result.data.user;
}
const existing = await db
  .from("sites")
  .select("*")
  .eq("name", SITE_NAME)
  .maybeSingle();
if (existing.error) throw existing.error;
const site =
  existing.data ??
  (await db.from("sites").insert({ name: SITE_NAME }).select().single()).data;
if (!site) throw Error("Could not create site");
for (const result of [
  await db
    .from("memberships")
    .upsert({ user_id: user.id, site_id: site.id, role: "admin" }),
  await db
    .from("dreams")
    .upsert(
      [11, 13, 17].map((n) => ({
        site_id: site.id,
        dream_id: String(n),
        name: "Dream " + n,
      })),
    ),
])
  if (result.error) throw result.error;
console.log("Site ready:", site.id);
