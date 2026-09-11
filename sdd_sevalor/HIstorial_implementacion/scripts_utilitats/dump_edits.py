import json
import os

transcript_path = "/home/akaun/.gemini/antigravity/brain/da520f80-05dd-469f-aa64-db6210163c62/.system_generated/logs/transcript_full.jsonl"
out_dir = "/home/akaun/.gemini/antigravity/brain/da520f80-05dd-469f-aa64-db6210163c62/scratch/raw_extracted"

with open(transcript_path, "r", encoding="utf-8") as f:
    for line in f:
        data = json.loads(line)
        step_idx = data.get("step_index")
        for tc in data.get("tool_calls", []):
            name = tc.get("name")
            args = tc.get("args", {})
            target = args.get("TargetFile", "")
            if "walkthrough.md" in target and name == "replace_file_content":
                content = args.get("ReplacementContent", "")
                desc = args.get("Description", "")
                fname = f"walkthrough_edit_step_{step_idx:04d}.md"
                with open(os.path.join(out_dir, fname), "w", encoding="utf-8") as out:
                    out.write(f"<!-- Description: {desc} -->\n" + content)
                print(f"Dumped {fname} ({len(content)} bytes)")
