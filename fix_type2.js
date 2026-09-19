const fs = require('fs');
const path = 'pwa/src/app/gestio/copilot/page.tsx';
let content = fs.readFileSync(path, 'utf8');

content = content.replace(
  'const form = e.target;',
  'const form = e.target as HTMLFormElement;'
).replace(
  'titol: form.elements.namedItem("titol").value,',
  'titol: (form.elements.namedItem("titol") as HTMLInputElement).value,'
).replace(
  'contingut: form.elements.namedItem("contingut").value,',
  'contingut: (form.elements.namedItem("contingut") as HTMLTextAreaElement).value,'
).replace(
  'tags: form.elements.namedItem("tags").value',
  'tags: (form.elements.namedItem("tags") as HTMLInputElement).value'
);

fs.writeFileSync(path, content, 'utf8');
