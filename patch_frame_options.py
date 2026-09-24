import re

with open("pwa/next.config.js", "r") as f:
    content = f.read()

content = content.replace(
'''          {
            key: 'X-Frame-Options',
            value: 'DENY',
          },''',
'''          {
            key: 'X-Frame-Options',
            value: 'SAMEORIGIN',
          },'''
)

with open("pwa/next.config.js", "w") as f:
    f.write(content)

print("Patched next.config.js to set X-Frame-Options to SAMEORIGIN")
