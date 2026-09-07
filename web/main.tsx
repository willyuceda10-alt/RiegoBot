import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { createClient, Session } from "@supabase/supabase-js";
import { RequestScope, StaleScopeError } from "../core/request-scope";
import "./style.css";
const url = import.meta.env.VITE_SUPABASE_URL,
  key = import.meta.env.VITE_SUPABASE_ANON_KEY;
const client = url && key ? createClient(url, key) : null;
type Data = {
  incidents: any[];
  rules: any[];
  contacts: any[];
  dreams: any[];
  collectors: any[];
  messages: any[];
};
const empty: Data = {
  incidents: [],
  rules: [],
  contacts: [],
  dreams: [],
  collectors: [],
  messages: [],
};
const statuses: Record<string, string> = {
  open: "Abierta",
  acknowledged: "Recibida",
  in_progress: "En atención",
  pending_review: "Por validar",
  resolved: "Resuelta",
};
const fmt = (x: string) =>
  x
    ? new Date(x).toLocaleString("es-PE", {
        dateStyle: "short",
        timeStyle: "short",
      })
    : "Sin registro";
function App() {
  const [session, setSession] = useState<Session | null>(null),
    [sites, setSites] = useState<any[]>([]),
    [site, setSite] = useState(""),
    [data, setData] = useState<Data>(empty);
  const [tab, setTab] = useState("Incidencias"),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [search, setSearch] = useState(""),
    [filter, setFilter] = useState("pending");
  const [detail, setDetail] = useState<any>(null),
    [rule, setRule] = useState<any>(null),
    [token, setToken] = useState<any>(null),
    [deliveries, setDeliveries] = useState<any[]>([]);
  const [dashboardLoaded, setDashboardLoaded] = useState(false),
    [dashboardError, setDashboardError] = useState("");
  const requests = useRef(new RequestScope());
  const activeUser = useRef<string | undefined>(undefined);
  const scope = requests.current.enter(`${session?.user.id ?? ""}:${site}`);
  function clearPrivateState() {
    setData(empty);
    setDetail(null);
    setRule(null);
    setToken(null);
    setDeliveries([]);
    setError("");
    setBusy(false);
    setDashboardLoaded(false);
    setDashboardError("");
  }
  async function api(action: string, body: any = {}) {
    requests.current.assertCurrent(scope);
    if (!client) throw Error("Configura Supabase");
    const { data, error } = await client.functions.invoke("api", {
      body: { action, site_id: site, ...body },
    });
    requests.current.assertCurrent(scope);
    if (error) {
      const response = (error as any).context;
      let msg =
        "No se pudo conectar con RiegoBot. Comprueba la conexión y vuelve a intentarlo.";
      try {
        msg = (await response.json()).error ?? msg;
      } catch {}
      if (
        response?.status >= 500 ||
        /Edge Function|Failed to fetch|NetworkError|fetch failed/i.test(msg)
      )
        msg =
          "El servicio de RiegoBot no está disponible. Comprueba la conexión y vuelve a intentarlo.";
      requests.current.assertCurrent(scope);
      throw Error(msg);
    }
    if (data?.error) throw Error(data.error);
    return data;
  }
  async function run(fn: () => Promise<void>) {
    if (!requests.current.isCurrent(scope)) return;
    setBusy(true);
    setError("");
    try {
      await fn();
    } catch (e) {
      if (requests.current.isCurrent(scope) && !(e instanceof StaleScopeError))
        setError(e instanceof Error ? e.message : String(e));
    } finally {
      if (requests.current.isCurrent(scope)) setBusy(false);
    }
  }
  const refresh = async () => {
    if (site) {
      try {
        const result = await api("dashboard");
        if (requests.current.isCurrent(scope)) {
          setData(result);
          setDashboardLoaded(true);
          setDashboardError("");
        }
      } catch (e) {
        if (
          requests.current.isCurrent(scope) &&
          !(e instanceof StaleScopeError)
        ) {
          setDashboardError(
            "No se pudieron cargar los datos. Pulsa Actualizar para reintentar.",
          );
        }
        throw e;
      }
    }
  };
  useEffect(() => {
    if (!client) return;
    let authEvents = 0;
    const applySession = (next: Session | null) => {
      if (activeUser.current !== next?.user.id) {
        requests.current.invalidate();
        activeUser.current = next?.user.id;
        clearPrivateState();
        setSites([]);
        setSite("");
      }
      setSession(next);
    };
    client.auth.getSession().then(({ data }) => {
      if (authEvents === 0) applySession(data.session);
    });
    const { data } = client.auth.onAuthStateChange((_, s) => {
      authEvents++;
      applySession(s);
    });
    return () => data.subscription.unsubscribe();
  }, []);
  useEffect(() => {
    let cancelled = false;
    setSites([]);
    setSite("");
    setData(empty);
    setDetail(null);
    setRule(null);
    setToken(null);
    setDeliveries([]);
    setDashboardLoaded(false);
    setDashboardError("");
    if (session && client)
      client
        .from("sites")
        .select("*")
        .then(({ data, error }) => {
          if (cancelled || !requests.current.isCurrent(scope)) return;
          if (error) setError(error.message);
          else {
            setSites(data ?? []);
            setSite(data?.[0]?.id ?? "");
          }
        });
    return () => {
      cancelled = true;
    };
  }, [session?.user.id]);
  useEffect(() => {
    setData(empty);
    setDetail(null);
    setRule(null);
    setToken(null);
    setDeliveries([]);
    setDashboardLoaded(false);
    setDashboardError("");
    if (site) {
      run(refresh);
      const t = setInterval(() => refresh().catch(() => {}), 20000);
      return () => clearInterval(t);
    }
  }, [site]);
  const form = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    return Object.fromEntries(new FormData(e.currentTarget));
  };
  useEffect(() => {
    if (!detail && !rule) return;
    const previous = document.activeElement as HTMLElement | null;
    const dialog = document.querySelector(
      '[role="dialog"]',
    ) as HTMLElement | null;
    const focusable = () =>
      Array.from(
        dialog?.querySelectorAll<HTMLElement>(
          "button:not([disabled]),input,select,textarea,a[href]",
        ) ?? [],
      );
    focusable()[0]?.focus();
    const trap = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setDetail(null);
        setRule(null);
      }
      if (e.key === "Tab") {
        const items = focusable(),
          first = items[0],
          last = items.at(-1);
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last?.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first?.focus();
        }
      }
    };
    document.addEventListener("keydown", trap);
    return () => {
      document.removeEventListener("keydown", trap);
      previous?.focus();
    };
  }, [!!detail, !!rule]);
  const pending = data.incidents.filter((i) => i.status !== "resolved");
  const statValue = (value: number | string) =>
    dashboardLoaded && !dashboardError ? value : "—";
  const openDetail = async (id: number) => {
    const result = await api("detail", { incident_id: id });
    if (requests.current.isCurrent(scope)) setDetail(result);
  };
  const refreshDeliveries = async () => {
    const result = await api("deliveries");
    if (requests.current.isCurrent(scope)) setDeliveries(result);
  };
  const transition = (act: string, note = "") =>
    run(async () => {
      await api("transition", { incident_id: detail.incident.id, act, note });
      await openDetail(detail.incident.id);
      await refresh();
    });
  if (!client)
    return (
      <main className="setup">
        <Brand />
        <h1>Conecta tu centro de riego</h1>
        <p>
          Copia .env.example a .env.local y configura la URL y clave pública de
          Supabase. No utilices claves administrativas en el navegador.
        </p>
        <code>Proyecto: zdgfjepoptlwjaoxvuju</code>
      </main>
    );
  if (!session)
    return (
      <main className="login">
        <div className="login-story">
          <Brand />
          <span className="eyebrow">SEMILLA LAB · OPERACIONES</span>
          <h1>
            Cada alerta.
            <br />
            Un responsable.
            <br />
            Una solución.
          </h1>
          <p>
            Información de Dream, atención de incidencias y evidencia de campo
            en un solo lugar.
          </p>
          <small>Dream 11 / 13 / 17 · Solo lectura</small>
        </div>
        <form
          onSubmit={(e) => {
            const f = form(e);
            run(async () => {
              const { error } = await client.auth.signInWithPassword({
                email: String(f.email),
                password: String(f.password),
              });
              if (error) throw error;
            });
          }}
        >
          <span className="eyebrow">CENTRO DE OPERACIÓN</span>
          <h2>Bienvenido a RiegoBot</h2>
          <p>Ingresa con tu cuenta autorizada.</p>
          <label>
            Correo
            <input name="email" type="email" required autoComplete="username" />
          </label>
          <label>
            Contraseña
            <input
              name="password"
              type="password"
              required
              autoComplete="current-password"
            />
          </label>
          {error && (
            <p role="alert" className="error">
              {error}
            </p>
          )}
          <button disabled={busy}>Ingresar →</button>
        </form>
      </main>
    );
  return (
    <div className="app">
      <aside>
        <Brand />
        <span className="eyebrow">ESPACIO DE TRABAJO</span>
        <select
          aria-label="Sitio"
          value={site}
          onChange={(e) => {
            requests.current.invalidate();
            clearPrivateState();
            setSite(e.target.value);
          }}
        >
          {sites.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </select>
        <nav>
          {[
            "Incidencias",
            "Reglas de alerta",
            "Responsables",
            "Equipos",
            "Conversaciones",
            "Indicadores",
            "Entregas",
          ].map((t, n) => (
            <button
              key={t}
              className={tab === t ? "active" : ""}
              onClick={() => {
                setTab(t);
                if (t === "Entregas") run(refreshDeliveries);
              }}
            >
              <span>0{n + 1}</span>
              {t}
              {t === "Incidencias" && <b>{statValue(pending.length)}</b>}
            </button>
          ))}
        </nav>
        <div className="sidebar-foot">
          <span className="dot" /> Operación de solo lectura
          <p>{session.user.email}</p>
          <button
            className="link"
            onClick={() => {
              requests.current.invalidate();
              clearPrivateState();
              setSession(null);
              void client.auth.signOut().then(({ error }) => {
                if (error) setError(error.message);
              });
            }}
          >
            Cerrar sesión
          </button>
        </div>
      </aside>
      <main>
        <header>
          <div>
            <span className="eyebrow">
              RIEGO /{" "}
              {sites.find((s) => s.id === site)?.name ?? "SIN SITIO ASIGNADO"}
            </span>
            <h1>{tab}</h1>
          </div>
          <button
            className="secondary"
            disabled={busy}
            onClick={() => run(refresh)}
          >
            Actualizar ↻
          </button>
        </header>
        {!site && (
          <p className="notice">
            Tu usuario aún no tiene un sitio asignado. Ejecuta el
            aprovisionamiento inicial indicado en la documentación.
          </p>
        )}
        {error && (
          <div className="error" role="alert">
            {error}
            <button className="link" onClick={() => setError("")}>
              Cerrar
            </button>
          </div>
        )}
        {dashboardError && (
          <p className="notice" role="status">
            {dashboardError}{" "}
            {dashboardLoaded &&
              "La tabla conserva la última información recibida; no se ha confirmado su actualización."}
          </p>
        )}
        {tab === "Incidencias" && (
          <>
            <div className="stats">
              <Stat label="Pendientes" value={statValue(pending.length)} />
              <Stat
                label="Por validar"
                value={statValue(
                  pending.filter((i) => i.status === "pending_review").length,
                )}
              />
              <Stat
                label="Escaladas"
                value={statValue(pending.filter((i) => i.level > 0).length)}
              />
              <Stat
                label="Resueltas"
                value={statValue(
                  data.incidents.filter((i) => i.status === "resolved").length,
                )}
              />
            </div>
            <section>
              <div className="section-head">
                <h2>Seguimiento de campo</h2>
                <span>Últimas 200 incidencias</span>
              </div>
              <div className="filters">
                <input
                  aria-label="Buscar incidencia"
                  placeholder="Buscar por caso, Dream o descripción"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
                <select
                  aria-label="Estado"
                  value={filter}
                  onChange={(e) => setFilter(e.target.value)}
                >
                  <option value="pending">Pendientes</option>
                  <option value="all">Todas</option>
                  {Object.entries(statuses).map(([k, v]) => (
                    <option key={k} value={k}>
                      {v}
                    </option>
                  ))}
                </select>
              </div>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Caso / incidencia</th>
                      <th>Dream</th>
                      <th>Estado</th>
                      <th>Responsable</th>
                      <th>Próximo aviso</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.incidents
                      .filter(
                        (i) =>
                          (filter === "all" ||
                            (filter === "pending"
                              ? i.status !== "resolved"
                              : i.status === filter)) &&
                          JSON.stringify([i.id, i.title, i.dream_id])
                            .toLowerCase()
                            .includes(search.toLowerCase()),
                      )
                      .map((i) => (
                        <tr
                          key={i.id}
                          onClick={() => run(() => openDetail(i.id))}
                        >
                          <td>
                            <button className="case-link">
                              #{i.id} <strong>{i.title}</strong>
                            </button>
                            <small>
                              {i.severity} · {fmt(i.created_at)}
                            </small>
                          </td>
                          <td>{i.dream_id ?? "—"}</td>
                          <td>
                            <Badge status={i.status} />
                            {i.level > 0 && <small>Nivel {i.level + 1}</small>}
                          </td>
                          <td>
                            {data.contacts.find((c) => c.id === i.assignee_id)
                              ?.name ?? "Destinatarios de la regla"}
                          </td>
                          <td>
                            {i.status === "resolved"
                              ? "Cerrada"
                              : fmt(i.next_reminder_at)}
                          </td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
              {!data.incidents.length && (
                <Empty
                  text={
                    dashboardError
                      ? "No se pudieron cargar las incidencias. Pulsa Actualizar para reintentar."
                      : !dashboardLoaded
                        ? site
                          ? "Cargando incidencias…"
                          : "Selecciona un sitio para consultar sus incidencias."
                        : "Todavía no hay incidencias. Configura responsables y reglas para iniciar el seguimiento."
                  }
                />
              )}
            </section>
          </>
        )}
        {tab === "Reglas de alerta" && (
          <section>
            <div className="section-head">
              <div>
                <h2>Clases y escalamiento</h2>
                <p>Umbrales, evidencias y responsables por cada clase.</p>
              </div>
              <button
                onClick={() =>
                  setRule({
                    site_id: site,
                    name: "",
                    kind: "event",
                    entity: "Reports",
                    field: "RepCode",
                    operator: "eq",
                    value: 0,
                    severity: "media",
                    enabled: false,
                    photo_required: true,
                    approval_required: true,
                    stale_minutes: 15,
                    reminder_minutes: 15,
                    ack_minutes: 10,
                    resolve_minutes: 60,
                    levels: [
                      { name: "Regador", after_minutes: 60, contacts: [] },
                    ],
                  })
                }
              >
                Nueva regla +
              </button>
            </div>
            {data.rules.map((r) => (
              <article className="rule-row" key={r.id}>
                <div>
                  <span className="eyebrow">
                    {r.enabled ? "ACTIVA" : "INACTIVA"} · {r.severity}
                  </span>
                  <h3>{r.name}</h3>
                  <p>
                    {r.entity}.{r.field} {r.operator} {r.value} ·{" "}
                    {r.levels.length} niveles · Recordatorio cada{" "}
                    {r.reminder_minutes} min
                  </p>
                </div>
                <button className="secondary" onClick={() => setRule({ ...r })}>
                  Configurar
                </button>
              </article>
            ))}
            {!data.rules.length && (
              <Empty text="Define primero los destinatarios, luego crea una regla. Los umbrales deben validarse con el operador de Dream." />
            )}
          </section>
        )}
        {tab === "Responsables" && (
          <section>
            <h2>Personal y destinatarios</h2>
            <p>
              Los roles controlan quién puede aprobar y recibir escalaciones.
            </p>
            <form
              className="inline-form"
              onSubmit={(e) => {
                const f = form(e);
                run(async () => {
                  await api("contact", { contact: f });
                  await refresh();
                });
              }}
            >
              <label>
                Nombre
                <input name="name" required />
              </label>
              <label>
                WhatsApp internacional
                <input
                  name="phone"
                  inputMode="tel"
                  pattern="[0-9]{8,15}"
                  required
                  placeholder="51999999999"
                />
              </label>
              <label>
                Rol
                <select name="role">
                  {[
                    "regador",
                    "supervisor",
                    "jefe",
                    "mantenimiento",
                    "admin",
                  ].map((x) => (
                    <option key={x}>{x}</option>
                  ))}
                </select>
              </label>
              <button disabled={busy}>Añadir</button>
            </form>
            <table>
              <thead>
                <tr>
                  <th>Nombre</th>
                  <th>Teléfono</th>
                  <th>Rol</th>
                  <th>Acceso</th>
                </tr>
              </thead>
              <tbody>
                {data.contacts.map((c) => (
                  <tr key={c.id}>
                    <td>{c.name}</td>
                    <td>{c.phone}</td>
                    <td>{c.role}</td>
                    <td>
                      <button
                        className="secondary"
                        onClick={() =>
                          run(async () => {
                            await api("contact", {
                              contact: { ...c, active: !c.active },
                            });
                            await refresh();
                          })
                        }
                      >
                        {c.active ? "Desactivar" : "Activar"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        )}
        {tab === "Equipos" && (
          <>
            <section>
              <h2>Dreams autorizados</h2>
              <form
                className="inline-form"
                onSubmit={(e) => {
                  const f = form(e);
                  run(async () => {
                    await api("dream", { dream: f });
                    await refresh();
                  });
                }}
              >
                <label>
                  Dream ID
                  <input name="dream_id" required pattern="[0-9]+" />
                </label>
                <label>
                  Nombre
                  <input name="name" required />
                </label>
                <button>Registrar</button>
              </form>
              {data.dreams.map((d) => (
                <div className="rule-row" key={d.dream_id}>
                  <h3>
                    {d.name} <small>Dream {d.dream_id}</small>
                  </h3>
                  <button
                    className="secondary"
                    onClick={() =>
                      run(async () => {
                        await api("dream", {
                          dream: { ...d, enabled: !d.enabled },
                        });
                        await refresh();
                      })
                    }
                  >
                    {d.enabled ? "Deshabilitar" : "Habilitar"}
                  </button>
                </div>
              ))}
            </section>
            <section>
              <h2>Unidades y escalas</h2>
              <p>
                Configura solo conversiones contrastadas con Dream. El bot
                conserva valores crudos si la conversión no está verificada.
              </p>
              <form
                className="inline-form"
                onSubmit={(e) => {
                  const f = form(e);
                  run(async () => {
                    await api("mapping", {
                      mapping: {
                        ...f,
                        scale: Number(f.scale),
                        verified: f.verified === "on",
                      },
                    });
                  });
                }}
              >
                <label>
                  Entidad
                  <select name="entity">
                    {[
                      "LastWM",
                      "DailyWM",
                      "RTWMFlow",
                      "LastFert",
                      "DailyFert",
                      "RTFertFlow",
                    ].map((x) => (
                      <option key={x}>{x}</option>
                    ))}
                  </select>
                </label>
                <label>
                  Campo
                  <input name="field" defaultValue="ValueA" required />
                </label>
                <label>
                  Unidad
                  <input name="unit" required />
                </label>
                <label>
                  Factor
                  <input
                    name="scale"
                    type="number"
                    step="any"
                    defaultValue="1"
                    required
                  />
                </label>
                <label className="check">
                  <input name="verified" type="checkbox" />
                  Verificada
                </label>
                <button>Guardar</button>
              </form>
            </section>
            <section>
              <h2>Colectores del PC local</h2>
              <form
                className="inline-form"
                onSubmit={(e) => {
                  const f = form(e);
                  run(async () => {
                    const credential = await api("collector", f);
                    if (requests.current.isCurrent(scope)) setToken(credential);
                    await refresh();
                  });
                }}
              >
                <label>
                  Nombre del PC
                  <input name="name" required />
                </label>
                <button>Crear credencial</button>
              </form>
              {token && (
                <div className="notice">
                  <p>
                    Guarda esta credencial en el PC. Se muestra una sola vez.
                  </p>
                  <code>{JSON.stringify(token, null, 2)}</code>
                  <button className="secondary" onClick={() => setToken(null)}>
                    Ya la guardé
                  </button>
                </div>
              )}
              {data.collectors.map((c) => (
                <div className="rule-row" key={c.id}>
                  <h3>{c.name}</h3>
                  <p>Última conexión: {fmt(c.last_seen)}</p>
                </div>
              ))}
            </section>
          </>
        )}
        {tab === "Entregas" && (
          <section>
            <h2>Cola de notificaciones</h2>
            <p>
              Los resultados inciertos requieren comprobar la entrega antes de
              reintentar.
            </p>
            <button
              className="secondary"
              onClick={() => run(refreshDeliveries)}
            >
              Actualizar entregas
            </button>
            <table>
              <thead>
                <tr>
                  <th>ID / destinatario</th>
                  <th>Estado</th>
                  <th>Intentos</th>
                  <th>Detalle</th>
                </tr>
              </thead>
              <tbody>
                {deliveries.map((j) => (
                  <tr key={j.id}>
                    <td>
                      #{j.id}
                      <small>{j.payload.phone}</small>
                    </td>
                    <td>{j.status}</td>
                    <td>{j.attempts}</td>
                    <td>
                      {j.last_error}
                      {["failed", "uncertain"].includes(j.status) && (
                        <form
                          onSubmit={(e) => {
                            const f = form(e);
                            run(async () => {
                              await api("retry_delivery", {
                                job_id: j.id,
                                confirmed_not_sent: f.confirmed === "on",
                              });
                              await refreshDeliveries();
                            });
                          }}
                        >
                          {j.status === "uncertain" && (
                            <label className="check">
                              <input
                                name="confirmed"
                                type="checkbox"
                                required
                              />
                              Comprobé en Meta que no se envió
                            </label>
                          )}
                          <button className="secondary">Reintentar</button>
                        </form>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        )}
        {tab === "Conversaciones" && (
          <section>
            <h2>Canal y simulador</h2>
            <p>
              El simulador procesa mensajes sin un número real cuando DRY_RUN
              está habilitado.
            </p>
            <form
              className="inline-form"
              onSubmit={(e) => {
                const f = form(e);
                run(async () => {
                  await api("simulate", f);
                  await refresh();
                });
              }}
            >
              <label>
                Destinatario
                <select name="phone">
                  {data.contacts
                    .filter((c) => c.active)
                    .map((c) => (
                      <option key={c.id} value={c.phone}>
                        {c.name}
                      </option>
                    ))}
                </select>
              </label>
              <label>
                Mensaje
                <input
                  name="text"
                  required
                  placeholder="SOPORTE Dream 11 fuga en campo"
                />
              </label>
              <button>Simular mensaje</button>
            </form>
            <div className="chat-log">
              {[...data.messages].reverse().map((m) => (
                <div key={m.id} className={"message " + m.direction}>
                  <small>
                    {m.phone} · {m.direction === "in" ? "Usuario" : "RiegoBot"}{" "}
                    · {fmt(m.created_at)} · {m.delivery_status}
                  </small>
                  <p>{m.body}</p>
                </div>
              ))}
            </div>
          </section>
        )}
        {tab === "Indicadores" && (
          <>
            <div className="stats">
              <Stat
                label="Casos registrados"
                value={statValue(data.incidents.length)}
              />
              <Stat
                label="Casos cerrados"
                value={statValue(
                  data.incidents.filter((i) => i.resolved_at).length,
                )}
              />
              <Stat
                label="Con evidencia por validar"
                value={statValue(
                  pending.filter((i) => i.status === "pending_review").length,
                )}
              />
              <Stat
                label="Mensajes recientes"
                value={statValue(data.messages.length)}
              />
            </div>
            <section>
              <h2>Tiempos de atención</h2>
              <p>
                Sobre las últimas 200 incidencias. Comparar con la línea base
                del piloto.
              </p>
              <div className="stats">
                <Stat
                  label="Recepción promedio (min)"
                  value={statValue(average(data.incidents, "ack_at"))}
                />
                <Stat
                  label="Resolución promedio (min)"
                  value={statValue(average(data.incidents, "resolved_at"))}
                />
              </div>
              <button
                className="secondary"
                onClick={() => {
                  const blob = new Blob(
                    [JSON.stringify(data.incidents, null, 2)],
                    { type: "application/json" },
                  );
                  const a = document.createElement("a");
                  a.href = URL.createObjectURL(blob);
                  a.download = "incidencias.json";
                  a.click();
                  URL.revokeObjectURL(a.href);
                }}
              >
                Exportar incidencias
              </button>
            </section>
          </>
        )}
      </main>
      {detail && (
        <div className="overlay">
          <section
            className="drawer"
            role="dialog"
            aria-modal="true"
            aria-label="Detalle de incidencia"
          >
            <button className="close secondary" onClick={() => setDetail(null)}>
              Cerrar ×
            </button>
            <span className="eyebrow">INCIDENCIA #{detail.incident.id}</span>
            <h2>{detail.incident.title}</h2>
            <Badge status={detail.incident.status} />
            <p>
              Dream {detail.incident.dream_id ?? "—"} · Nivel{" "}
              {detail.incident.level + 1} · {fmt(detail.incident.created_at)}
            </p>
            <div className="actions">
              <button className="secondary" onClick={() => transition("ack")}>
                Recibido
              </button>
              <button onClick={() => transition("start")}>Atender</button>
              {detail.incident.status === "pending_review" && (
                <button onClick={() => transition("approve")}>
                  Aprobar cierre
                </button>
              )}
            </div>
            <form
              onSubmit={(e) => {
                const f = form(e);
                run(async () => {
                  await api("assign", {
                    incident_id: detail.incident.id,
                    contact_id: f.contact,
                  });
                  await openDetail(detail.incident.id);
                });
              }}
            >
              <label>
                Asignar responsable
                <select name="contact">
                  {data.contacts
                    .filter((c) => c.active)
                    .map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name}
                      </option>
                    ))}
                </select>
              </label>
              <button className="secondary">Asignar</button>
            </form>
            <h3>Evidencias</h3>
            <input
              aria-label="Adjuntar foto"
              type="file"
              accept="image/jpeg,image/png,image/webp"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file)
                  run(async () => {
                    if (file.size > 10 * 1024 * 1024)
                      throw Error("Máximo 10 MB");
                    const base64 = await new Promise<string>(
                      (resolve, reject) => {
                        const reader = new FileReader();
                        reader.onload = () =>
                          resolve(String(reader.result).split(",")[1]);
                        reader.onerror = reject;
                        reader.readAsDataURL(file);
                      },
                    );
                    await api("evidence", {
                      incident_id: detail.incident.id,
                      base64,
                      mime: file.type,
                    });
                    await openDetail(detail.incident.id);
                  });
              }}
            />
            <div className="photos">
              {detail.evidence.map((e: any) => (
                <a key={e.id} href={e.url} target="_blank" rel="noreferrer">
                  <img
                    src={e.url}
                    alt={e.caption || "Evidencia de subsanación"}
                  />
                </a>
              ))}
            </div>
            <form
              onSubmit={(e) => {
                const f = form(e);
                transition(
                  detail.incident.status === "resolved" ? "reopen" : "submit",
                  String(f.note),
                );
              }}
            >
              <label>
                {detail.incident.status === "resolved"
                  ? "Motivo de reapertura"
                  : "Descripción de subsanación"}
                <textarea
                  name="note"
                  minLength={8}
                  required
                  defaultValue={detail.incident.resolution ?? ""}
                />
              </label>
              <button disabled={busy}>
                {detail.incident.status === "resolved"
                  ? "Reabrir"
                  : "Enviar subsanación"}
              </button>
            </form>
            <form
              onSubmit={(e) => {
                const f = form(e);
                run(async () => {
                  await api("reply", {
                    incident_id: detail.incident.id,
                    text: f.text,
                  });
                  await refresh();
                });
              }}
            >
              <label>
                Respuesta al usuario
                <textarea name="text" required />
              </label>
              <button className="secondary">Enviar a la cola</button>
            </form>
            <h3>Historial</h3>
            <ol className="timeline">
              {detail.events.map((e: any) => (
                <li key={e.id}>
                  <strong>{e.action}</strong>
                  <small>
                    {fmt(e.created_at)} · {e.actor}
                  </small>
                  <p>{e.body}</p>
                </li>
              ))}
            </ol>
          </section>
        </div>
      )}
      {rule && (
        <div className="overlay">
          <section
            className="drawer"
            role="dialog"
            aria-modal="true"
            aria-label="Configurar regla"
          >
            <button className="close secondary" onClick={() => setRule(null)}>
              Cerrar ×
            </button>
            <h2>Configurar clase de alerta</h2>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                run(async () => {
                  await api("rule", { rule });
                  if (requests.current.isCurrent(scope)) setRule(null);
                  await refresh();
                });
              }}
            >
              {["name", "entity", "field"].map((k) => (
                <label key={k}>
                  {
                    (
                      {
                        name: "Nombre de la clase",
                        entity: "Tabla / entidad",
                        field: "Campo",
                      } as any
                    )[k]
                  }
                  <input
                    required
                    value={rule[k]}
                    onChange={(e) => setRule({ ...rule, [k]: e.target.value })}
                  />
                </label>
              ))}
              <div className="two">
                <label>
                  Tipo
                  <select
                    value={rule.kind}
                    onChange={(e) => setRule({ ...rule, kind: e.target.value })}
                  >
                    <option value="event">Evento</option>
                    <option value="threshold">Umbral</option>
                    <option value="support">Solicitud de soporte</option>
                  </select>
                </label>
                <label>
                  Condición
                  <select
                    value={rule.operator}
                    onChange={(e) =>
                      setRule({ ...rule, operator: e.target.value })
                    }
                  >
                    <option value="eq">Igual a</option>
                    <option value="gt">Mayor que</option>
                    <option value="lt">Menor que</option>
                  </select>
                </label>
                <label>
                  Valor
                  <input
                    type="number"
                    step="any"
                    required
                    value={rule.value}
                    onChange={(e) =>
                      setRule({ ...rule, value: Number(e.target.value) })
                    }
                  />
                </label>
                <label>
                  Dream
                  <select
                    value={rule.dream_id ?? ""}
                    onChange={(e) =>
                      setRule({ ...rule, dream_id: e.target.value || null })
                    }
                  >
                    <option value="">Todos</option>
                    {data.dreams.map((d) => (
                      <option key={d.dream_id} value={d.dream_id}>
                        {d.name}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Prioridad
                  <select
                    value={rule.severity}
                    onChange={(e) =>
                      setRule({ ...rule, severity: e.target.value })
                    }
                  >
                    {["baja", "media", "alta", "critica"].map((s) => (
                      <option key={s}>{s}</option>
                    ))}
                  </select>
                </label>
              </div>
              <h3>Plazos en minutos</h3>
              <div className="two">
                {Object.entries({
                  ack_minutes: "Confirmar recepción",
                  resolve_minutes: "Subsanar tras recepción",
                  reminder_minutes: "Reenviar cada",
                  stale_minutes: "Antigüedad máxima del dato",
                }).map(([k, v]) => (
                  <label key={k}>
                    {v}
                    <input
                      type="number"
                      min={1}
                      required
                      value={rule[k]}
                      onChange={(e) =>
                        setRule({ ...rule, [k]: Number(e.target.value) })
                      }
                    />
                  </label>
                ))}
              </div>
              {Object.entries({
                enabled: "Regla activa",
                photo_required: "Foto obligatoria",
                approval_required: "Supervisor valida el cierre",
              }).map(([k, v]) => (
                <label className="check" key={k}>
                  <input
                    type="checkbox"
                    checked={rule[k]}
                    onChange={(e) =>
                      setRule({ ...rule, [k]: e.target.checked })
                    }
                  />
                  {v}
                </label>
              ))}
              <h3>Cadena de escalamiento</h3>
              {rule.levels.map((l: any, n: number) => (
                <fieldset key={n}>
                  <legend>Nivel {n + 1}</legend>
                  <label>
                    Área / rol
                    <input
                      required
                      value={l.name}
                      onChange={(e) =>
                        setRule({
                          ...rule,
                          levels: rule.levels.map((x: any, i: number) =>
                            i === n ? { ...x, name: e.target.value } : x,
                          ),
                        })
                      }
                    />
                  </label>
                  <label>
                    Minutos hasta siguiente nivel
                    <input
                      type="number"
                      min={1}
                      value={l.after_minutes}
                      onChange={(e) =>
                        setRule({
                          ...rule,
                          levels: rule.levels.map((x: any, i: number) =>
                            i === n
                              ? { ...x, after_minutes: Number(e.target.value) }
                              : x,
                          ),
                        })
                      }
                    />
                  </label>
                  {data.contacts
                    .filter((c) => c.active)
                    .map((c) => (
                      <label className="check" key={c.id}>
                        <input
                          type="checkbox"
                          checked={l.contacts.includes(c.id)}
                          onChange={(e) =>
                            setRule({
                              ...rule,
                              levels: rule.levels.map((x: any, i: number) =>
                                i === n
                                  ? {
                                      ...x,
                                      contacts: e.target.checked
                                        ? [...x.contacts, c.id]
                                        : x.contacts.filter(
                                            (id: string) => id !== c.id,
                                          ),
                                    }
                                  : x,
                              ),
                            })
                          }
                        />
                        {c.name} · {c.role}
                      </label>
                    ))}
                  {n > 0 && (
                    <button
                      type="button"
                      className="link"
                      onClick={() =>
                        setRule({
                          ...rule,
                          levels: rule.levels.filter(
                            (_: any, i: number) => i !== n,
                          ),
                        })
                      }
                    >
                      Quitar nivel
                    </button>
                  )}
                </fieldset>
              ))}
              <button
                type="button"
                className="secondary"
                onClick={() =>
                  setRule({
                    ...rule,
                    levels: [
                      ...rule.levels,
                      { name: "Supervisor", after_minutes: 60, contacts: [] },
                    ],
                  })
                }
              >
                Añadir nivel
              </button>
              <button disabled={busy}>Guardar configuración</button>
            </form>
          </section>
        </div>
      )}
    </div>
  );
}
function Brand() {
  return (
    <div className="brand">
      <span>R</span>RiegoBot<small>OPERACIONES</small>
    </div>
  );
}
function Stat({ label, value }: { label: string; value: any }) {
  return (
    <div className="stat">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}
function Badge({ status }: { status: string }) {
  return (
    <span className={"badge " + status}>{statuses[status] ?? status}</span>
  );
}
function Empty({ text }: { text: string }) {
  return (
    <div className="empty">
      <span>◎</span>
      <p>{text}</p>
    </div>
  );
}
function average(rows: any[], field: string) {
  const a = rows.filter((x) => x[field]);
  return a.length
    ? Math.round(
        a.reduce(
          (n, x) =>
            n + (Date.parse(x[field]) - Date.parse(x.created_at)) / 60000,
          0,
        ) / a.length,
      )
    : "—";
}
createRoot(document.getElementById("root")!).render(<App />);
