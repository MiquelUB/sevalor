const fs = require('fs');
const path = 'pwa/src/app/gestio/layout.tsx';
let content = fs.readFileSync(path, 'utf8');

if (!content.includes('import CopilotWidget')) {
  content = content.replace('import Link from "next/link";', 'import Link from "next/link";\nimport CopilotWidget from "@/components/CopilotWidget";');
  content = content.replace('      {/* MODAL SPOTLIGHT META-SEARCH (<200 ms) */}', '      <CopilotWidget />\n\n      {/* MODAL SPOTLIGHT META-SEARCH (<200 ms) */}');
  fs.writeFileSync(path, content, 'utf8');
}
