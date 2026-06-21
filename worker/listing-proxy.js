/**
 * Cloudflare Worker — CORS proxy for fetching rental-listing pages.
 *
 * The browser can't fetch arbitrary listing sites directly (CORS). This Worker
 * fetches the page server-side and returns the raw HTML with permissive CORS
 * headers, so berkeley-houses.html can parse Open Graph / JSON-LD client-side.
 *
 * Deploy (free, ~5 min):
 *   1. Create a free account at https://dash.cloudflare.com
 *   2. Workers & Pages → Create → Worker → name it e.g. "listing-proxy"
 *   3. Paste this file, Deploy.
 *   4. Copy the worker URL (https://listing-proxy.<you>.workers.dev) and set:
 *        const PROXY_URL = "https://listing-proxy.<you>.workers.dev/?url=";
 *      in berkeley-houses.html.
 *
 * Optional: lock it to your origin by setting ALLOWED to your site URL below.
 */
const ALLOWED = "*"; // e.g. "https://<you>.github.io"

export default {
  async fetch(request) {
    const cors = {
      "Access-Control-Allow-Origin": ALLOWED,
      "Access-Control-Allow-Methods": "GET, OPTIONS",
      "Access-Control-Allow-Headers": "*",
    };
    if (request.method === "OPTIONS") return new Response(null, { headers: cors });

    const target = new URL(request.url).searchParams.get("url");
    if (!target) return new Response("Missing ?url=", { status: 400, headers: cors });

    let parsed;
    try { parsed = new URL(target); } catch { return new Response("Bad url", { status: 400, headers: cors }); }
    if (!/^https?:$/.test(parsed.protocol)) return new Response("Only http(s)", { status: 400, headers: cors });

    try {
      const upstream = await fetch(parsed.toString(), {
        headers: {
          "User-Agent": "Mozilla/5.0 (compatible; berkeley-houses/1.0)",
          "Accept": "text/html,application/xhtml+xml",
        },
        redirect: "follow",
      });
      const body = await upstream.text();
      return new Response(body, {
        status: upstream.status,
        headers: { ...cors, "Content-Type": "text/html; charset=utf-8" },
      });
    } catch (e) {
      return new Response("Fetch error: " + e.message, { status: 502, headers: cors });
    }
  },
};
