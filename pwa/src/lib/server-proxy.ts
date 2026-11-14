import { NextRequest } from "next/server";

let cachedBackendRoot: string | null = null;

function normalizeBackendRoot(raw: string | undefined | null): string | null {
  if (!raw) return null;
  const trimmed = raw.trim().replace(/\/+$/, "");
  if (!trimmed.startsWith("http://") && !trimmed.startsWith("https://")) {
    return null;
  }
  return trimmed.replace(/\/api\/v1$/, "");
}

function getCandidateBackendRoots(): string[] {
  const candidates: string[] = [];
  const addCandidate = (url: string | undefined | null) => {
    const norm = normalizeBackendRoot(url);
    if (norm && !candidates.includes(norm)) {
      candidates.push(norm);
    }
  };

  if (cachedBackendRoot) {
    addCandidate(cachedBackendRoot);
  }

  // 1. Variables d'entorn explícites d'infraestructura interna
  addCandidate(process.env.INTERNAL_API_URL);
  addCandidate(process.env.INTERNAL_BACKEND_URL);
  addCandidate(process.env.BACKEND_URL);

  // 2. Noms de servei interns Docker Swarm (EasyPanel) i Docker Compose
  addCandidate("http://sevalor_sevalor-backend:8000");
  addCandidate("http://sevalor-backend:8000");
  addCandidate("http://sevalor_backend:8000");
  addCandidate("http://backend:8000");

  // 3. Variable pública configurada a EasyPanel / Dockerfile
  addCandidate(process.env.NEXT_PUBLIC_API_URL);
  addCandidate("https://sevalor-sevalor-backend.80opze.easypanel.host");

  // 4. Fallbacks per a desenvolupament local
  addCandidate("http://127.0.0.1:8000");
  addCandidate("http://127.0.0.1:8001");

  return candidates;
}

function buildForwardHeaders(request: NextRequest): Headers {
  const headers = new Headers();
  const hopByHop = new Set([
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
    "host",
    "content-length",
  ]);

  request.headers.forEach((value, key) => {
    if (!hopByHop.has(key.toLowerCase())) {
      headers.set(key, value);
    }
  });

  const originalHost =
    request.headers.get("x-forwarded-host") ||
    request.headers.get("host") ||
    request.nextUrl.host ||
    "";
  if (originalHost) {
    headers.set("x-forwarded-host", originalHost);
  }

  const forwardedProto =
    request.headers.get("x-forwarded-proto") ||
    request.nextUrl.protocol.replace(":", "") ||
    "https";
  headers.set("x-forwarded-proto", forwardedProto);

  return headers;
}

function buildResponseHeaders(upstreamHeaders: Headers): Headers {
  const responseHeaders = new Headers();
  const excluded = new Set([
    "connection",
    "keep-alive",
    "transfer-encoding",
    "content-encoding",
    "content-length",
  ]);

  upstreamHeaders.forEach((value, key) => {
    if (!excluded.has(key.toLowerCase())) {
      responseHeaders.append(key, value);
    }
  });

  return responseHeaders;
}

export async function proxyToBackend(
  request: NextRequest,
  prefix: string,
  pathSegments?: string[]
): Promise<Response> {
  const cleanPrefix = prefix.replace(/^\/+|\/+$/g, "");
  const joinedPath = (pathSegments || []).join("/");
  const targetPath = joinedPath ? `/${cleanPrefix}/${joinedPath}` : `/${cleanPrefix}`;
  const search = request.nextUrl.search || "";

  const method = request.method.toUpperCase();
  const hasBody = method !== "GET" && method !== "HEAD" && method !== "OPTIONS";
  const bodyBuffer = hasBody ? await request.arrayBuffer() : undefined;
  const forwardHeaders = buildForwardHeaders(request);

  const candidates = getCandidateBackendRoots();
  let lastUpstreamResponse: Response | null = null;
  let lastError: unknown = null;

  for (const baseRoot of candidates) {
    const targetUrl = `${baseRoot}${targetPath}${search}`;
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 15000);

      let upstreamRes: Response;
      try {
        upstreamRes = await fetch(targetUrl, {
          method,
          headers: forwardHeaders,
          body: bodyBuffer ? bodyBuffer.slice(0) : undefined,
          redirect: "manual",
          signal: controller.signal,
          cache: "no-store",
        });

        // Seguir redireccions internes 307/308 (ex. trailing slash de FastAPI) preservant Authorization i body
        if (upstreamRes.status === 307 || upstreamRes.status === 308) {
          const location = upstreamRes.headers.get("location");
          if (location) {
            const parsedLoc = new URL(location, baseRoot);
            const redirectTarget = `${baseRoot}${parsedLoc.pathname}${parsedLoc.search}`;
            upstreamRes = await fetch(redirectTarget, {
              method,
              headers: forwardHeaders,
              body: bodyBuffer ? bodyBuffer.slice(0) : undefined,
              redirect: "manual",
              signal: controller.signal,
              cache: "no-store",
            });
          }
        }
      } finally {
        clearTimeout(timeoutId);
      }

      // Si l'upstream respon amb 502, 503 o 504 (ex. Traefik Bad Gateway), provar el següent candidat
      if ([502, 503, 504].includes(upstreamRes.status)) {
        if (cachedBackendRoot === baseRoot) {
          cachedBackendRoot = null;
        }
        lastUpstreamResponse = upstreamRes;
        continue;
      }

      cachedBackendRoot = baseRoot;
      const resBody = method === "HEAD" ? null : await upstreamRes.arrayBuffer();
      return new Response(resBody, {
        status: upstreamRes.status,
        statusText: upstreamRes.statusText,
        headers: buildResponseHeaders(upstreamRes.headers),
      });
    } catch (err) {
      if (cachedBackendRoot === baseRoot) {
        cachedBackendRoot = null;
      }
      lastError = err;
      continue;
    }
  }

  if (lastUpstreamResponse) {
    const resBody = method === "HEAD" ? null : await lastUpstreamResponse.arrayBuffer();
    return new Response(resBody, {
      status: lastUpstreamResponse.status,
      statusText: lastUpstreamResponse.statusText,
      headers: buildResponseHeaders(lastUpstreamResponse.headers),
    });
  }

  return Response.json(
    {
      detail: "El servidor backend no està disponible temporalment.",
      code: "BACKEND_UNREACHABLE",
      error: lastError instanceof Error ? lastError.message : String(lastError || ""),
    },
    { status: 503 }
  );
}
