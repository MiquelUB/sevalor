import ast
import os

def parse_models():
    model_file = "backend/app/models/models.py"
    if not os.path.exists(model_file):
        return "No models.py found."
    
    with open(model_file, "r") as f:
        tree = ast.parse(f.read())
        
    classes = [node for node in tree.body if isinstance(node, ast.ClassDef)]
    
    md = "# Data Model Schema\n\n"
    for c in classes:
        md += f"## {c.name}\n"
        has_fields = False
        for node in c.body:
            if isinstance(node, ast.AnnAssign):
                target = node.target.id if isinstance(node.target, ast.Name) else str(node.target)
                annotation = ast.unparse(node.annotation)
                md += f"- `{target}`: `{annotation}`\n"
                has_fields = True
            elif isinstance(node, ast.Assign):
                # sometimes fields are assigned without annotation in old SQLAlchemy
                pass
        if not has_fields:
            md += "- (No direct fields annotated)\n"
        md += "\n"
    return md

with open("sevalor_AgentV2/docs/sdd/data-model.md", "w") as f:
    f.write(parse_models())

print("Data model generated.")
