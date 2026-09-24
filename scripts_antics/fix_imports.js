const fs = require('fs');
let content = fs.readFileSync("pwa/src/app/gestio/clients/page.tsx", "utf-8");

// Revert all bad replacements
content = content.replace(/import { Package, Factory, /g, "import { ");

// Add them specifically to lucide-react
content = content.replace('import {\n  Users,', 'import {\n  Package,\n  Factory,\n  Users,');

fs.writeFileSync("pwa/src/app/gestio/clients/page.tsx", content);
