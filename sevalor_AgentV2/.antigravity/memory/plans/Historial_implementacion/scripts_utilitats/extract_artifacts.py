import json

transcript_path = "/home/akaun/.gemini/antigravity/brain/da520f80-05dd-469f-aa64-db6210163c62/.system_generated/logs/transcript_full.jsonl"

with open(transcript_path, "r", encoding="utf-8") as f:
    for idx, line in enumerate(f):
        data = json.loads(line)
        tool_calls = data.get("tool_calls", [])
        for tc in tool_calls:
            name = tc.get("name")
            args = tc.get("args", {})
            target = args.get("TargetFile", "")
            step_idx = data.get("step_index")
            desc = args.get("Description", "")
            content_len = len(args.get("CodeContent", args.get("ReplacementContent", "")))
            if "implementation_plan.md" in target:
                print(f"PLAN step {step_idx}: {name} | {desc[:60]} | len={content_len}")
            elif "walkthrough.md" in target:
                print(f"WALKTHROUGH step {step_idx}: {name} | {desc[:60]} | len={content_len}")
