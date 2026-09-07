import fs from "node:fs";
import assert from "node:assert/strict";
import { createClient } from "@supabase/supabase-js";

const env = JSON.parse(fs.readFileSync("runtime/local-session.json", "utf8"));
const apiUrl = process.env.TEST_API_URL ?? env.url + "/functions/v1/api";
for (const url of [env.url, apiUrl]) {
  if (!["127.0.0.1", "localhost"].includes(new URL(url).hostname)) {
    throw Error("Security integration tests require local services");
  }
}
const admin = createClient(env.url, env.service, {
  auth: { persistSession: false },
});
const checked = ({ data, error }) => {
  if (error) throw error;
  return data;
};
const sites = [];
let userId, incidentId;
try {
  for (const name of ["Security audit A", "Security audit B"]) {
    sites.push(
      checked(await admin.from("sites").insert({ name }).select().single()).id,
    );
  }
  const email = `audit-${crypto.randomUUID()}@riegobot.local`;
  const password = crypto.randomUUID() + "Aa1!";
  userId = checked(
    await admin.auth.admin.createUser({ email, password, email_confirm: true }),
  ).user.id;
  checked(
    await admin
      .from("memberships")
      .insert({ user_id: userId, site_id: sites[0], role: "operator" }),
  );
  const phone = "51" + String(Date.now()).slice(-10);
  const supervisor = checked(
    await admin
      .from("contacts")
      .insert({
        site_id: sites[0],
        name: "Audit supervisor",
        phone,
        role: "supervisor",
      })
      .select()
      .single(),
  );
  const policy = {
    severity: "media",
    reminder_minutes: 60,
    ack_minutes: 60,
    resolve_minutes: 60,
    photo_required: false,
    approval_required: true,
    levels: [
      { name: "Supervisor", after_minutes: 60, contacts: [supervisor.id] },
    ],
  };
  incidentId = checked(
    await admin.rpc("open_incident", {
      s: sites[0],
      r: null,
      d: null,
      title_text: "Security test",
      asset: crypto.randomUUID(),
      policy_data: policy,
      raw: {},
    }),
  );
  checked(
    await admin.rpc("act_incident", {
      case_id: incidentId,
      actor_text: "test",
      act: "submit",
      note: "Reparación de prueba",
      can_approve: false,
    }),
  );
  const operator = createClient(env.url, env.anon, {
    auth: { persistSession: false },
  });
  const session = checked(
    await operator.auth.signInWithPassword({ email, password }),
  ).session;
  async function call(body) {
    return fetch(apiUrl, {
      method: "POST",
      headers: {
        Authorization: "Bearer " + session.access_token,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ site_id: sites[0], ...body }),
    });
  }
  assert.equal((await call({ action: "dashboard" })).status, 200);
  assert.notEqual(
    (await call({ action: "dashboard", site_id: sites[1] })).status,
    200,
    "Cross-site dashboard must be denied",
  );
  assert.notEqual(
    (
      await call({
        action: "transition",
        incident_id: incidentId,
        act: "approve",
      })
    ).status,
    200,
    "Operator cannot approve directly",
  );
  assert.notEqual(
    (await call({ action: "simulate", phone, text: "APROBAR " + incidentId }))
      .status,
    200,
    "Operator cannot impersonate supervisor through simulation",
  );
  const incident = checked(
    await admin
      .from("incidents")
      .select("status")
      .eq("id", incidentId)
      .single(),
  );
  assert.equal(
    incident.status,
    "pending_review",
    "Rejected simulation must not apply a supervisor transition",
  );
  const visible = checked(await operator.from("sites").select("id"));
  assert.deepEqual(
    visible.map((row) => row.id),
    [sites[0]],
    "RLS only exposes the member's site",
  );
  const mutation = await operator
    .from("contacts")
    .insert({ site_id: sites[0], name: "Forbidden", phone: "51900009999" });
  assert.ok(mutation.error, "Direct client writes must be denied");
  const credentialRead = await operator.from("collectors").select("token_hash");
  assert.ok(credentialRead.error, "Collector hashes must not be readable");
  console.log(
    "API security: site isolation, RLS, write restrictions, collector secrets, operator approval and simulation bypass PASS",
  );
} finally {
  if (incidentId) {
    checked(
      await admin
        .from("jobs")
        .delete()
        .eq("payload->>incident_id", String(incidentId)),
    );
    checked(
      await admin
        .from("incident_events")
        .delete()
        .eq("incident_id", incidentId),
    );
    checked(await admin.from("incidents").delete().eq("id", incidentId));
  }
  if (sites.length) {
    checked(await admin.from("contacts").delete().in("site_id", sites));
    checked(await admin.from("memberships").delete().in("site_id", sites));
    checked(await admin.from("sites").delete().in("id", sites));
  }
  if (userId) checked(await admin.auth.admin.deleteUser(userId));
}
