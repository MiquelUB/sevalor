import re
import sys

def refactor_file(filename):
    with open(filename, "r", encoding="utf-8") as f:
        content = f.read()

    # Import
    if 'import CameraInput from "@/components/CameraInput";' not in content:
        content = re.sub(
            r'import \{ (.*?) \} from "@/lib/media";',
            lambda m: 'import { ' + m.group(1).replace('CAMERA_LIVE_INPUT_PROPS, ', '').replace('CAMERA_LIVE_INPUT_PROPS', '') + ' } from "@/lib/media";\nimport CameraInput from "@/components/CameraInput";',
            content
        )
        content = content.replace("import {  } from", "import {} from") # cleanup if empty

    # There are two main patterns of label used:
    # Pattern 1 (vehicles):
    # <label className="flex flex-col items-center justify-center p-4 rounded-xl border-2 border-dashed border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/50 cursor-pointer hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors">
    #   <Camera className={`w-8 h-8 mb-2 ${fotoOdometreInici ? 'text-emerald-500' : 'text-slate-400'}`} />
    #   <span className={`text-sm font-bold ${fotoOdometreInici ? 'text-emerald-600' : 'text-slate-500'}`}>
    #     {fotoOdometreInici ? "OK" : "Capturar"}
    #   </span>
    #   <input
    #     {...CAMERA_LIVE_INPUT_PROPS}
    #     onChange={async (e) => {
    #       if (e.target.files && e.target.files[0]) {
    #         const w = await compressImageToWebP(e.target.files[0]);
    #         setFotoOdometreInici(w);
    #         setErrorValidacio(null);
    #       }
    #     }}
    #     className="hidden"
    #   />
    # </label>
    
    # Actually, it's easier to find the `setFotoXXX(w)` or similar and extract the state variable name.
    
    # We will find `<label...` up to `</label>` containing CAMERA_LIVE_INPUT_PROPS.
    
    pattern = r'<label[^>]*>.*?{([^}]*\?[^:]*:[^}]*)}.*?<input\s+\{\.\.\.CAMERA_LIVE_INPUT_PROPS\}.*?set([a-zA-Z0-9_]+)\((?:w|blob)\);.*?<\/label>'
    
    def repl(m):
        full_match = m.group(0)
        label_expr = m.group(1) # e.g. fotoOdometreInici ? "OK" : "Capturar"
        state_var = m.group(2) # e.g. FotoOdometreInici
        
        # Determine the fallback label string from the ternary
        # {fotoOdometreInici ? "OK" : "Capturar"}
        match_label = re.search(r':\s*"([^"]+)"', label_expr)
        lbl = match_label.group(1) if match_label else "Capturar"
        
        state_camel = state_var[0].lower() + state_var[1:]
        
        return f'<CameraInput captured={{!!{state_camel}}} label="{lbl}" onCapture={{(blob) => {{ set{state_var}(blob); setErrorValidacio(null); }} }} />'
    
    new_content = re.sub(pattern, repl, content, flags=re.DOTALL)
    
    with open(filename, "w", encoding="utf-8") as f:
        f.write(new_content)

for arg in sys.argv[1:]:
    refactor_file(arg)
