import json

transcript_path = "/home/akaun/.gemini/antigravity/brain/da520f80-05dd-469f-aa64-db6210163c62/.system_generated/logs/transcript_full.jsonl"

steps_to_inspect = [270, 505, 679, 736, 883, 943, 1025, 1150, 1280, 1417, 1537, 1753]

with open(transcript_path, "r", encoding="utf-8") as f:
    for line in f:
        data = json.loads(line)
        step_idx = data.get("step_index")
        if step_idx in steps_to_inspect:
            for tc in data.get("tool_calls", []):
                args = tc.get("args", {})
                if "walkthrough.md" in args.get("TargetFile", ""):
                    content = args.get("CodeContent") or args.get("ReplacementContent") or ""
                    print(f"=== STEP {step_idx}: {tc.get('name')} (len {len(content)}) ===")
                    first_lines = [l for l in content.splitlines() if l.strip()][:5]
                    for fl in first_lines:
                        print("  ", fl)
