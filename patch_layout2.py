import re

with open("pwa/src/app/gestio/layout.tsx", "r") as f:
    content = f.read()

# Find the main return statement
target = "  return ("
replacement = """  if (isEmbed) {
    return (
      <div className="flex flex-col h-screen bg-slate-950 overflow-hidden">
        <main className="flex-1 flex flex-col h-full w-full">{children}</main>
      </div>
    );
  }

  return ("""

content = content.replace(target, replacement, 1)

with open("pwa/src/app/gestio/layout.tsx", "w") as f:
    f.write(content)

print("Inserted early return successfully.")
