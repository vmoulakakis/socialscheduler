import "jsr:@supabase/functions-js/edge-runtime.d.ts";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL") ?? "";
const SERVICE_ROLE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json", "cache-control": "no-store" },
  });
}

Deno.serve(async (req: Request) => {
  if (req.method !== "POST") return json({ error: "method_not_allowed" }, 405);

  const runtimeResponse = await fetch(`${SUPABASE_URL}/rest/v1/rpc/socialscheduler_provider_edge_runtime`, {
    method: "POST",
    headers: {
      apikey: SERVICE_ROLE_KEY,
      authorization: `Bearer ${SERVICE_ROLE_KEY}`,
      "content-type": "application/json",
    },
    body: JSON.stringify({ p_provider_key: "brightbean" }),
  });
  if (!runtimeResponse.ok) return json({ error: "runtime_config_unavailable" }, 503);
  const runtime = await runtimeResponse.json();
  if (!runtime?.api_key || req.headers.get("x-autopilot-key") !== runtime.worker_key) {
    return json({ error: "unauthorized" }, 401);
  }

  const payload = await req.json();
  const required = ["job_id", "account_id", "caption", "media_url", "scheduled_at"];
  if (required.some((key) => typeof payload[key] !== "string" || !payload[key])) {
    return json({ error: "invalid_payload" }, 422);
  }

  try {
    const mediaResponse = await fetch(payload.media_url);
    if (!mediaResponse.ok) return json({ error: "media_download_failed", status: mediaResponse.status }, 422);
    const mediaBlob = await mediaResponse.blob();
    if (!mediaBlob.type.startsWith("image/") || mediaBlob.size > 25 * 1024 * 1024) {
      return json({ error: "invalid_media" }, 422);
    }

    const mediaKey = `socialscheduler-media-${payload.job_id}`;
    const form = new FormData();
    form.append("idempotency_key", mediaKey);
    form.append("file", mediaBlob, `${payload.job_id}.png`);
    const upload = await fetch(`${runtime.api_url}/media/`, {
      method: "POST",
      headers: {
        authorization: `Bearer ${runtime.api_key}`,
        "Idempotency-Key": mediaKey,
      },
      body: form,
    });
    const uploadBody = await upload.json().catch(() => ({}));
    if (!upload.ok || !uploadBody.id) {
      return json({ error: "media_upload_failed", status: upload.status, detail: uploadBody }, 502);
    }

    const postKey = `socialscheduler-${payload.job_id}-${payload.account_id}`;
    const create = await fetch(`${runtime.api_url}/posts/`, {
      method: "POST",
      headers: {
        authorization: `Bearer ${runtime.api_key}`,
        "content-type": "application/json",
        "Idempotency-Key": postKey,
      },
      body: JSON.stringify({
        social_account_id: payload.account_id,
        caption: payload.caption,
        title: "",
        media_asset_ids: [uploadBody.id],
        action: "schedule",
        scheduled_at: payload.scheduled_at,
        idempotency_key: postKey,
      }),
    });
    const postBody = await create.json().catch(() => ({}));
    if (!create.ok) return json({ error: "post_create_failed", status: create.status, detail: postBody }, 502);

    return json({
      provider: "brightbean",
      status: postBody.status,
      post_id: postBody.id,
      platform_posts: postBody.platform_posts ?? [],
      scheduled_at: postBody.scheduled_at,
      media_id: uploadBody.id,
    }, 201);
  } catch (error) {
    return json({ error: "dispatch_failed", detail: String(error).slice(0, 500) }, 502);
  }
});

