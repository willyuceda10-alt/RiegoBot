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
  await db.query("set local role authenticated");
  assert.equal(
    (await db.query("select count(*)::int n from incidents")).rows[0].n,
    0,
    "RLS hides unassigned sites",
  );
  await db.query("reset role");
  await db.query("rollback");
  console.log(
    "Database lifecycle, deduplication, photos, escalation, approval and RLS: PASS",
  );
} finally {
  await db.end();
}
