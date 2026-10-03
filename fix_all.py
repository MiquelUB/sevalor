import re
import sys

def replace_camera_labels(filename):
    with open(filename, 'r') as f:
        content = f.read()

    # Import fix
    if 'import CameraInput' not in content:
        content = re.sub(
            r'import \{ (.*?) \} from "@/lib/media";',
            lambda m: 'import { ' + m.group(1).replace('CAMERA_LIVE_INPUT_PROPS, ', '').replace('CAMERA_LIVE_INPUT_PROPS', '') + ' } from "@/lib/media";\nimport CameraInput from "@/components/CameraInput";',
            content
        )
        content = content.replace("import {  } from", "import {} from")

    # Find labels
    out = []
    i = 0
    while i < len(content):
        # find next <label
        start = content.find('<label', i)
        if start == -1:
            out.append(content[i:])
            break
            
        out.append(content[i:start])
        
        # find matching </label>
        end = content.find('</label>', start)
        if end == -1:
            out.append(content[start:])
            break
            
        block = content[start:end+8]
        
        if 'CAMERA_LIVE_INPUT_PROPS' in block:
            # We found a block!
            # Extract state variable: setFotoXXX(w) or setFotoXXX(blob)
            m_set = re.search(r'set([A-Za-z0-9_]+)\(', block)
            if m_set:
                state_var_suffix = m_set.group(1)
                
                # Check for label text in ternary: e.g. fotoXXX ? "OK" : "Capturar"
                # Or just hardcode based on file context if it's simpler, but let's try to extract
                lbl = "Capturar"
                if "Tiquet capturat" in block:
                    lbl = "Foto Tiquet (Viu)"
                elif "Odòmetre capturat" in block:
                    lbl = "Foto Odòmetre"
                elif "Afegir" in block:
                    lbl = "Afegir"
                elif "Càmera en Viu" in block:
                    lbl = "Càmera en Viu"
                
                # Special cases for state var
                if state_var_suffix == "FotoPujada":
                    cond = "fotoPujada"
                else:
                    cond = f"foto{state_var_suffix}"
                    
                new_comp = f'<CameraInput captured={{!!{cond}}} label="{lbl}" onCapture={{(blob) => {{ set{state_var_suffix}(blob); setErrorValidacio(null); }} }} />'
                # incidencies uses handleFotoChange, let's special case it
                if "handleFotoChange" in block:
                    new_comp = f'<CameraInput captured={{fotoPujada}} label="{lbl}" onCapture={{(blob) => {{ setFotoPujada(true); setErrorValidacio(null); }} }} />'
                    
                # tiquets has custom handleFotoTiquet
                if "handleFotoTiquet" in block:
                    new_comp = f'<CameraInput captured={{!!fotoTiquet}} label="{lbl}" onCapture={{(blob) => {{ setFotoTiquet(blob); setErrorValidacio(null); }} }} />'
                if "handleFotoOdometre" in block:
                    new_comp = f'<CameraInput captured={{!!fotoOdometre}} label="{lbl}" onCapture={{(blob) => {{ setFotoOdometre(blob); setErrorValidacio(null); }} }} />'
                    
                out.append(new_comp)
            else:
                out.append(block)
        else:
            out.append(block)
            
        i = end + 8

    with open(filename, 'w') as f:
        f.write(''.join(out))

for file in ["pwa/src/app/operari/vehicles/page.tsx", "pwa/src/app/operari/tiquets/page.tsx", "pwa/src/app/operari/incidencies/page.tsx"]:
    replace_camera_labels(file)

