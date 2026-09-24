import re

with open("pwa/src/app/gestio/clients/page.tsx", "r") as f:
    content = f.read()

old_code = """      await apiFetch("/gestio/feines", {
        method: "POST",
        body: payload
      });"""

new_code = """      await apiFetch("/gestio/feines", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify(payload)
      });"""

content = content.replace(old_code, new_code)

with open("pwa/src/app/gestio/clients/page.tsx", "w") as f:
    f.write(content)

print("Fixed!")
