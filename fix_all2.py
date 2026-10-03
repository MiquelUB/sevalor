import re

def fix_vehicles(filename):
    with open(filename, 'r') as f:
        content = f.read()
    content = content.replace("fotoFoto", "foto")
    with open(filename, 'w') as f:
        f.write(content)

def fix_incidencies(filename):
    with open(filename, 'r') as f:
        content = f.read()
    pattern = r'<label[^>]*>.*?<Camera className="w-4 h-4 text-emerald-600" \/>.*?<span>\{fotoPujada \? "Foto Capturada ✓" : "Càmera en Viu"\}<\/span>.*?<input\s+\{\.\.\.CAMERA_LIVE_INPUT_PROPS\}.*?onChange=\{handleFotoChange\}.*?<\/label>'
    content = re.sub(pattern, '<CameraInput captured={fotoPujada} label="Càmera en Viu" onCapture={(blob) => { setFotoPujada(true); setErrorValidacio(null); }} />', content, flags=re.DOTALL)
    with open(filename, 'w') as f:
        f.write(content)

def fix_tiquets(filename):
    with open(filename, 'r') as f:
        content = f.read()
    # Replace Tiquet
    tiquet_pattern = r'<label[^>]*>.*?fotoTiquet \? "Tiquet capturat ✓" : "Foto Tiquet \(Viu\).*?<input.*?onChange=\{handleFotoTiquet\}.*?<\/label>'
    content = re.sub(tiquet_pattern, '<CameraInput captured={!!fotoTiquet} label="Foto Tiquet (Viu)" onCapture={(blob) => { setFotoTiquet(blob); setErrorValidacio(null); }} />', content, flags=re.DOTALL)

    # Replace Odometre
    odometre_pattern = r'<label[^>]*>.*?fotoOdometre \? "Odòmetre capturat ✓" : "Foto Odòmetre".*?<input.*?onChange=\{handleFotoOdometre\}.*?<\/label>'
    content = re.sub(odometre_pattern, '<CameraInput captured={!!fotoOdometre} label="Foto Odòmetre" onCapture={(blob) => { setFotoOdometre(blob); setErrorValidacio(null); }} />', content, flags=re.DOTALL)
    with open(filename, 'w') as f:
        f.write(content)

fix_vehicles('pwa/src/app/operari/vehicles/page.tsx')
fix_incidencies('pwa/src/app/operari/incidencies/page.tsx')
fix_tiquets('pwa/src/app/operari/tiquets/page.tsx')
