import ast
import os
import glob

def parse_api():
    api_dir = "backend/app/api/v1/"
    md = "# API Specification\n\n"
    if not os.path.exists(api_dir):
        return "No API directory found."
    
    for root, dirs, files in os.walk(api_dir):
        for file in files:
            if file.endswith(".py") and file != "__init__.py":
                path = os.path.join(root, file)
                module = path.replace("backend/app/", "").replace(".py", "").replace("/", ".")
                
                with open(path, "r") as f:
                    try:
                        tree = ast.parse(f.read())
                    except:
                        continue
                
                endpoints = []
                for node in tree.body:
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        for decorator in node.decorator_list:
                            if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute):
                                if decorator.func.attr in ['get', 'post', 'put', 'delete', 'patch']:
                                    route = "Unknown"
                                    if decorator.args and isinstance(decorator.args[0], ast.Constant):
                                        route = decorator.args[0].value
                                    method = decorator.func.attr.upper()
                                    endpoints.append((method, route, node.name, ast.get_docstring(node)))
                
                if endpoints:
                    md += f"## {module}\n"
                    for method, route, name, doc in endpoints:
                        md += f"### {method} `{route}`\n"
                        md += f"**Function**: `{name}`\n\n"
                        if doc:
                            md += f"{doc}\n\n"
    return md

with open("sevalor_AgentV2/docs/sdd/api-spec.md", "w") as f:
    f.write(parse_api())

print("API spec generated.")
