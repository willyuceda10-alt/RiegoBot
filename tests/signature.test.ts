import { signature } from "../supabase/functions/_shared/common.ts";
Deno.test(
  "Webhook validates exact signed bytes and rejects tampering",
  async () => {
    Deno.env.set("WHATSAPP_APP_SECRET", "local-test-secret");
    const raw = '{"entry":[]}';
    const key = await crypto.subtle.importKey(
      "raw",
      new TextEncoder().encode("local-test-secret"),
      { name: "HMAC", hash: "SHA-256" },
      false,
      ["sign"],
    );
    const signed = new Uint8Array(
      await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(raw)),
    );
    const header =
      "sha256=" +
      [...signed].map((v) => v.toString(16).padStart(2, "0")).join("");
    if (!(await signature(raw, header)))
      throw Error("Valid signature rejected");
    if (await signature(raw + " ", header))
      throw Error("Tampered body accepted");
    if (await signature(raw, null)) throw Error("Unsigned payload accepted");
  },
);
