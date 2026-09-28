path = "pwa/src/app/gestio/proveidors/page.tsx"
with open(path, "r") as f:
    text = f.read()

target = "const [modalAltaObert, setModalAltaObert] = useState(false);"
replace = """const [modalAltaObert, setModalAltaObert] = useState(false);
  const [ocrLoading, setOcrLoading] = useState(false);"""

text = text.replace(target, replace)

with open(path, "w") as f:
    f.write(text)
print("State fixed")
