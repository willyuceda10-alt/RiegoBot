export type Level = { name: string; after_minutes: number; contacts: string[] };
export type Rule = {
  id?: string;
  site_id: string;
  name: string;
  kind: "event" | "threshold" | "support";
  entity: string;
  field: string;
  operator: "eq" | "gt" | "lt";
  value: number;
  dream_id?: string | null;
  severity: string;
  stale_minutes: number;
  photo_required: boolean;
  approval_required: boolean;
  reminder_minutes: number;
  ack_minutes: number;
  resolve_minutes: number;
  levels: Level[];
  enabled: boolean;
};
export function validateRule(r: Rule) {
  if (
    !r.name?.trim() ||
    !r.site_id ||
    !["event", "threshold", "support"].includes(r.kind) ||
    !r.entity ||
    !r.field ||
    !Number.isFinite(r.value)
  )
    throw Error("Regla incompleta");
  if (
    !["eq", "gt", "lt"].includes(r.operator) ||
    !["baja", "media", "alta", "critica"].includes(r.severity)
  )
    throw Error("Condición inválida");
  for (const key of [
    "stale_minutes",
    "reminder_minutes",
    "ack_minutes",
    "resolve_minutes",
  ] as const)
    if (!Number.isInteger(r[key]) || r[key] < 1 || r[key] > 43200)
      throw Error("Plazos inválidos");
  if (!Array.isArray(r.levels) || !r.levels.length || r.levels.length > 8)
    throw Error("Configura entre 1 y 8 niveles");
  for (const l of r.levels)
    if (
      !l.name ||
      !Number.isInteger(l.after_minutes) ||
      l.after_minutes < 1 ||
      !l.contacts?.length
    )
      throw Error("Cada nivel requiere nombre, plazo y destinatarios");
  return r;
}
export function matches(
  r: Rule,
  o: {
    dream_id: string;
    entity: string;
    source_at: string;
    data: Record<string, unknown>;
  },
  now = Date.now(),
) {
  if (
    r.kind === "support" ||
    !r.enabled ||
    o.entity !== r.entity ||
    (r.dream_id && r.dream_id !== o.dream_id)
  )
    return false;
  const age = now - Date.parse(o.source_at);
  if (!Number.isFinite(age) || age < -60000 || age > r.stale_minutes * 60000)
    return false;
  const raw = o.data[r.field];
  if (raw === null || raw === "" || typeof raw === "boolean") return false;
  const v = Number(raw);
  return (
    Number.isFinite(v) &&
    (r.operator === "gt"
      ? v > r.value
      : r.operator === "lt"
        ? v < r.value
        : v === r.value)
  );
}
export type Intent = {
  kind: string;
  id?: number;
  note?: string;
  dream?: string;
  entity?: string;
  today?: boolean;
};
export function canAccessIncident(
  incident: {
    site_id: string;
    assignee_id?: string;
    policy: { levels?: Level[] };
    source_data?: { requester_phone?: string };
  },
  contact: { site_id: string; id: string; phone: string; role: string },
) {
  return (
    incident.site_id === contact.site_id &&
    (["supervisor", "jefe", "mantenimiento", "admin"].includes(contact.role) ||
      incident.assignee_id === contact.id ||
      incident.source_data?.requester_phone === contact.phone ||
      (incident.policy.levels ?? []).some((level) =>
        level.contacts.includes(contact.id),
      ))
  );
}
export function parseMessage(text: string): Intent {
  const t = text
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .trim();
  const m = text
    .trim()
    .match(
      /^(recibido|atendiendo|subsanar|aprobar|reabrir|caso)\s+#?(\d+)(?:\s+([\s\S]+))?$/i,
    );
  if (m)
    return {
      kind: (
        {
          recibido: "ack",
          atendiendo: "start",
          subsanar: "submit",
          aprobar: "approve",
          reabrir: "reopen",
          caso: "select",
        } as Record<string, string>
      )[m[1].toLowerCase()],
      id: Number(m[2]),
      note: m[3] ?? "",
    };
  if (/^(soporte|necesito (ayuda|soporte))/i.test(t))
    return {
      kind: "support",
      note: text,
      dream: t.match(/dream\s*(\d+)/i)?.[1],
    };
  if (/incidencias|mis casos|pendientes/i.test(t)) return { kind: "incidents" };
  const dream = t.match(/dream\s*(\d+)/i)?.[1];
  if (/alarma|evento/i.test(t))
    return { kind: "query", entity: "Reports", dream };
  if (/caudal/i.test(t)) return { kind: "query", entity: "RTWMFlow", dream };
  if (/fertili|fertirriego/i.test(t))
    return {
      kind: "query",
      entity: /hoy|diari/i.test(t) ? "DailyFert" : "LastFert",
      dream,
      today: /hoy/i.test(t),
    };
  if (/consumo|cuanto.*reg|agua.*hoy/i.test(t))
    return { kind: "query", entity: "DailyWM", dream, today: /hoy/i.test(t) };
  if (/medidor|lectura/i.test(t))
    return { kind: "query", entity: "LastWM", dream };
  if (/programa/i.test(t)) return { kind: "query", entity: "Programs", dream };
  if (/nombre.*valvula|catalogo/i.test(t))
    return { kind: "query", entity: "TactName10", dream };
  if (/valvula|regando|activo/i.test(t)) return { kind: "live_state", dream };
  if (/estado|como esta|resumen|operativo/i.test(t))
    return { kind: "status", dream };
  return { kind: "help" };
}
export function nextRetry(attempt: number) {
  return Math.min(3600, 30 * 2 ** Math.min(attempt, 7));
}
export const help =
  "Puedes consultar: estado Dream 11, caudal Dream 13, consumo hoy Dream 17, alarmas, medidores, fertilización y programas. Incidencias: PENDIENTES; RECIBIDO 123; ATENDIENDO 123; CASO 123 (antes de enviar fotos); SUBSANAR 123 descripción. Para ayuda humana: SOPORTE Dream 11 descripción.";
