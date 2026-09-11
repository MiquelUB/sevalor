Pla de Tasques Atòmiques d'Implementació — Sevalor Suite (v4.0)
Aquest document conté el desglossament de la planificació tècnica de Sevalor Suite en tasques de menys de 30 minuts de durada estimativa, ordenades per dependència seqüencial, indicant els requisits funcionals (RF) que cobreix cadascuna d'elles i la línia de validació "Fet quan:" per a l'assegurament de la qualitat (QA).
--------------------------------------------------------------------------------
🧱 Bloc 1: Infraestructura i Base de Dades Inicial (Fundació)

    [x] Tasca 1.1: Configuració d'Orquestració Docker Compose al Servidor Hetzner
        Dependència: Cap (Punt d'inici).
        RF associats: Spec 021 (RF-04), Spec 022 (RF-10), Spec 024 (RF-01).
        Fet quan: En executar docker compose up -d a la VPS Hetzner CPX21, s'aixequen i queden en estat operatiu els contenidors de PostgreSQL 16 (amb PostGIS i pgvector), Redis 7, la pila de Supabase local i el contenidor d'inferència local de Whisper.
    [x] Tasca 1.2: Definició de l'Esquema de Base de Dades - Core Multi-Tenant
        Dependència: Tasca 1.1.
        RF associats: Spec 011 (RF-21), Spec 019 (RF-24), Spec 021 (RF-01).
        Fet quan: Les taules físiques empreses, usuaris i slots_jornada estan creades a la base de dades PostgreSQL amb les seves respectives restriccions de clau primària (UUID) i clau única composta UNIQUE (empresa_id, NIF).
    [x] Tasca 1.3: Script SQL d'Activació de Row Level Security (RLS) Global
        Dependència: Tasca 1.2.
        RF associats: Spec 011 (RF-21), Spec 019 (RF-24), Spec 021 (RF-05).
        Fet quan: En executar el script SQL d'inicialització, la directiva ALTER TABLE ... FORCE ROW LEVEL SECURITY està activa a totes les taules creades i la política filtra estrictament per l'atribut app.current_empresa_id.
    [x] Tasca 1.4: Esquema Físic de Base de Dades - Clients i Finques amb PostGIS
        Dependència: Tasca 1.2.
        RF associats: Spec 002 (RF-01 a RF-05).
        Fet quan: Les taules clients i finques s'han creat a la base de dades PostgreSQL, definint la columna coords_gps de forma estricta com a tipus de dades geomètric GEOMETRY(Point, 4326).
    [x] Tasca 1.5: Esquema Físic de Base de Dades - Magatzem i Inventari de Format Continu
        Dependència: Tasca 1.2.
        RF associats: Spec 004 (RF-01, RF-06), Spec 014 (RF-13, RF-18).
        Fet quan: Les taules articles, estocs_magatzem i magatzems estan creades, incloent el camp autorreferencial parent_material_id a la taula articles per a traçar l'estoc de retalls de canonades i cables.
    [x] Tasca 1.6: Esquema Físic de Base de Dades - Flota i de Repostatges de Carburant
        Dependència: Tasca 1.2.
        RF associats: Spec 006 (RF-01), Spec 015 (RF-07), Spec 018 (RF-05).
        Fet quan: S'han creat les taules físiques vehicles, estancies_substitucio i tiquets_carburant amb els respectius camps de traçabilitat tiquet_foto_path i odometre_foto_path.
    [x] Tasca 1.7: Esquema Físic de Base de Dades - Registre d'Esdeveniments SIF (Inmutable)
        Dependència: Tasca 1.2.
        RF associats: Spec 007 (RF-12, RF-24).
        Fet quan: La taula registre_esdeveniments_sif està creada i un disparador (trigger) de base de dades a PostgreSQL bloqueja de forma atòmica i retorna un error davant de qualsevol intent de sentència UPDATE o DELETE.

--------------------------------------------------------------------------------
🔑 Bloc 2: Backend Core, Seguretat Multi-Tenant i Autenticació

    [x] Tasca 2.1: Implementació de Middleware d'Extracció de Context Tenant a FastAPI
        Dependència: Tasca 1.3.
        RF associats: Spec 011 (RF-21), Spec 019 (RF-24).
        Fet quan: El middleware de seguretat intercepta cada petició HTTP, extreu el token JWT, valida el subdomini de l'inquilí i executa de forma transparent la sentència SQL SET LOCAL app.current_empresa_id a la connexió de PostgreSQL assignada.
    [x] Tasca 2.2: Test d'Integració Pytest d'Aïllament d'Inquilins (RLS)
        Dependència: Tasca 2.1.
        RF associats: Spec 011 (RF-21), Spec 019 (RF-24), Spec 021 (RF-05).
        Fet quan: En executar la comanda pytest test_rls.py, es verifica amb un assert binari que una consulta de lectura realitzada amb la sessió de l'"Inquilí A" sobre la taula clients retorna un array buit [] en intentar accedir de forma fraudulenta a dades de l'"Inquilí B".
    [x] Tasca 2.3: API d'Enrolament Inicial de Dispositiu a la PWA (SMS OTP)
        Dependència: Tasca 2.1.
        RF associats: Spec 019 (RF-03, RF-11).
        Fet quan: Un endpoint de tipus POST a /api/v1/operari/enrolar rep el número de telèfon mòbil, valida que figuri a la taula usuaris de l'empresa, genera i envia un codi OTP de 6 dígits i asenta el secret del dispositiu a IndexedDB.
    [x] Tasca 2.4: Mecanisme de Validació Criptogràfica Offline al Client (Web Crypto API)
        Dependència: Tasca 2.3.
        RF associats: Spec 019 (RF-05, RF-06).
        Fet quan: El script del Service Worker en JavaScript executa correctament la derivació de clau amb l'algorisme PBKDF2 (100.000 iteracions) a partir d'un PIN de 4 dígits de camp i desxifra el bloc sentinella SEVALOR_SENTINEL mitjançant AES-GCM-256.
    [x] Tasca 2.5: Endpoint de Recuperació de PIN Temporal i Registre d'Incidència
        Dependència: Tasca 2.3.
        RF associats: Spec 019 (RF-14, RF-15, RF-16).
        Fet quan: En cridar l'endpoint POST /api/v1/operari/recuperar-pin, el backend genera de forma desatenduda un PIN temporal de 4 caràcters, enclava el seu enviament per SMS i obre una incidència de seguretat a l'expedient de l'operari.

--------------------------------------------------------------------------------
📱 Bloc 3: Mòdul de Campo (PWA /operari)

    [x] Tasca 3.1: Disseny Tàctil d'Inici de Sessió (Numpad) en Next.js
        Dependència: Tasca 2.4.
        RF associats: Spec 019 (RF-01, RF-02, RF-04).
        Fet quan: El component de teclat de gran format de la PWA processa les entrades tàctils i, al completar el quart dígit del PIN de forma exacta, commuta el flux d'entrada i activa de forma immediata la petició d'obertura de sessió.
    [x] Tasca 3.2: Control d'Abertura de Càmera en Viu Antifraude
        Dependència: Tasca 3.1.
        RF associats: Spec 020 (RF-17).
        Fet quan: L'element <input> de captura mòbil conté strictly els atributs HTML5 accept="image/*" capture="environment", inhabilitant per complet la selecció d'arxius històrics des de les galeries o carrete local del terminal.
    [x] Tasca 3.3: Lògica de Compressió WebP en Client i Emmagatzematge IndexedDB
        Dependència: Tasca 3.2.
        RF associats: Spec 020 (RF-11, RF-12).
        Fet quan: El script comprimeix localment qualsevol captura en format WebP limitant el seu pes de fitxer a sota d'1 MB i asenta de forma segura el registre a IndexedDB.
    [x] Tasca 3.4: Pantalla de Llista de Feines del Dia amb Estat Buit Net (Zero-Mock)
        Dependència: Tasca 3.1.
        RF associats: Spec 013 (RF-05, RF-07).
        Fet quan: Davant de zero feines assignades per a la data actual, la vista Next.js renderitza un Empty State sincer i amigable amb el text exactat: "No hi ha feines assignades per a avui".
    [x] Tasca 3.5: Lògica del Botó "Iniciar Trajecte" i Notificació d'ETA
        Dependència: Tasca 3.4.
        RF associats: Spec 013 (RF-11).
        Fet quan: En prémer "Iniciar Trajecte", la PWA actualitza l'estat del vehicle associat a Blau (En trànsit) a la base de dades i dispara la notificació automàtica d'ETA cap al client final via SMS/Telegram.
    [x] Tasca 3.6: Bloqueig d'Inici de Feina per Control de Geovalla d'Obra
        Dependència: Tasca 3.4.
        RF associats: Spec 013 (RF-12, RF-12.1).
        Fet quan: En prémer "Començar Feina", el script compara la geolocalització nativa del dispositiu mòbil amb el punt de la parcela; si es troba a més de 50 metres, bloca l'inici ordinar i obre el protocol d' "Inici per Desviació".
    [x] Tasca 3.7: Pantalla de Registre d'Incidències Multimodal i Botó SOS
        Dependència: Tasca 3.1.
        RF associats: Spec 016 (RF-05, RF-06, RF-07).
        Fet quan: El formulari d'incidència s'envia de forma vàlida amb un sol canal aportat (ex: àudio) i compta amb el botó vermell de trucada manual d'emergència directa al 112 de veu tradicional.
    [x] Tasca 3.8: Visor Cartogràfic Tàctil amb Capes d'Anotacions As-Built
        Dependència: Tasca 3.1.
        RF associats: Spec 017 (RF-10, RF-11, RF-13).
        Fet quan: El visor de plànols carrega un Selector de Capes dinàmic per commutar la visibilitat individual dels vectors de camp d'anotacions As-Built de forma no destructiva sobre el plànol mestre.
    [x] Tasca 3.9: Control d'Edició de Plànols sobre Obres Tancades
        Dependència: Tasca 3.8.
        RF associats: Spec 017 (RF-13.1).
        Fet quan: En col·locar un pin gràfic sobre un plànol d'una tasca marcada com a tancada i facturada, el sistema inhabilita l'escriptura local i emet a pantalla el pop-up: «Capa tancada, vols crear una capa nova?».
    [x] Tasca 3.10: Formulari de Tiquets de Despesa amb Segon Foto d'Odòmetre
        Dependència: Tasca 3.2.
        RF associats: Spec 015 (RF-07), Spec 018 (RF-05).
        Fet quan: En seleccionar la categoria de tiquet "Carburant", el sistema de la PWA bloqueja el desat de la despesa fins que es capturen consecutivament la foto del tiquet de benzinera i la foto de l'odòmetre en viu.

--------------------------------------------------------------------------------
🖥️ Bloc 4: Central Web i Administració (/gestio)

    [x] Tasca 4.1: Panell de Control - Spotlight Meta-Search de Ràpid Rendiment
        Dependència: Tasca 1.4.
        RF associats: Spec 001 (RF-02), Spec 011 (RF-22).
        Fet quan: Al prémer Cmd+K o Ctrl+K a Next.js, s'obre el cercador Spotlight d'oficina i, en escriure un criteri, retorna la llista d'ordres, vehicles i clients indexada en un temps inferior a 200 ms.
    [x] Tasca 4.2: Triple Conciliació de Factures (Three-Way Matching) en Proveïdors
        Dependència: Tasca 1.5.
        RF associats: Spec 003 (RF-14, RF-21).
        Fet quan: El backend compara de forma digital les línies, imports i quantitats de la factura de proveïdor amb l'albarà de lliurament del transportista i el pressupost d'obra, passant-la a estat "Conciliada" si el desvío és del 0%.
    [x] Tasca 4.3: Bloqueig Pesimista de Reserves d'Estoc (Magatzem)
        Dependència: Tasca 1.5.
        RF associats: Spec 004 (RF-17, RF-20).
        Fet quan: La consulta transaccional de reserves a PostgreSQL utilitza estrictamente l'ordre SELECT FOR UPDATE ORDER BY material_id per assegurar el bloqueig atòmic i evitar condicions de bloqueig mutu (deadlocks).
    [x] Tasca 4.4: Enrutador de Seguretat de Rols del Backend - Veto d'Enginyer
        Dependència: Tasca 2.1.
        RF associats: Spec 001 (RF-03), Spec 002 (RF-17), Spec 007 (RF-05).
        Fet quan: Un usuari amb rol "Enginyer" intenta invocar endpoints del llibre de comptabilitat o de consultes salarials reals de base d'operaris de l'empresa, rebent un error dur HTTP 403 Forbidden.
    [x] Tasca 4.5: Mòdul de Flota - Control d'ITV en Quatre Veredictes
        Dependència: Tasca 1.6.
        RF associats: Spec 006 (RF-18).
        Fet quan: Al registrar el document de resultats de la ITV com a desfavorable, el sistema de flota canvia automàticament el furgó a estat no-operatiu i enllaça els defectes tècnics com a tasca d'obra mecànica interna de taller.

--------------------------------------------------------------------------------
⚙️ Bloc 5: Microserveis, Integracions i Processament Asíncron (Workers)

    [x] Tasca 5.1: Pipeline de Transcripció d'Àudio Whisper amb Quantificació INT8
        Dependència: Tarea 1.1.
        RF associats: Spec 012 (RF-16), Spec 022 (RF-10).
        Fet quan: Un worker asíncron de Celery rep un fitxer de nota d'àudio de camp i l'analitza localment utilitzant faster-whisper a precisió INT8 en menys de 8 segons sense superar el límit del 90% d'ús de CPU del servidor Hetzner.
    [x] Tasca 5.2: Bot de Telegram de Clients - Middleware de Prevenció de Doble Extensió
        Dependència: Tarea 1.1.
        RF associats: Spec 023 (RF-16).
        Fet quan: El bot interactiu d'aiogram 3.x intercepta un document de tiquet i, en cas de detectar extensions dobles (ex: rebut.pdf.sh), bloca immediatament la pujada, purga l'arxiu de la memòria i respon un avís d'error.
    [x] Tasca 5.3: Generació de Factures Veri*factu en PDF (ReportLab) amb Codi QR
        Dependència: Tarea 1.7.
        RF associats: Spec 007 (RF-12, RF-14), Spec 024 (RF-07).
        Fet quan: El worker asíncron genera el document de factura en PDF inalterable utilitzant la llibreria ReportLab de Python, inserint el codi QR legal oficial i el hash signat i encadenat de conformitat amb la AEAT.
    [x] Tasca 5.4: Outbox Pattern per a Envia de Lots SOAP de Veri*factu
        Dependència: Tarea 5.3.
        RF associats: Spec 024 (RF-07, RF-11).
        Fet quan: El sistema llegeix de forma desatendida l'Outbox local de tiquets des de la ruta /docs/<empresa_id>/factures/outbox/ mitjançant Celery Beat, transmetent-los cap a la AEAT de forma asíncrona amb reintents exponencials.
    [x] Tasca 5.5: Còpies de Seguretat de Tenants amb Filtre d'Exclusió de Recursivitat
        Dependència: Tarea 1.1.
        RF associats: Spec 024 (RF-18).
        Fet quan: El script setmanal de còpies de seguretat comprimeix el directori de l'inquilí /docs/<empresa_id>/ de forma normalitzada però exclou de forma explícita el subdirectori /docs/<empresa_id>/backups/ del ZIP resultant.