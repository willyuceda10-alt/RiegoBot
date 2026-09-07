import { createClient } from "@supabase/supabase-js";
export const db = () =>
  createClient(
    Deno.env.get("SUPABASE_URL")!,
    Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
    { auth: { persistSession: false } },
  );
export function must<T>(r: { data: T; error: unknown }): NonNullable<T> {
  if (r.error) throw r.error;
  return r.data as NonNullable<T>;
}
export function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      "Content-Type": "application/json",
      "Access-Control-Allow-Origin":
        Deno.env.get("ALLOWED_ORIGIN") ?? "http://localhost:5173",
      "Access-Control-Allow-Headers":
        "authorization,apikey,content-type,x-collector-token,x-worker-secret",
      "Access-Control-Allow-Methods": "POST,OPTIONS",
    },
  });
}
export function error(e: unknown) {
  console.error(e);
  return json(
    { error: e instanceof Error ? e.message : "Operación rechazada" },
    e instanceof PayloadTooLargeError ? 413 : 400,
  );
}
export class PayloadTooLargeError extends Error {
  constructor() {
    super("Carga demasiado grande");
  }
}
// Check actual streamed bytes: Content-Length can be absent or untrusted.
export async function boundedBytes(
  source: Request | Response,
  limit: number,
): Promise<Uint8Array> {
  const reader = source.body?.getReader();
  if (!reader) return new Uint8Array();
  const chunks: Uint8Array[] = [];
  let size = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > limit) {
        await reader.cancel();
        throw new PayloadTooLargeError();
      }
      chunks.push(value);
    }
  } finally {
    reader.releaseLock();
  }
  const bytes = new Uint8Array(size);
  let offset = 0;
  for (const chunk of chunks) {
    bytes.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return bytes;
}
export async function boundedJson(req: Request, limit: number) {
  return JSON.parse(new TextDecoder().decode(await boundedBytes(req, limit)));
}
export async function sha(value: string) {
  return [
    ...new Uint8Array(
      await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value)),
    ),
  ]
    .map((v) => v.toString(16).padStart(2, "0"))
    .join("");
}
export async function signature(raw: string, header: string | null) {
  const secret = Deno.env.get("WHATSAPP_APP_SECRET");
  if (!secret || !header) return false;
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const bytes = new Uint8Array(
    await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(raw)),
  );
  const expected =
    "sha256=" + [...bytes].map((v) => v.toString(16).padStart(2, "0")).join("");
  if (expected.length !== header.length) return false;
  let diff = 0;
  for (let i = 0; i < header.length; i++)
    diff |= expected.charCodeAt(i) ^ header.charCodeAt(i);
  return diff === 0;
}
export async function staff(
  req: Request,
  site: string,
  roles = ["admin", "supervisor", "operator"],
) {
  const client = db();
  const token =
    req.headers.get("Authorization")?.replace(/^Bearer /i, "") ?? "";
  const auth = await client.auth.getUser(token);
  if (auth.error) throw auth.error;
  const user = auth.data.user;
  if (!user) throw Error("Inicia sesión");
  const membership = must(
    await client
      .from("memberships")
      .select("role")
      .eq("site_id", site)
      .eq("user_id", user.id)
      .single(),
  );
  if (!roles.includes(membership.role)) throw Error("No tienes permiso");
  return { id: user.id, role: membership.role };
}
export async function queue(
  phone: string,
  site: string,
  text: string,
  key: string,
  incident_id?: number,
) {
  must(
    await db().rpc("enqueue", {
      k: "outbound",
      d: key,
      p: { phone, site_id: site, text, incident_id },
    }),
  );
}
