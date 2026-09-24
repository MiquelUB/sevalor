import re

with open("pwa/src/components/CopilotWidget.tsx", "r") as f:
    content = f.read()

# Add Check to SendMessage
# We need to render the action payload
content = content.replace('setConversaXat((prev) => [\n          ...prev,\n          { sender: "bot", text: dades.resposta, links: dades.enllacos || [] },\n        ]);',
'''const requiresConf = dades.metadata?.tool_resultat?.requires_confirmation;
        setConversaXat((prev) => [
          ...prev,
          { 
            sender: "bot", 
            text: dades.resposta || (requiresConf ? dades.metadata.tool_resultat.missatge : ""), 
            links: dades.enllacos || [],
            actionContext: requiresConf ? dades.metadata.tool_resultat : null
          },
        ]);'''
)

# Add Action Confirm function
confirm_func = '''
  const [executantAccio, setExecutantAccio] = useState(false);
  const confirmarAccio = async (actionContext: any, mIdx: number) => {
    setExecutantAccio(true);
    try {
      const res = await apiFetch("/gestio/copilot/action/confirm", {
        method: "POST",
        body: JSON.stringify({ action: actionContext.action, payload: actionContext.payload }),
      });
      const dades = await res.json();
      
      // Update message to show success
      setConversaXat(prev => {
        const newArr = [...prev];
        newArr[mIdx].actionContext = null; // Hide the action box
        newArr[mIdx].text = newArr[mIdx].text + "\\n\\n✅ " + (dades.missatge || "Acció executada amb èxit.");
        return newArr;
      });
    } catch (err) {
      alert("Error a l'executar l'acció.");
    } finally {
      setExecutantAccio(false);
    }
  };

  const enviarMissatgeXat = async (msgOpcional?: string) => {
'''

content = content.replace('const enviarMissatgeXat = async (msgOpcional?: string) => {', confirm_func)

# Render action block
render_action = '''
                {m.actionContext && (
                  <div className="mt-2 p-2 bg-indigo-50 border border-indigo-200 rounded-xl">
                    <p className="text-[10px] font-bold text-indigo-800 mb-1">Requereix Confirmació:</p>
                    <pre className="text-[9px] text-indigo-900 bg-indigo-100 p-1.5 rounded mb-2 overflow-x-auto">
                      {JSON.stringify(m.actionContext.payload, null, 2)}
                    </pre>
                    <div className="flex gap-2">
                      <button 
                        onClick={() => confirmarAccio(m.actionContext, idx)}
                        disabled={executantAccio}
                        className="flex-1 bg-indigo-600 text-white py-1 rounded text-[10px] font-bold hover:bg-indigo-700 disabled:opacity-50"
                      >
                        {executantAccio ? "Processant..." : "Aprovar i Executar"}
                      </button>
                    </div>
                  </div>
                )}
'''

content = content.replace('{m.text}\n                </div>', '{m.text}\n                </div>' + render_action)

with open("pwa/src/components/CopilotWidget.tsx", "w") as f:
    f.write(content)

print("Patch applied to CopilotWidget.tsx")
