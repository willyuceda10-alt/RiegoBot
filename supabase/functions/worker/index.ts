import { json, error } from "../_shared/common.ts";
import { work } from "../_shared/worker.ts";
Deno.serve(async (req) => {
  if (
    req.method !== "POST" ||
    !Deno.env.get("WORKER_SECRET") ||
    req.headers.get("x-worker-secret") !== Deno.env.get("WORKER_SECRET")
  )
    return json({ error: "Unauthorized" }, 401);
  try {
    return json(await work());
  } catch (e) {
    return error(e);
  }
});
