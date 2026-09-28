path = "pwa/src/app/gestio/flota/page.tsx"
with open(path, "r") as f:
    text = f.read()

target = """  const [nouOdometre, setNouOdometre] = useState<number>(0);
  const [nouRegim, setNouRegim] = useState<string>("PROPIETAT");
  const [nouLimitKm, setNouLimitKm] = useState<number>(100000);"""

replacement = """  const [nouOdometre, setNouOdometre] = useState<number>(0);
  const [nouRegim, setNouRegim] = useState<string>("PROPIETAT");
  const [nouLimitKm, setNouLimitKm] = useState<number>(100000);
  
  const [nouEstatItv, setNouEstatItv] = useState<string>("FAVORABLE");
  const [novaDataItv, setNovaDataItv] = useState<string>("");
  const [novaDataAsseguranca, setNovaDataAsseguranca] = useState<string>("");
  const [novaCompanyiaAsseguranca, setNovaCompanyiaAsseguranca] = useState<string>("");
  const [nouCarnet, setNouCarnet] = useState<string>("B");"""

if target in text:
    text = text.replace(target, replacement)
    print("Patched state declarations")
else:
    print("Target state not found")

with open(path, "w") as f:
    f.write(text)
