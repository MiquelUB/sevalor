# Research & Lessons Learned: Backoffice Gestió

**Feature Path**: `sevalor_AgentV2/specs/01-backoffice-gestio`  
**Status**: Consolidat (Migrat de les especificacions 001 a 011 i incidències reals de desenvolupament)  
**Propòsit**: Documentar fallades tècniques prèvies, patrons d'errors recurrents, decisions de governança i regles mandatòries d'implementació per blindar futures iteracions.

---

## 1. Lliçons Apreses Crítiques i Regles d'Or

### 1. Obligatorietat de `Depends(get_db_with_tenant_context)` per a Polítiques RLS
- **El Problema**: A PostgreSQL, les polítiques de Row Level Security (RLS) s'activen basant-se en la variable de sessió `app.current_empresa_id` (`SET LOCAL app.current_empresa_id = :empresa_id`). Si un endpoint utilitza un injector de base de dades ordinari (`Depends(get_db)`) en lloc del context d'inquilí, la variable no s'estableix mai en aquesta connexió del pool.
- **La Conseqüència**: La base de dades denega la lectura de files retornant llistats buits (comportament silenciosament enganyós) o, pitjor, si la connexió s'executa amb un usuari amb permisos administratius sense RLS forçat, es produeix una fuita massiva de dades entre diferents empreses clients (*Cross-Tenant Data Leak*).
- **La Regla d'Or**: **Tots els endpoints de l'API de Gestió han d'injectar obligatòriament la sessió mitjançant `Depends(get_db_with_tenant_context)`**. Mai s'ha d'utilitzar una sessió crua sense l'establiment previ del paràmetre d'empresa.

```python
# CORRECTE:
@router.get("/clients")
async def llistar_clients(
    db: AsyncSession = Depends(get_db_with_tenant_context),
    current_user: Usuari = Depends(requereix_rol(["BOSS", "SECRETARIA", "ENGINYER"]))
):
    ...
```

---

### 2. Importació Obligatòria d'`UploadFile` i `File` a Endpoints Multipart
- **El Problema**: En diversos mòduls que reben fitxers d'albarans, fotos d'odòmetres o plànols (com va ocórrer durant el desenvolupament de `proveidors.py` i `flota.py`), es van afegir paràmetres de tipus `file: UploadFile = File(...)` a les funcions dels routers sense haver afegit prèviament la importació a la capçalera del fitxer.
- **La Conseqüència**: Python va aixecar un error fatal en temps d'execució: `NameError: name 'UploadFile' is not defined`. Això va provocar la caiguda immediata del procés de càrrega del mòdul i errors 500 continus a qualsevol petició d'alta documental.
- **La Regla d'Or**: **Sempre que es defineixi un endpoint que rebi arxius binaris o formularis multipart, cal verificar explícitament que la capçalera inclou**:
```python
from fastapi import File, UploadFile
```

---

### 3. Evitar `NameError: name 'valida_uuid'` (Definir o Eliminar Dependències Inutilitzades)
- **El Problema**: En els controladors de càrrega OCR (`flota.py`, `magatzem.py`), es van copiar fragments de codi que incloïen dependències com `tenant: dict = Depends(valida_uuid)` o comprovacions manuals `emp_uuid = valida_uuid(empresa_id)` sense importar ni declarar la funció `valida_uuid`.
- **La Conseqüència**: Quan el framework resolia les dependències de la ruta abans d'executar el controlador, l'aplicació fallava amb `NameError: name 'valida_uuid' is not defined`.
- **La Regla d'Or**: 
  - Si la validació d'identificador d'empresa ja està resolta de forma centralitzada mitjançant `get_db_with_tenant_context`, cal **eliminar la dependència redundant `valida_uuid`**.
  - Si cal transformar o verificar una cadena com a UUID en un paràmetre de ruta (`/articles/{article_id}`), cal importar la utilitat canònica compartida o implementar un bloc `try/except ValueError` que aixequi un `HTTPException(status_code=400, detail="Identificador invàlid")`.

```python
# Patró de validació canònica segura d'UUID:
def valida_uuid(id_str: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(id_str))
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(status_code=400, detail="Identificador UUID invàlid.")
```

---

### 4. Precaució amb Rutes Absolutes a Next.js (Multi-Tenant & Reverse Proxy)
- **El Problema**: La utilització de rutes absolutes codificades en dur (com ara cridar `fetch('/api/v1/gestio/clients')` o `window.location.href = 'https://app.sevalor.com/gestio'`) trenca la navegació quan l'aplicació es desplega sota subdominis multi-empresa (ex: `empresa-aigua.sevalor.cat`), dominis corporatius personalitzats (*whitelabel*) o proxies inversos que afegeixen prefixos de ruta.
- **La Conseqüència**: Petits desplaçaments provoquen errors 404 de recursos no trobats, fallades de preflight CORS entre orígens no previstos, o pèrdua de l'estat de sessió a la PWA mòbil en mode fora de línia.
- **La Regla d'Or**: **Cal utilitzar sempre el client API centralitzat (`apiClient`) configurat amb la variable d'entorn `process.env.NEXT_PUBLIC_API_URL`**, rutes relatives del router de Next.js (`useRouter()`, `<Link href="...">`), i respectar el context de la marca camaleònica.

