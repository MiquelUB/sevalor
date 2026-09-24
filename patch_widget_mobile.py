import re

with open("pwa/src/components/CopilotWidget.tsx", "r") as f:
    content = f.read()

# 1. Add props
content = content.replace("export default function CopilotWidget() {", "export default function CopilotWidget({ isMobile = false }: { isMobile?: boolean }) {")

# 2. Add image state and Camera Icon import
content = content.replace('import { Sparkles, X, Send, ExternalLink, Bot, MessageSquare } from "lucide-react";',
'import { Sparkles, X, Send, ExternalLink, Bot, MessageSquare, Camera, Image as ImageIcon } from "lucide-react";')

content = content.replace('const [carregant, setCarregant] = useState(false);',
'''const [carregant, setCarregant] = useState(false);
  const [imatgeB64, setImatgeB64] = useState<string | null>(null);

  const handleImageUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onloadend = () => {
        setImatgeB64(reader.result as string);
      };
      reader.readAsDataURL(file);
    }
  };
''')

# 3. Add image to fetch payload
content = content.replace('body: JSON.stringify({ pregunta: textFinal }),',
'body: JSON.stringify({ pregunta: textFinal, imatge_b64: imatgeB64 }),')

# 4. Clear image after send
content = content.replace('setCarregant(true);', 'setCarregant(true);\n    setImatgeB64(null);')

# 5. Modify container classes for mobile
content = content.replace(
'className="fixed bottom-6 right-6 w-96 h-[550px] bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-2xl flex flex-col z-50 overflow-hidden flex flex-col"',
'className={`fixed z-50 bg-white dark:bg-slate-900 flex flex-col overflow-hidden shadow-2xl border-slate-200 dark:border-slate-800 ${isMobile ? "inset-0 w-full h-full pb-[60px]" : "bottom-6 right-6 w-96 h-[550px] border rounded-2xl"}`}'
)

content = content.replace(
'className={`fixed bottom-6 right-6 p-4 rounded-full bg-indigo-600 text-white shadow-xl hover:bg-indigo-700 transition-all z-50 flex items-center justify-center ${obert ? \'hidden\' : \'\'}`}',
'className={`fixed p-4 rounded-full bg-indigo-600 text-white shadow-xl hover:bg-indigo-700 transition-all z-50 flex items-center justify-center ${obert ? \'hidden\' : \'\'} ${isMobile ? "bottom-20 right-4" : "bottom-6 right-6"}`}'
)


# 6. Add camera input in chat input row
chat_input = '''
          <div className="p-3 border-t border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-850">
            {imatgeB64 && (
              <div className="mb-2 relative inline-block">
                <img src={imatgeB64} alt="Upload preview" className="h-16 w-16 object-cover rounded-lg border border-slate-200" />
                <button onClick={() => setImatgeB64(null)} className="absolute -top-2 -right-2 bg-rose-500 text-white rounded-full p-0.5">
                  <X className="w-3 h-3" />
                </button>
              </div>
            )}
            <div className="flex items-center gap-2">
              <label className="p-2 text-slate-400 hover:text-indigo-600 cursor-pointer bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 rounded-xl transition-colors">
                <Camera className="w-5 h-5" />
                <input type="file" accept="image/*" capture="environment" className="hidden" onChange={handleImageUpload} />
              </label>
              <input
                type="text"
'''

content = content.replace(
'''          <div className="p-3 border-t border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-850 flex items-center gap-2">
            <input
              type="text"''', chat_input)

content = content.replace(
'''            <button
              onClick={() => enviarMissatgeXat()}''', 
'''            </div>
            <button
              onClick={() => enviarMissatgeXat()}'''
)

# Fix a small div error from the replacement
content = content.replace(
'''            </div>
            <button
              onClick={() => enviarMissatgeXat()}
              disabled={carregant || !missatgeXat.trim()}
              className="p-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white transition-all shadow"
            >
              <Send className="w-4 h-4" />
            </button>
          </div>''',
'''              <button
                onClick={() => enviarMissatgeXat()}
                disabled={carregant || (!missatgeXat.trim() && !imatgeB64)}
                className="p-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white transition-all shadow"
              >
                <Send className="w-4 h-4" />
              </button>
            </div>
          </div>'''
)

with open("pwa/src/components/CopilotWidget.tsx", "w") as f:
    f.write(content)

print("Patch applied to CopilotWidget.tsx")
