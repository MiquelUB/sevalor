import { NextRequest } from "next/server";
import { proxyToBackend } from "@/lib/server-proxy";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type RouteContext = {
  params: { path?: string[] };
};

export async function GET(request: NextRequest, context: RouteContext) {
  return proxyToBackend(request, "api/v1", context.params?.path);
}

export async function POST(request: NextRequest, context: RouteContext) {
  return proxyToBackend(request, "api/v1", context.params?.path);
}

export async function PUT(request: NextRequest, context: RouteContext) {
  return proxyToBackend(request, "api/v1", context.params?.path);
}

export async function PATCH(request: NextRequest, context: RouteContext) {
  return proxyToBackend(request, "api/v1", context.params?.path);
}

export async function DELETE(request: NextRequest, context: RouteContext) {
  return proxyToBackend(request, "api/v1", context.params?.path);
}

export async function HEAD(request: NextRequest, context: RouteContext) {
  return proxyToBackend(request, "api/v1", context.params?.path);
}

export async function OPTIONS(request: NextRequest, context: RouteContext) {
  return proxyToBackend(request, "api/v1", context.params?.path);
}
