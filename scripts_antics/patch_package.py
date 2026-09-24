import json

with open("pwa/package.json", "r") as f:
    pkg = json.load(f)

test_script = pkg["scripts"]["test"]
if "node test_pwa_sw.mjs" not in test_script:
    pkg["scripts"]["test"] = test_script + " && node test_pwa_sw.mjs"

with open("pwa/package.json", "w") as f:
    json.dump(pkg, f, indent=2)