---

## 2. Incidències Reals Resoltes i Anàlisi de Causes Arrel

### Incidència A: Contaminació Creuada de Context (Superadmin vs Gestió) i Polítiques CORS
- **Símptoma**: En obrir la interfície de Gestió després d'utilitzar el panell de Superadmin al mateix navegador, la pantalla es bloquejava amb errors de CORS i fallades 403 Forbidden a `/configuracio/empresa`.
- **Causa Arrel**: Tots dos mòduls compartien el mateix origen web i emmagatzemaven tokens a `localStorage`. Quan l'usuari obria Gestió, el frontend enviava el token JWT de Superadmin. El backend detectava el rol `SUPERADMIN` i aplicava el veto corporatiu pertinent (ja que un administrador d'infraestructura no pot llegir dades privades d'empreses). En produir-se un rebuig no gestionat adequadament amb `ValueError` abans d'arribar al controlador, el middleware de CORS de FastAPI no podia adjuntar les capçaleres `Access-Control-Allow-Origin`, transformant un error lògic de permisos en un error de xarxa CORS confús.
- **Solució Aplicada**:
  1. Aïllar les claus d'emmagatzematge de token a nivell de frontend (`token_gestio` vs `token_superadmin`).
  2. Implementar un short-circuit al middleware de backend que capturi els intents d'accés de Superadmin i retorni un `HTTP 403` normalitzat amb totes les capçaleres CORS injectades.

---

### Incidència B: Condicions de Cursa a l'Encadenament Veri*factu (SHA-256)
- **Símptoma**: Durant proves de facturació simultània d'ordres de treball de tancament de mes, dues factures consecutives es van generar amb el mateix `hash_anterior_sha256`, invalidant la cadena criptogràfica legal exigida per l'AEAT.
- **Causa Arrel**: Dues peticions concurrents van executar `SELECT hash_cadena_sha256 FROM factures_capcalera ORDER BY numero DESC LIMIT 1` a la vegada. Ambdues van llegir el mateix hash anterior abans que cap de les dues hagués desat la nova fila.
- **Solució Aplicada**: Aplicar un bloqueig pessimista forçat (`SELECT FOR UPDATE`) sobre la taula o fila de seqüència de facturació de l'empresa:
```sql
SELECT id, hash_cadena_sha256, numero 
FROM factures_capcalera 
WHERE empresa_id = :empresa_id AND serie = :serie 
ORDER BY numero DESC 
LIMIT 1 
FOR UPDATE;
```
Això garanteix que la generació de la factura següent s'esperi fins que la transacció de l'anterior s'hagi consolidat (*commit*) a la base de dades.

---

### Incidència C: Famílies de Magatzem Estàtiques vs Adaptació per Verticals
- **Símptoma**: Una empresa instal·ladora de xarxes de fontaneria i reg es trobava amb opcions de catàleg fixes pensades per a electricistes (ex: "Quadres elèctrics", "Safates portacables") que entorpien el filtratge i l'alta ràpida.
- **Causa Arrel**: Els desplegables de categories del magatzem estaven definits com un enumerat rígid a la base de dades i al frontend.
- **Solució Aplicada**: Migració a un model dinàmic en què la taula `empreses` defineix el camp `magatzem_families_default` (JSONB) configurat durant l'onboarding segons la vertical de negoci de l'empresa (WATERPRO, ELECTRICPRO, CLIMAPRO), permetent que l'API injecti les opcions de selecció adaptades a cada realitat operativa.

---

## 3. Directrius Arquitectòniques Innegociables

1. **Principi Zero Mock Data**: Està terminantment prohibit retornar col·leccions falses o *mocks* a l'entorn de producció o desenvolupament integrat. Si un tenant no té clients, proveïdors o factures, la resposta ha de ser un array buit `[]` o un objecte buit que activi l'Estat Dia 0 a la interfície.
2. **Prohibició de Codis QR en Magatzem i Eines**: La traçabilitat interna d'inventari i eines es realitza exclusivament mitjançant codis de barres estàndard (EAN-13, Code 128) i números de sèrie físics. Els codis QR queden restringits estrictament a:
   - Factures legals Veri*factu (impressió tributària).
   - Enllaços d'invitació i accés d'usuaris/clients al canal Telegram.
3. **Principi Human-in-the-Loop (HITL) en Processos d'IA**: Cap pressupost d'imprevistos, transcripció pericial o informe tècnic generat per Copilot o Whisper es pot consolidar automàticament ni enviar-se a facturació sense que un usuari humà amb rol de Supervisor o Boss hagi premut el botó d'aprovació expressa.
4. **Segregació de Rols a la Capa d'Accés de Dades (Zero-Trust)**: La protecció de la informació mai es delega a la mera ocultació visual d'elements d'interfície. Qualsevol crida HTTP d'un usuari amb rol `ENGINYER` a endpoints de `/comptabilitat/*` o a salaris privats de personal ha de retornar un codi d'estat `HTTP 403 Forbidden` a nivell de middleware.
