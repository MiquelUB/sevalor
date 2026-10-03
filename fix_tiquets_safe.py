import sys

def process(filename):
    with open(filename, "r") as f:
        content = f.read()

    # We know exactly how it looks in tiquets/page.tsx
    # It looks like:
    # <label className="p-3 border-2 border-dashed border-slate-300 dark:border-slate-700 rounded-xl flex flex-col items-center justify-center text-center cursor-pointer hover:border-emerald-500 transition-colors">
    #   <Camera className="w-5 h-5 text-emerald-600 mb-1" />
    #   <span className="text-[10px] font-bold text-slate-700 dark:text-slate-300">
    #     {fotoTiquet ? "Tiquet capturat ✓" : "Foto Tiquet (Viu)"}
    #   </span>
    #   <input
    #     {...CAMERA_LIVE_INPUT_PROPS}
    #     onChange={handleFotoTiquet}
    #     className="hidden"
    #   />
    # </label>
    
    # Let's find `<label className="p-3 border-2 border-dashed border-slate-300 dark:border-slate-700 rounded-xl flex flex-col items-center justify-center text-center cursor-pointer hover:border-emerald-500 transition-colors">`
    # and `</label>`
    
    out = []
    lines = content.split('\n')
    skip = False
    
    for i, line in enumerate(lines):
        if 'import { CAMERA_LIVE_INPUT_PROPS, compressImageToWebP }' in line:
            out.append('import { compressImageToWebP } from "@/lib/media";')
            out.append('import CameraInput from "@/components/CameraInput";')
            continue
            
        if '<label className="p-3 border-2 border-dashed border-slate-300' in line:
            # Check what's inside the next few lines
            if 'handleFotoTiquet' in "".join(lines[i:i+15]):
                out.append('                <CameraInput captured={!!fotoTiquet} label="Foto Tiquet (Viu)" onCapture={(blob) => { setFotoTiquet(blob); setErrorValidacio(null); }} />')
                skip = True
                continue
            elif 'handleFotoOdometre' in "".join(lines[i:i+15]):
                out.append('                  <CameraInput captured={!!fotoOdometre} label="Foto Odòmetre" onCapture={(blob) => { setFotoOdometre(blob); setErrorValidacio(null); }} />')
                skip = True
                continue

        if skip:
            if '</label>' in line:
                skip = False
            continue
            
        out.append(line)
        
    with open(filename, "w") as f:
        f.write('\n'.join(out))

process('pwa/src/app/operari/tiquets/page.tsx')
