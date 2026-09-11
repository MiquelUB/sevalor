import json

transcript_path = "/home/akaun/.gemini/antigravity/brain/da520f80-05dd-469f-aa64-db6210163c62/.system_generated/logs/transcript_full.jsonl"

steps = [63, 707, 909, 961, 1073, 1172, 1304, 1457, 1613]

with open(transcript_path, "r", encoding="utf-8") as f:
    for line in f:
        data = json.loads(line)
        step_idx = data.get("step_index")
        if step_idx in steps:
            for tc in data.get("tool_calls", []):
                args = tc.get("args", {})
                if "implementation_plan.md" in args.get("TargetFile", ""):
                    content = args.get("CodeContent") or ""
                    print(f"=== STEP {step_idx}: Title & Sections (len {len(content)}) ===")
                    for l in content.splitlines():
                        if l.startswith("#"):
                            print(" ", l)
