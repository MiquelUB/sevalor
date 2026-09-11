import os

with open('backend/app/core/config.py', 'r') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if line.startswith('    SECRET_KEY: str = "sevalor-dev-secret-key-32-chars-long-abc"'):
        new_lines.append('    SECRET_KEY: str | None = None\n')
    else:
        new_lines.append(line)

content = "".join(new_lines)

# Add auto-generate logic at the end
content += """
import secrets

if not settings.SECRET_KEY:
    import os
    if os.getenv("TESTING") == "1" or os.getenv("ENVIRONMENT") == "development":
        settings.SECRET_KEY = secrets.token_urlsafe(32)
    else:
        raise ValueError("CRITICAL: SECRET_KEY no està definida a les variables d'entorn en producció.")
"""

with open('backend/app/core/config.py', 'w') as f:
    f.write(content)
