import {
  db,
  json,
  error,
  must,
  signature,
  boundedBytes,
  PayloadTooLargeError,
} from "../_shared/common.ts";
Deno.serve(async (req) => {
  if (req.method === "GET") {
    const u = new URL(req.url);
    const token = Deno.env.get("WHATSAPP_VERIFY_TOKEN");
    return token &&
      u.searchParams.get("hub.mode") === "subscribe" &&
      u.searchParams.get("hub.verify_token") === token
      ? new Response(u.searchParams.get("hub.challenge"))
      : new Response("Forbidden", { status: 403 });
  }
  if (req.method !== "POST")
    return new Response("Method not allowed", { status: 405 });
  try {
    const raw = new TextDecoder().decode(await boundedBytes(req, 1_000_000));
    if (!(await signature(raw, req.headers.get("x-hub-signature-256"))))
      return json({ error: "Firma inválida" }, 401);
    const body = JSON.parse(raw);
    for (const entry of body.entry ?? [])
      for (const change of entry.changes ?? []) {
        const value = change.value;
        if (
          value?.metadata?.phone_number_id !==
          Deno.env.get("WHATSAPP_PHONE_NUMBER_ID")
        )
          continue;
        for (const message of value.messages ?? [])
          must(
            await db().rpc("enqueue", {
              k: "inbound",
              d: "in:" + message.id,
              p: message,
            }),
          );
        for (const status of value.statuses ?? [])
          must(
            await db()
              .from("messages")
              .update({ delivery_status: status.status })
              .eq("external_id", status.id)
              .eq("direction", "out"),
          );
      }
    return json({ received: true });
  } catch (e) {
    if (e instanceof PayloadTooLargeError) return error(e);
    console.error(e);
    return json({ error: "Persistencia fallida, reintentar" }, 503);
  }
});
