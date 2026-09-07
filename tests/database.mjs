import pg from "pg";
import assert from "node:assert/strict";
const db = new pg.Client({
  connectionString:
    process.env.TEST_DATABASE_URL ??
    "postgresql://postgres:postgres@127.0.0.1:55322/postgres",
});
await db.connect();
try {
  await db.query("begin");
  const s = (
    await db.query(
      "insert into sites(name) values('Integration test') returning id",
    )
  ).rows[0].id;
  const c = (
    await db.query(
      "insert into contacts(site_id,name,phone) values($1,'Regador','51911111111') returning id",
      [s],
    )
  ).rows[0].id;
  const c2 = (
    await db.query(
      "insert into contacts(site_id,name,phone,role) values($1,'Supervisor','51922222222','supervisor') returning id",
      [s],
    )
  ).rows[0].id;
  const policy = {
    severity: "alta",
    ack_minutes: 1,
    resolve_minutes: 2,
    reminder_minutes: 1,
    photo_required: true,
    approval_required: true,
    levels: [
      { name: "regador", after_minutes: 2, contacts: [c] },
      { name: "supervisor", after_minutes: 3, contacts: [c2] },
    ],
  };
  const r = (
    await db.query(
      "insert into rules(site_id,name,kind,entity,value,levels) values($1,'test','event','Reports',33,$2) returning id",
      [s, JSON.stringify(policy.levels)],
    )
  ).rows[0].id;
  const open = () =>
    db.query(
      "select open_incident($1,$2,'11','Prueba','11:valve', $3,'{}') id",
      [s, r, policy],
    );
  const id = (await open()).rows[0].id;
  assert.equal((await open()).rows[0].id, id, "one open episode");
  assert.equal(
    (
      await db.query(
        "select count(*)::int n from jobs where payload->>'incident_id'=$1",
        [String(id)],
      )
    ).rows[0].n,
    1,
    "one initial notification",
  );
  async function reject(sql, args) {
    await db.query("savepoint rejection");
    await assert.rejects(db.query(sql, args));
    await db.query("rollback to savepoint rejection");
  }
  await reject(
    "select act_incident($1,'regador','submit','Reparación concluida',false)",
    [id],
  );
  await db.query("select act_incident($1,'regador','ack','',false)", [id]);
  assert.equal(
    (await db.query("select status from incidents where id=$1", [id])).rows[0]
      .status,
    "acknowledged",
  );
  await db.query(
    "update incidents set next_escalation_at=now()-interval '1 minute' where id=$1",
    [id],
  );
  await db.query("select tick_incidents()");
  assert.equal(
    (await db.query("select level from incidents where id=$1", [id])).rows[0]
      .level,
    1,
  );
  await db.query(
    "insert into evidence(incident_id,path,mime,actor) values($1,'test-photo','image/png','regador')",
    [id],
  );
  await db.query(
    "select act_incident($1,'regador','submit','Se reparó la conexión',false)",
    [id],
  );
  assert.equal(
    (await db.query("select status from incidents where id=$1", [id])).rows[0]
      .status,
    "pending_review",
  );
  await reject("select act_incident($1,'regador','approve','',false)", [id]);
  await reject("select act_incident($1,'regador','ack','',false)", [id]);
  await db.query("select act_incident($1,'supervisor','approve','',true)", [
    id,
  ]);
  const jobs = (await db.query("select count(*)::int n from jobs")).rows[0].n;
  await db.query("select tick_incidents()");
  assert.equal(
    (await db.query("select count(*)::int n from jobs")).rows[0].n,
    jobs,
    "closed cases stop reminders",
  );
  assert.notEqual(
    (await open()).rows[0].id,
    id,
    "new occurrence after closure",
  );
  const thresholdRule = (
    await db.query(
      "insert into rules(site_id,name,kind,entity,field,operator,value,enabled,levels,photo_required,approval_required) values($1,'Latest sample','threshold','RTWMFlow','ValueA','gt',10,true,$2,false,false) returning id",
      [s, JSON.stringify(policy.levels)],
    )
  ).rows[0].id;
  const currentAt = new Date().toISOString();
  const staleRow = {
    entity: "RTWMFlow",
    source_key: "mutable-meter",
    source_at: new Date(Date.now() - 60000).toISOString(),
    data: { ValueA: 20 },
  };
  await db.query(
    "insert into observations(site_id,dream_id,entity,source_key,source_at,data) values($1,'11','RTWMFlow','mutable-meter',$2,'{\"ValueA\":5}')",
    [s, currentAt],
  );
  const evaluate = (source, row) =>
    db.query("select evaluate_alert($1,$2,'11','meter-1',$3) id", [
      thresholdRule,
      source,
      row,
    ]);
  assert.equal(
    (await evaluate("delayed", staleRow)).rows[0].id,
    null,
    "Delayed high sample cannot override newer normal reading",
  );
  assert.equal(
    (
      await evaluate("normal", {
        ...staleRow,
        source_at: currentAt,
        data: { ValueA: 5 },
      })
    ).rows[0].id,
    null,
    "Database rechecks current threshold",
  );
  await db.query(
    "update observations set data='{\"ValueA\":20}' where site_id=$1 and source_key='mutable-meter'",
    [s],
  );
  const currentRow = { ...staleRow, source_at: currentAt };
  const validAlert = (await evaluate("current", currentRow)).rows[0].id;
  assert.ok(validAlert, "Current matching sample opens alert");
  await db.query(
    "select act_incident($1,'test','submit','Medidor revisado',false)",
    [validAlert],
  );
  assert.equal(
    (await evaluate("current", currentRow)).rows[0].id,
    null,
    "Replayed revision cannot reopen closed alert",
  );
  const supportRule = (
    await db.query(
      "insert into rules(site_id,name,kind,entity,value,enabled,levels,photo_required,approval_required) values($1,'Support','support','Reports',0,true,$2,false,false) returning id",
      [s, JSON.stringify(policy.levels)],
    )
  ).rows[0].id;
  const support = () =>
    db.query(
      "select open_support_incident($1,'support-message','51911111111',null,'Solicitud de ayuda') id",
      [supportRule],
    );
  const supportId = (await support()).rows[0].id;
  await db.query(
    "select act_incident($1,'test','submit','Atención completada',false)",
    [supportId],
  );
  assert.equal(
    (await support()).rows[0].id,
    supportId,
    "Retried support message keeps original closed case instead of opening another",
  );
  const oldCases = (
    await db.query(
      `insert into incidents(site_id,title,policy,assignee_id,source_data,created_at,next_reminder_at,next_escalation_at)
     values
     ($1,'Older assignment','{"levels":[]}',$2,'{}',now()-interval '30 days',now(),now()),
     ($1,'Older support','{"levels":[]}',null,'{"requester_phone":"51911111111"}',now()-interval '30 days',now(),now()),
     ($1,'Older policy',$3,null,'{}',now()-interval '30 days',now(),now()) returning id`,
      [s, c, policy],
    )
  ).rows.map((row) => row.id);
  await db.query(
    `insert into incidents(site_id,title,policy,next_reminder_at,next_escalation_at)
     select $1,'Unrelated recent '||n,'{"levels":[]}',now(),now() from generate_series(1,60) n`,
    [s],
  );
  const visibleCases = (
    await db.query("select id from contact_incidents($1)", [c])
  ).rows.map((row) => row.id);
  for (const oldId of oldCases)
    assert.ok(
      visibleCases.includes(oldId),
      "Authorization precedes the result limit for old assignments, support and policy recipients",
    );
  assert.ok(
    visibleCases.length <= 15,
    "Default WhatsApp response stays bounded",
  );
  assert.equal(
    (
      await db.query("select count(*)::int n from contact_incidents($1,15)", [
        c2,
      ])
    ).rows[0].n,
    15,
    "Supervisors also receive bounded results",
  );
  await db.query("update contacts set active=false where id=$1", [c]);
  assert.equal(
    (await db.query("select count(*)::int n from contact_incidents($1)", [c]))
      .rows[0].n,
    0,
    "Inactive contacts cannot list cases",
  );
  await db.query("set local role authenticated");
  await reject("select * from contact_incidents($1)", [c2]);
  assert.equal(
    (await db.query("select count(*)::int n from incidents")).rows[0].n,
    0,
    "RLS hides unassigned sites",
  );
  await db.query("reset role");
  await db.query("rollback");
  console.log(
    "Database lifecycle, deduplication, photos, escalation, approval, stale alerts, support replay, old assigned cases and RLS: PASS",
  );
} finally {
  await db.end();
}
