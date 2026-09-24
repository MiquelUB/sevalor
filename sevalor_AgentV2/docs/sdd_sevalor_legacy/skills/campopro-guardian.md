---
name: campopro-guardian
description: >-
  Usa aquesta skill per consultar i fer complir els 7 mandats constitucionals, les regles d'or d'enginyeria i els patrons d'infraestructura específics de CampoPro Suite (Zero Mock Data, RLS, Web Crypto API offline, Veri*factu SHA-256, sobirania local Hetzner i proteccions de CPU).
---

# Guardià Constitucional i Patrons de Pila (CampoPro Guardian)

Actua com la guia d'estil i blindatge arquitectònic del projecte. Conté els patrons concrets de codificació i les restriccions d'enginyeria que cal aplicar en qualsevol component de la plataforma per evitar violacions constitucionals o vulnerabilitats de seguretat.

---

## Els 7 Mandats Innegociables i Patrons d'Implementació

### 1. Premissa Suprema: Zero Dades Fictícies (Zero Mock Data)
* **Regla:** Està terminantment prohibit introduir llistes simulades, usuaris de prova, clients ficticis ("Joan Perez") o mocks a qualsevol part del codi de producció o endpoints.
* **Patró UI:** Tot component frontend ha de tractar la llista buida `[]` amb un estat buit fidel (*Empty State*):
  ```tsx
  {items.length === 0 ? (
    <div className="p-8 text-center text-slate-500">
      <p className="text-sm font-medium">No hi ha registres disponibles</p>
    </div>
  ) : (
    /* Renderitzar taula real */
  )}
  ```

### 2. Aïllament Multi-Tenant (PostgreSQL RLS)
* **Regla:** Tota taula amb `empresa_id` ha de tenir RLS forçat.
* **Patró SQL:**
  ```sql
  ALTER TABLE public.[NOM_TAULA] ENABLE ROW LEVEL SECURITY;
  ALTER TABLE public.[NOM_TAULA] FORCE ROW LEVEL SECURITY;

  CREATE POLICY "Aïllament per empresa" ON public.[NOM_TAULA]
  FOR ALL USING (empresa_id::text = current_setting('app.current_empresa_id', true));
  ```
* **Patró FastAPI:** El middleware o sessió asíncrona ha d'injectar:
  ```python
  await session.execute(text("SET LOCAL app.current_empresa_id = :tenant_id"), {"tenant_id": str(tenant_id)})
  ```

### 3. Seguretat Offline a la PWA (Web Crypto API)
* **Regla:** Queda prohibit desar tokens JWT o credencials en text pla a `localStorage` o `IndexedDB`.
* **Patró Criptogràfic:** Derivació de clau mitjançant PBKDF2 (100.000 iteracions) a partir del PIN de 4 dígits de l'operari i xifratge simètric **AES-GCM de 256 bits** amb comprovació contra el bloc sentinella `CAMPOPRO_SENTINEL`.

### 4. Captura Tècnica en Viu Antifrau (HTML5)
* **Regla:** L'operari no pot seleccionar fotografies antigues de la galeria per justificar feines, danys o carburant.
* **Patró Input:**
  ```html
  <input type="file" accept="image/*" capture="environment" />
  ```

### 5. Facturació Legal Inmutable Veri*factu (RD 1007/2023)
* **Regla:** Tota factura emesa ha d'incorporar l'encadenament de Hash SHA-256 amb l'anterior de la mateixa sèrie mitjançant bloqueig pessimista, i codi QR oficial segons l'AEAT.
* **Patró Transaccional:**
  ```python
  # Bloqueig pessimista per evitar concurrències
  last_invoice = await session.execute(
      select(Factura).where(Factura.serie == serie).order_by(Factura.numero.desc()).with_for_update()
  )
  # Càlcul del nou hash SHA-256 encadenat
  nou_hash = hashlib.sha256(f"{nif_emissor}{serie}{numero}{data_iso}{base}{iva}{hash_anterior}".encode()).hexdigest()
  ```

### 6. Sobirania Local d'Emmagatzematge (Cero AWS S3)
* **Regla:** Totes les imatges, factures PDF, informes pericials i còpies de seguretat s'allotgen exclusivament a discs locals de l'empresa o servidor Hetzner a Alemanya:
  - Dades operatives: `/data/<empresa_id>/...`
  - Documents oficials: `/docs/<empresa_id>/...`
  - Còpies de seguretat: `/docs/<empresa_id>/backups/...`
* **Patró de Seguretat de Backups (No-Recursivitat):** El script de compressió ZIP de Celery Beat **ha d'excloure explícitament** la carpeta `backups` per evitar que un backup contingui els backups precedents en bucle exponencial.

### 7. IA Local Eficient en Servidor CPU-only (Hetzner CPX21)
* **Regla:** Hetzner CPX21 no disposa de GPU. El paquet estàndard de Whisper saturaria la CPU.
* **Patró:** Utilitzar estrictament **`faster-whisper`** amb quantificació **INT8** optimitzada per a CPU, processant notes de veu de camp en menys de 3 segons.

### 8. Seguretat del Bot de Telegram (aiogram 3.x)
* **Regla:** Bloqueig d'atacs de programari maliciós (malware) disfressat.
* **Patró Middleware:** Interceptar tots els documents rebuts i rebutjar de forma atòmica qualsevol fitxer que contingui doble extensió (ex: `rebut.pdf.sh` o `foto.jpg.exe`).
