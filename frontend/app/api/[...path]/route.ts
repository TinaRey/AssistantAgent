import type { NextRequest } from "next/server";

/**
 * Same-origin proxy to the FastAPI backend (the browser never talks to it directly).
 * Configuration is read at runtime, not at build time:
 *   BACKEND_URL      e.g. https://pantalelle-api.onrender.com
 *   INTERNAL_API_KEY shared secret; the backend rejects /api calls that do not carry it.
 * This keeps the session cookie httpOnly + same-origin and lets the public backend refuse everyone else.
 */
export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const FORWARDED_REQUEST_HEADERS = ["content-type", "cookie", "accept", "accept-language", "user-agent"];
// fetch() already decoded the body, so encoding/length headers no longer describe it.
const DROPPED_RESPONSE_HEADERS = new Set([
  "content-encoding", "content-length", "transfer-encoding", "connection", "keep-alive", "set-cookie",
]);
const TIMEOUT_MS = 5 * 60 * 1000; // the slowest tool (research, presentation) can take minutes

function clientIp(req: NextRequest): string {
  const forwarded = req.headers.get("x-forwarded-for");
  return (forwarded?.split(",")[0] ?? "").trim() || req.headers.get("x-real-ip") || "";
}

async function proxy(req: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const backend = process.env.BACKEND_URL || (process.env.NODE_ENV === "production" ? "" : "http://localhost:8000");
  if (!backend) return Response.json({ detail: "BACKEND_URL n'est pas configuré." }, { status: 500 });

  const { path } = await params;
  if (path.some((segment) => segment === "." || segment === "..")) {
    return Response.json({ detail: "Chemin invalide." }, { status: 400 });
  }
  const url = new URL(`/api/${path.map(encodeURIComponent).join("/")}`, backend);
  url.search = req.nextUrl.search;

  const headers = new Headers();
  for (const name of FORWARDED_REQUEST_HEADERS) {
    const value = req.headers.get(name);
    if (value) headers.set(name, value);
  }
  if (process.env.INTERNAL_API_KEY) headers.set("x-internal-key", process.env.INTERNAL_API_KEY);
  const ip = clientIp(req);
  if (ip) headers.set("x-client-ip", ip);

  const hasBody = req.method !== "GET" && req.method !== "HEAD";
  let upstream: Response;
  try {
    upstream = await fetch(url, {
      method: req.method, headers, redirect: "manual", cache: "no-store",
      signal: AbortSignal.timeout(TIMEOUT_MS),
      ...(hasBody ? { body: req.body, duplex: "half" } : {}),
    } as RequestInit);
  } catch {
    return Response.json({ detail: "Le service est momentanément indisponible." }, { status: 502 });
  }

  const out = new Headers();
  upstream.headers.forEach((value, name) => {
    if (!DROPPED_RESPONSE_HEADERS.has(name.toLowerCase())) out.set(name, value);
  });
  for (const cookie of upstream.headers.getSetCookie()) out.append("set-cookie", cookie);
  return new Response(upstream.body, { status: upstream.status, headers: out });
}

export { proxy as GET, proxy as POST, proxy as PUT, proxy as DELETE, proxy as PATCH };
