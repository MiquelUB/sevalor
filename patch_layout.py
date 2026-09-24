import re

with open("pwa/src/app/gestio/layout.tsx", "r") as f:
    content = f.read()

# 1. Add isEmbed state
state_code = """  const [cercaSpotlight, setCercaSpotlight] = useState("");
  const [isEmbed, setIsEmbed] = useState(false);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      setIsEmbed(window.location.search.includes("embed=true") || window.self !== window.top);
    }
  }, []);"""

content = content.replace('  const [cercaSpotlight, setCercaSpotlight] = useState("");', state_code)

# 2. If isEmbed is true, render a minimal layout
render_code = """  // Early return minimal layout if embedded
  if (isEmbed) {
    return (
      <div className="flex flex-col h-screen bg-slate-950 overflow-hidden">
        <main className="flex-1 flex flex-col h-full w-full">{children}</main>
      </div>
    );
  }

  // Calculate filtered results for spotlight..."""

content = content.replace("  // Calculate filtered results for spotlight...", render_code)

with open("pwa/src/app/gestio/layout.tsx", "w") as f:
    f.write(content)

print("Patched layout.tsx to handle isEmbed state cleanly.")
