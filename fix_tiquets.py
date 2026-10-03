import re
import sys

with open('pwa/src/app/operari/tiquets/page.tsx', 'r') as f:
    content = f.read()

# Replace Tiquet
tiquet_pattern = r'<label[^>]*>.*?fotoTiquet \? "Tiquet capturat ✓" : "Foto Tiquet \(Viu\).*?<input.*?onChange=\{handleFotoTiquet\}.*?<\/label>'
content = re.sub(tiquet_pattern, '<CameraInput captured={!!fotoTiquet} label="Foto Tiquet (Viu)" onCapture={(blob) => { setFotoTiquet(blob); setErrorValidacio(null); }} />', content, flags=re.DOTALL)

# Replace Odometre
odometre_pattern = r'<label[^>]*>.*?fotoOdometre \? "Odòmetre capturat ✓" : "Foto Odòmetre".*?<input.*?onChange=\{handleFotoOdometre\}.*?<\/label>'
content = re.sub(odometre_pattern, '<CameraInput captured={!!fotoOdometre} label="Foto Odòmetre" onCapture={(blob) => { setFotoOdometre(blob); setErrorValidacio(null); }} />', content, flags=re.DOTALL)

with open('pwa/src/app/operari/tiquets/page.tsx', 'w') as f:
    f.write(content)
