import { test } from "node:test";
import assert from "node:assert/strict";
import { RequestScope, StaleScopeError } from "../core/request-scope.ts";
import {
  matches,
  parseMessage,
  validateRule,
  nextRetry,
  canAccessIncident,
  type Rule,
} from "../core/domain.ts";
const rule: Rule = {
  site_id: "s",
  name: "Caudal alto",
  kind: "threshold",
  entity: "RTWMFlow",
  field: "ValueA",
  operator: "gt",
  value: 10,
  severity: "alta",
  stale_minutes: 5,
  photo_required: true,
  approval_required: true,
  reminder_minutes: 10,
  ack_minutes: 5,
  resolve_minutes: 30,
  enabled: true,
  levels: [{ name: "Regador", after_minutes: 30, contacts: ["c"] }],
};
test("No alerta con telemetría vieja, futura, nula o de otro Dream", () => {
  const now = Date.now(),
    row = {
      dream_id: "11",
      entity: "RTWMFlow",
      source_at: new Date(now).toISOString(),
      data: { ValueA: 12 },
    };
  assert.equal(matches(rule, row, now), true);
  assert.equal(
    matches(
      rule,
      { ...row, source_at: new Date(now - 3600000).toISOString() },
      now,
    ),
    false,
  );
  assert.equal(
    matches(
      rule,
      { ...row, source_at: new Date(now + 3600000).toISOString() },
      now,
    ),
    false,
  );
  assert.equal(matches(rule, { ...row, data: { ValueA: null } }, now), false);
  assert.equal(matches({ ...rule, dream_id: "13" }, row, now), false);
});
test("Reglas requieren destinatarios y plazos positivos", () => {
  assert.throws(() => validateRule({ ...rule, levels: [] }));
  assert.throws(() => validateRule({ ...rule, ack_minutes: 0 }));
  assert.equal(validateRule(rule).name, rule.name);
});
test("Comandos distinguen recibido de subsanado y conservan la descripción", () => {
  assert.deepEqual(parseMessage("SUBSANAR #123 reparación terminada"), {
    kind: "submit",
    id: 123,
    note: "reparación terminada",
  });
  assert.equal(parseMessage("RECIBIDO 123").kind, "ack");
  assert.equal(parseMessage("CASO 123").kind, "select");
  assert.equal(parseMessage("¿Qué está regando ahora?").kind, "live_state");
});
test("Consultas seleccionan tabla por ámbito", () => {
  assert.equal(parseMessage("alarmas Dream 13").entity, "Reports");
  assert.equal(parseMessage("consumo hoy Dream 17").today, true);
  assert.equal(parseMessage("fertilización Dream 11").entity, "LastFert");
});
test("Backoff acotado", () => {
  assert.equal(nextRetry(1), 60);
  assert.equal(nextRetry(20), 3600);
});
test("Una respuesta pendiente no sobrevive logout y reingreso al mismo sitio", async () => {
  const requests = new RequestScope();
  const pendingScope = requests.enter("user-a:site-a");
  let complete!: (value: string) => void;
  const response = new Promise<string>((resolve) => {
    complete = resolve;
  });
  const pendingCredential = (async () => {
    requests.assertCurrent(pendingScope);
    const credential = await response;
    requests.assertCurrent(pendingScope);
    return credential;
  })();
  requests.invalidate(); // Immediate logout invalidation, before React renders.
  requests.enter(":");
  const newSessionScope = requests.enter("user-a:site-a");
  complete("secret-from-old-session");
  await assert.rejects(pendingCredential, StaleScopeError);
  requests.assertCurrent(newSessionScope);
  requests.enter("user-a:site-b");
  assert.throws(() => requests.assertCurrent(newSessionScope), StaleScopeError);
});
test("Asignados y solicitantes ven sus casos sin permitir acceso entre sitios", () => {
  const contact = {
    id: "regador",
    phone: "51900000001",
    site_id: "site-a",
    role: "regador",
  };
  const incident = { site_id: "site-a", policy: { levels: [] } };
  assert.equal(canAccessIncident(incident, contact), false);
  assert.equal(
    canAccessIncident({ ...incident, assignee_id: contact.id }, contact),
    true,
  );
  assert.equal(
    canAccessIncident(
      { ...incident, source_data: { requester_phone: contact.phone } },
      contact,
    ),
    true,
  );
  assert.equal(
    canAccessIncident(
      { ...incident, site_id: "site-b", assignee_id: contact.id },
      contact,
    ),
    false,
  );
  assert.equal(
    canAccessIncident(
      { ...incident, site_id: "site-b" },
      { ...contact, role: "admin" },
    ),
    false,
  );
});
