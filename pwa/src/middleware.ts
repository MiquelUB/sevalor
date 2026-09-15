import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl
  const token = request.cookies.get('sevalor_access_token')

  // Proteger rutas /gestio (excepto login)
  if (pathname.startsWith('/gestio') && !pathname.includes('/login')) {
    if (!token) {
      return NextResponse.redirect(new URL('/gestio/login', request.url))
    }
  }

  // Proteger rutas /superadmin (excepto login)
  if (pathname.startsWith('/superadmin') && !pathname.includes('/login')) {
    if (!token) {
      return NextResponse.redirect(new URL('/superadmin/login', request.url))
    }
  }

  // Proteger rutas /operari (excepto login)
  if (pathname.startsWith('/operari') && !pathname.includes('/login')) {
    if (!token) {
      return NextResponse.redirect(new URL('/operari/login', request.url))
    }
  }

  return NextResponse.next()
}

export const config = {
  matcher: ['/gestio/:path*', '/superadmin/:path*', '/operari/:path*'],
}