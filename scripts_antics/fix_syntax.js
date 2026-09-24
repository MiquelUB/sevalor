const fs = require('fs');
let content = fs.readFileSync("pwa/src/app/gestio/clients/page.tsx", "utf-8");

const bad = "              )}\n            </div>\n            </div>\n\n            {/* SEVALOR DIGITAL TWIN UI (Fitxa 360) */}";
const good = "              )}\n            </div>\n\n            {/* SEVALOR DIGITAL TWIN UI (Fitxa 360) */}";

content = content.replace(bad, good);

fs.writeFileSync("pwa/src/app/gestio/clients/page.tsx", content);
