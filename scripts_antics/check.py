with open("pwa/src/app/gestio/proveidors/page.tsx", "r") as f:
    lines = f.readlines()
for i, l in enumerate(lines):
    if "nouAplicaIsp" in l or "nouIban" in l:
        print(f"{i}: {l.strip()}")
