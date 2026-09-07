import {
  boundedBytes,
  PayloadTooLargeError,
} from "../supabase/functions/_shared/common.ts";
import { work } from "../supabase/functions/_shared/worker.ts";

function assert(condition: unknown, message: string): asserts condition {
  if (!condition) throw Error(message);
}

Deno.test(
  "Body limit counts streamed bytes and cancels oversized input",
  async () => {
    let cancelled = false;
    const stream = new ReadableStream<Uint8Array>({
      pull(controller) {
        controller.enqueue(new Uint8Array(4));
      },
      cancel() {
        cancelled = true;
      },
    });
    try {
      await boundedBytes(new Response(stream), 7);
      throw Error("Oversized stream accepted");
    } catch (e) {
      assert(
        e instanceof PayloadTooLargeError,
        "Must reject at the byte limit",
      );
      assert(cancelled, "Must stop reading oversized bodies");
    }
    const bytes = await boundedBytes(new Response("á"), 2);
    assert(bytes.length === 2, "Limit is UTF-8 bytes, not string characters");
  },
);

Deno.test(
  "An accepted Meta send with truncated JSON is uncertain and never automatically retried",
  async () => {
    const originalFetch = globalThis.fetch;
    const saved = new Map<string, string | undefined>();
    for (const [key, value] of Object.entries({
      SUPABASE_URL: "https://local-db.test",
      SUPABASE_SERVICE_ROLE_KEY: "local-test-key",
      DRY_RUN: "false",
      WHATSAPP_TOKEN: "local-test-token",
      WHATSAPP_PHONE_NUMBER_ID: "local-test-phone",
      WHATSAPP_ALERT_TEMPLATE: "test_template",
    })) {
      saved.set(key, Deno.env.get(key));
      Deno.env.set(key, value);
    }
    const updates: any[] = [];
    let metaSends = 0;
    globalThis.fetch = (async (
      input: RequestInfo | URL,
      init?: RequestInit,
    ) => {
      const url = new URL(input instanceof Request ? input.url : String(input));
      const reply = (value: unknown) =>
        new Response(JSON.stringify(value), {
          headers: { "Content-Type": "application/json" },
        });
      if (url.hostname === "graph.facebook.com") {
        metaSends++;
        return new Response('{"messages":[', { status: 200 });
      }
      if (url.pathname.endsWith("/rpc/tick_incidents")) return reply(0);
      if (url.pathname.endsWith("/rpc/claim_jobs"))
        return reply([
          {
            id: 1,
            kind: "outbound",
            lease_id: "lease-test",
            attempts: 1,
            payload: {
              site_id: "site-test",
              phone: "51911111111",
              text: "Test",
            },
          },
        ]);
      if (url.pathname.endsWith("/contacts"))
        return reply({ id: "contact-test" });
      if (url.pathname.endsWith("/conversations")) return reply(null);
      if (url.pathname.endsWith("/jobs") && init?.method === "PATCH") {
        updates.push(JSON.parse(String(init.body)));
        return new Response(null, { status: 204 });
      }
      throw Error("Unexpected request: " + url.pathname);
    }) as typeof fetch;
    try {
      await work();
      assert(metaSends === 1, "Expected exactly one mocked send");
      assert(
        updates.length === 1 && updates[0].status === "uncertain",
        "Ambiguous result must require reconciliation instead of pending retry",
      );
    } finally {
      globalThis.fetch = originalFetch;
      for (const [key, value] of saved) {
        if (value === undefined) Deno.env.delete(key);
        else Deno.env.set(key, value);
      }
    }
  },
);
