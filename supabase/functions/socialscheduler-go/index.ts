import "jsr:@supabase/functions-js/edge-runtime.d.ts";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL") ?? "";
const SERVICE_ROLE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
const ALLOWED_SEED = /^[a-z0-9][a-z0-9-]{1,63}$/;

function response(body: string, status: number): Response {
  return new Response(body, {
    status,
    headers: {
      "content-type": "text/plain; charset=utf-8",
      "cache-control": "no-store, max-age=0",
      "referrer-policy": "no-referrer",
      "x-content-type-options": "nosniff",
    },
  });
}

Deno.serve(async (req: Request) => {
  if (req.method !== "GET" && req.method !== "HEAD") {
    return response("Method not allowed", 405);
  }

  const url = new URL(req.url);
  const seedKey = url.pathname.split("/").filter(Boolean).at(-1) ?? "";
  if (!ALLOWED_SEED.test(seedKey) || seedKey === "socialscheduler-go") {
    return response("Affiliate link not found", 404);
  }

  const platform = (url.searchParams.get("p") ?? "unknown").toLowerCase();
  const campaign = url.searchParams.get("c") ?? "";

  try {
    const rpc = await fetch(`${SUPABASE_URL}/rest/v1/rpc/socialscheduler_track_affiliate_click`, {
      method: "POST",
      headers: {
        apikey: SERVICE_ROLE_KEY,
        authorization: `Bearer ${SERVICE_ROLE_KEY}`,
        "content-type": "application/json",
      },
      body: JSON.stringify({
        p_seed_key: seedKey,
        p_platform: platform,
        p_campaign: campaign,
        p_user_agent: req.headers.get("user-agent") ?? "",
      }),
    });

    if (!rpc.ok) {
      return response("Affiliate link temporarily unavailable", 503);
    }

    const destination = await rpc.json();
    if (typeof destination !== "string" || !destination.startsWith("https://go.linkwi.se/")) {
      return response("Affiliate link not found", 404);
    }

    return new Response(null, {
      status: 302,
      headers: {
        location: destination,
        "cache-control": "no-store, max-age=0",
        "referrer-policy": "no-referrer",
        "x-content-type-options": "nosniff",
      },
    });
  } catch {
    return response("Affiliate link temporarily unavailable", 503);
  }
});

