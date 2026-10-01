from fastapi.testclient import TestClient
from app.main import app

for route in app.routes:
    if hasattr(route, "methods"):
        print(route.path, route.methods)

from starlette.routing import Mount
def print_tree(routes, prefix=""):
    for r in routes:
        if isinstance(r, Mount):
            print_tree(r.routes, prefix + r.path)
        elif hasattr(r, "path"):
            print(prefix + r.path, r.methods)
print_tree(app.router.routes)
