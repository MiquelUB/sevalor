import re
import sys

with open('pwa/src/app/operari/incidencies/page.tsx', 'r') as f:
    content = f.read()

pattern = r'<label[^>]*>.*?<Camera className="w-4 h-4 text-emerald-600" \/>.*?<span>\{fotoPujada \? "Foto Capturada ✓" : "Càmera en Viu"\}<\/span>.*?<input\s+\{\.\.\.CAMERA_LIVE_INPUT_PROPS\}.*?onChange=\{handleFotoChange\}.*?<\/label>'
content = re.sub(pattern, '<CameraInput captured={fotoPujada} label="Càmera en Viu" onCapture={(blob) => { setFotoPujada(true); setErrorValidacio(null); }} />', content, flags=re.DOTALL)

with open('pwa/src/app/operari/incidencies/page.tsx', 'w') as f:
    f.write(content)
