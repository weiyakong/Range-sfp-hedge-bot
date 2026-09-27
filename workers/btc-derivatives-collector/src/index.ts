import { runScheduledCollection } from "./collector";
import { Env } from "./types";

export default {
  async fetch(
    request: Request,
    env: Env,
    ctx: ExecutionContext
  ): Promise<Response> {
    const url = new URL(request.url);

    // Cheap health endpoint: strictly GET /health only. NO discovery, NO API calls, NO D1 writes
    if (url.pathname === "/health") {
      if (request.method !== "GET") {
        return new Response("Method Not Allowed", { status: 405 });
      }
      return Response.json({
        status: "healthy",
        service: "btc-derivatives-collector",
        timestamp_utc: Math.floor(Date.now() / 1000),
      });
    }

    return new Response("Not Found", { status: 404 });
  },

  async scheduled(
    _event: ScheduledEvent,
    env: Env,
    ctx: ExecutionContext
  ): Promise<void> {
    ctx.waitUntil(
      runScheduledCollection(env).then((run) => {
        console.log(
          `[Scheduled Collection] runId=${run.run_id} status=${run.status} rows=${run.rows_inserted}`
        );
      })
    );
  },
};
