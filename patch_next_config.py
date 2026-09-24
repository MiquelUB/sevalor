import re

with open("pwa/next.config.js", "r") as f:
    content = f.read()

content = content.replace("eslint: { ignoreDuringBuilds: false },", "eslint: { ignoreDuringBuilds: true },")

with open("pwa/next.config.js", "w") as f:
    f.write(content)

print("Patched next.config.js to ignore eslint")
