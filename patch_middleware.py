import re

with open("pwa/src/middleware.ts", "r") as f:
    content = f.read()

# Remove the cookie clearing from middleware
old_block = """  const createRedirectWithClearedCookie = (targetUrl: string) => {
    const response = NextResponse.redirect(new URL(targetUrl, request.url));
    if (tokenCookie) {
      response.cookies.delete('sevalor_access_token');
    }
    return response;
  };"""

new_block = """  const createRedirectWithClearedCookie = (targetUrl: string) => {
    // We don't clear the cookie here to avoid false negative logouts
    return NextResponse.redirect(new URL(targetUrl, request.url));
  };"""

content = content.replace(old_block, new_block)

with open("pwa/src/middleware.ts", "w") as f:
    f.write(content)

print("Middleware patched.")
