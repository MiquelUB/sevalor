import re

with open("pwa/src/app/gestio/layout.tsx", "r") as f:
    content = f.read()

# Restore the broken filter return
broken_filter = """    if (isEmbed) {
    return (
      <div className="flex flex-col h-screen bg-slate-950 overflow-hidden">
        <main className="flex-1 flex flex-col h-full w-full">{children}</main>
      </div>
    );
  }

  return ("""
content = content.replace(broken_filter, "    return (")

# Now inject it before the REAL return
# The real return looks like:
#   return (
#     <div className="min-h-screen bg-slate-50 text-slate-900

correct_injection = """  if (isEmbed) {
    return (
      <div className="flex flex-col h-screen bg-slate-950 overflow-hidden">
        <main className="flex-1 flex flex-col h-full w-full">{children}</main>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900"""

content = content.replace('  return (\n    <div className="min-h-screen bg-slate-50 text-slate-900', correct_injection)

with open("pwa/src/app/gestio/layout.tsx", "w") as f:
    f.write(content)

print("Layout fixed")
