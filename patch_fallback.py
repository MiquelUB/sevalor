import re

path = "pwa/src/app/gestio/flota/page.tsx"
with open(path, "r") as f:
    text = f.read()

pattern = re.compile(r"""      \} else \{
        // Fallback optimista per a entorn local.*?
        setModalNouVehicleObert\(false\);
      \}
    \} catch \{
      setModalNouVehicleObert\(false\);
    \}
  \};""", re.DOTALL)

replacement = """      } else {
        const errorData = await res.json();
        alert("Error al crear el vehicle: " + (errorData.detail || "Error desconegut"));
      }
    } catch (err) {
      alert("Excepció de xarxa: " + err);
    }
  };"""

new_text = pattern.sub(replacement, text)
if new_text != text:
    print("Fallback removed")
else:
    print("Fallback not found")

with open(path, "w") as f:
    f.write(new_text)
