# API Specification

## api.v1.auth
### POST `/login`
**Function**: `login_oficina`

### GET `/me`
**Function**: `get_me`

## api.v1.health
### GET ``
**Function**: `health_check`

Comprova la connectivitat del sistema i de la base de dades PostgreSQL.

## api.v1.operari_auth
### POST `/login`
**Function**: `login_operari`

## api.v1.telemetria
### GET `/kpis`
**Function**: `get_system_kpis`

Retorna els KPIs de disponibilitat, microserveis, cues i IA local sota CPU-only (Spec 022).

### PATCH `/tenants/{tenant_id}/features`
**Function**: `toggle_tenant_feature`

Commuta un feature flag d'un tenant en temps real (Spec 022 RF-15).

### PATCH `/tenants/{tenant_id}/quota`
**Function**: `update_tenant_quota`

Actualitza el pla de llicència i quota d'operaris d'un tenant (Spec 022 RF-13).

### POST `/traces-error`
**Function**: `record_error_trace`

Registra una traça d'error tècnica a l'esquema segregat superadmin_telemetry (Spec 022 RF-03).

### GET `/traces-error`
**Function**: `list_error_traces`

Llista les darreres traces d'error des de superadmin_telemetry sense dades de negoci.

## api.v1.workers
### GET `/status/{task_id}`
**Function**: `get_task_status`

Retorna l'estat en temps real d'una tasca encolada (Spec 024 RF-21).

## api.v1.gestio.cerca
### GET ``
**Function**: `cerca_spotlight`

Executa la cerca ràpida Spotlight multi-entitat sota el tenant actual.

### GET `/items`
**Function**: `llistar_spotlight_items_inicials`

Retorna els elements principals per a cerca ràpida.

## api.v1.gestio.clients
### GET ``
**Function**: `llistar_clients`

### POST ``
**Function**: `alta_client`

### GET `/{client_id}/iban`
**Function**: `obtenir_iban_client`

Retorna l'IBAN complet del client. Enginyer rep 403.

### PUT `/{client_id}/iban`
**Function**: `canviar_iban_client`

Canvia l'IBAN d'un client (Spec 002). Enginyer rep 403.

### GET `/{client_id}/fitxa360`
**Function**: `obtenir_fitxa_360_client`

Recopila cronològicament totes les intervencions tècniques, peces instal·lades
i incidències registrades per al client durant els últims 365 dies (Spec 012 RF-04).

## api.v1.gestio.comptabilitat
### GET `/factures`
**Function**: `llistar_factures`

### POST `/factures`
**Function**: `crear_factura`

### GET `/factures/{factura_id}/xml`
**Function**: `exportar_factura_xml`

## api.v1.gestio.configuracio
### GET `/empresa`
**Function**: `obtenir_dades_empresa`

Consulta els paràmetres de l'empresa autenticada sota RLS.

### PUT `/empresa`
**Function**: `actualitzar_dades_empresa`

Actualitza dades bàsiques de l'empresa (Boss i Secretaria; Enginyer 403).

### GET `/marca`
**Function**: `obtenir_marca_camaleonica`

Retorna la configuració cromàtica i visual de la marca de l'empresa.

### PUT `/marca`
**Function**: `actualitzar_marca_camaleonica`

Modifica els colors HSL corporatius amb validació algorítmica WCAG 2.1 AA (EDGE-02).

### POST `/marca/adn`
**Function**: `analitzar_adn_marca`

Analitza l'ADN de marca per Copilot IA i proposa un esborrany de paleta (RF-12).

### POST `/marca/adn/aprovar`
**Function**: `aprovar_paleta_adn`

Aprovació HITL de la paleta proposada per la IA, reservada al Boss (RF-13).

### POST `/logotip`
**Function**: `pujar_logotip_corporatiu`

Pujada de logotip amb comprovació de Magic Bytes i redimensionament sobirà (EDGE-03).

### GET `/usuaris`
**Function**: `llistar_usuaris_administratius`

Llistat complet de personal d'oficina (Zero Mock Data, RF-01, RF-04).

### POST `/usuaris`
**Function**: `crear_usuari_administratiu`

Alta de personal administratiu amb contrasenya forta de 12 caràcters (RF-02; Enginyer 403).

### PUT `/usuaris/{usuari_id}`
**Function**: `actualitzar_usuari_administratiu`

Modifica dades de l'empleat administratiu (Boss i Secretaria; Enginyer 403).

### DELETE `/usuaris/{usuari_id}`
**Function**: `eliminar_usuari_administratiu`

Eliminació o baixa d'usuari amb protecció contra orfandat de l'inquilí (EDGE-05).

### POST `/usuaris/{usuari_id}/reset-2fa`
**Function**: `reiniciar_2fa_usuari`

Reinici de secret 2FA TOTP reservat exclusivament al Boss (RF-06).

### POST `/emergencia-2fa-boss`
**Function**: `acces_emergencia_2fa_boss`

Accés d'emergència de l'últim Boss mitjançant codi de recuperació estàtic (EDGE-01).

### GET `/slots`
**Function**: `llistar_slots_jornada`

Llistat d'slots de jornada laboral de l'empresa.

### POST `/slots`
**Function**: `crear_slot_jornada`

Crea un nou slot de jornada laboral amb validació de rangs coherents (EDGE-08; Enginyer 403).

### PUT `/telegram`
**Function**: `actualitzar_credencials_telegram`

Guarda les credencials del Bot de Telegram (Boss i Secretaria; Enginyer 403).

### POST `/telegram/provar`
**Function**: `provar_connexio_telegram`

Test asíncron de getMe contra l'API de Telegram amb timeout de 5s (RF-20, EDGE-09).

## api.v1.gestio.copilot
### GET `/estat-node`
**Function**: `obtenir_estat_node_ia`

Retorna l'estat operatiu del Node d'IA Sobirà Local (RF-01, RF-02).

### GET `/garanties/auditoria`
**Function**: `auditar_garanties_i_memoria_finca`

Audita l'historial de 365 dies, garanties de fabricant i garantia interna de mà d'obra (RF-04, RF-05, RF-06, RF-07, EDGE-07, EDGE-09).

### POST `/incidencies/peritatge`
**Function**: `peritar_incidencia_multimodal`

Peritatge multimodal de veu (Whisper v3) i foto d'incidència de camp (RF-08, RF-09, EDGE-02, EDGE-03).

### PUT `/memorandums/{memo_id}/validacio`
**Function**: `validar_memorandum_enginyer`

Validació humana de l'Enginyer sobre el Memoràndum Tècnic d'Incidència (RF-10 HITL).

### GET `/memorandums`
**Function**: `llistar_memorandums`

Llista els memoràndums tècnics registrats per a l'empresa.

### POST `/reconciliacio/post-obra`
**Function**: `reconciliar_post_obra`

Reconciliació automàtica post-obra dels 4 pilars del cost real i proposta de pressupost corregit (RF-11, RF-12, EDGE-04, EDGE-08).

### PUT `/reconciliacio/{auditoria_id}/aprovar-pressupost`
**Function**: `aprovar_pressupost_corregit_enginyer`

Confirmació humana indispensable de l'Enginyer per enviar el pressupost corregit a facturació (RF-13 HITL).

### POST `/stock/verificacio-assignacio`
**Function**: `verificar_stock_en_assignacio`

Monitorització preventiva de stock en assignar obra amb protecció de concurrència SELECT FOR UPDATE (RF-14, RF-15, EDGE-06).

### POST `/xat`
**Function**: `consultar_xat_tecnic`

Finestra de xat tècnic amb RAG local, veto d'enginyer i aïllament de vertical (RF-16, RF-19, RF-20, RF-20.1, EDGE-05, EDGE-10).

### GET `/alertes`
**Function**: `llistar_alertes_copilot`

Llista les alertes actives de garantia i reposició de stock.

### POST `/rag`
**Function**: `afegir_document_rag`

Permet als administradors afegir protocols i documentació al RAG del Copilot.

### GET `/rag`
**Function**: `llistar_documents_rag`

Llista els protocols del RAG actius.

## api.v1.gestio.feines
### GET ``
**Function**: `llistar_feines`

### POST ``
**Function**: `alta_feina`

### GET `/mapa`
**Function**: `llistar_feines_mapa`

Retorna les OTs del tenant actual amb les seves coordenades reals per al Mapa GIS (Spec 001/005).

### PUT `/{feina_id}/agendar`
**Function**: `agendar_feina`

Planifica/reagenda una Ordre de Treball usant Optimistic Locking (version_id).
Si un altre usuari ha modificat l'OT, es retorna HTTP 409 Conflict.

### GET `/actives`
**Function**: `llistar_intervencions_actives`

## api.v1.gestio.flota
### GET ``
**Function**: `llistar_flota`

### POST ``
**Function**: `alta_vehicle`

### GET `/propers`
**Function**: `llistar_vehicles_propers`

Retorna els vehicles de l'empresa ordenats per proximitat geogràfica a les coordenades donades (Haversine).
Determina la posició del vehicle segons l'OT activa en curs o ubicació registrada.

## api.v1.gestio.magatzem
### GET `/articles`
**Function**: `llistar_articles`

### POST `/articles`
**Function**: `alta_article`

### GET `/magatzems/{magatzem_id}/estoc`
**Function**: `llistar_estoc_magatzem`

Llista l'estoc d'un magatzem (Spec 004).

### POST `/magatzems/{magatzem_id}/moviment`
**Function**: `registrar_moviment_estoc`

Registra un moviment d'estoc (entrada/sortida/reserva) amb bloqueig pessimista (SELECT FOR UPDATE).

Spec 004: prevenció de condicions de carrera. Un SELECT FOR UPDATE sobre
la fila d'estoc garanteix que dos enginyers no puguin reservar el mateix
stock concurrentment.

### POST `/picking`
**Function**: `crear_fulla_picking`

Crea una fulla de picking per a una ordre de treball (RF-20: 1 tasca = 1 fulla).

### POST `/picking/{picking_id}/linies`
**Function**: `afegir_linia_picking`

Afegeix una línia de picking a una fulla (RF-17: reserva amb SELECT FOR UPDATE).

### PUT `/picking/linies/{linia_id}/pick-in`
**Function**: `confirmar_pick_in`

Confirma la recollida de material (pick-in) des de la PWA (RF-23).

### PUT `/picking/linies/{linia_id}/pick-out`
**Function**: `confirmar_devolucio`

Registra la devolució de sobrants i mermes (RF-22: pick-out post-obra).

### POST `/albara/ocr`
**Function**: `processar_document_ocr`

Processa un document PDF o imatge via OCR d'IA per extreure dades d'albarà o factura en BACKGROUND.

### POST `/albara/confirmar`
**Function**: `confirmar_document`

### PUT `/articles/{article_id}`
**Function**: `modificar_article`

## api.v1.gestio.notificacions
### GET `/converses`
**Function**: `llistar_converses`

### POST `/converses`
**Function**: `crear_conversa`

### GET `/converses/{conversa_id}/missatges`
**Function**: `llistar_missatges`

### POST `/converses/{conversa_id}/missatges`
**Function**: `crear_missatge`

### PUT `/converses/{conversa_id}/estat`
**Function**: `canviar_estat_conversa`

### GET `/converses/{conversa_id}/enllac-factura`
**Function**: `generar_enllac_factura`

### POST `/converses/{conversa_id}/invitar-telegram`
**Function**: `generar_invitacio_telegram`

Genera un token d'invitació per al Bot de Telegram (Spec 023 RF-05: expira 48h, un sol ús).

## api.v1.gestio.operaris
### GET ``
**Function**: `llistar_operaris`

### POST ``
**Function**: `alta_operari`

### POST `/{operari_id}/reset-pin`
**Function**: `reset_pin_operari`

## api.v1.gestio.planols
### GET ``
**Function**: `llistar_planols`

### POST ``
**Function**: `alta_planol`

### GET `/carpetes`
**Function**: `llistar_carpetes`

Llista les carpetes de plànols de l'empresa (Spec 010).

### POST `/carpetes`
**Function**: `crear_carpeta`

Crea una carpeta de plànols (Spec 010).

### GET `/planols/{planol_id}/capes`
**Function**: `llistar_capes_planol`

Llista les capes vectorials d'un plànol (Spec 010).

### POST `/planols/{planol_id}/capes`
**Function**: `crear_capa_planol`

Crea una capa vectorial sobre un plànol (Spec 010).

### PUT `/planols/{planol_id}/capes/{capa_id}`
**Function**: `editar_capa_planol`

Edita una capa vectorial d'un plànol (Spec 010). Les capes immutables no es poden editar.

### DELETE `/planols/{planol_id}/capes/{capa_id}`
**Function**: `eliminar_capa_planol`

Elimina una capa vectorial (Spec 010). Les immutables no es poden eliminar.

### POST `/{planol_id}/exportar-pdf`
**Function**: `exportar_planol_pdf`

## api.v1.gestio.pressupostos
### GET ``
**Function**: `llistar_pressupostos`

Llista els pressupostos de l'empresa (filtrats per RLS).

### POST ``
**Function**: `crear_pressupost`

Crea un nou pressupost en estat PENDENT.

### GET `/{pressupost_id}`
**Function**: `obtenir_pressupost`

Obté el detall d'un pressupost per ID (Spec 009 / TEST-F4-01).

### POST `/{pressupost_id}/enviar-telegram`
**Function**: `enviar_pressupost_via_telegram`

Envia el pressupost amb Inline Keyboard al client via Telegram (Spec 009 RF-09).

## api.v1.gestio.proveidors
### GET ``
**Function**: `llistar_proveidors`

### POST ``
**Function**: `alta_proveidor`

### GET `/{proveidor_id}/iban`
**Function**: `obtenir_iban_proveidor`

Retorna l'IBAN complet del proveïdor. Només BOSS/SECRETARIA (403 per Enginyer).

### PUT `/{proveidor_id}/iban`
**Function**: `canviar_iban_proveidor`

Canvia l'IBAN d'un proveïdor amb autorització de BOSS i registre SIF (EDGE-01, RF-09).

### PUT `/{proveidor_id}`
**Function**: `editar_proveidor`

Edita la fitxa del proveïdor (nom, telèfon, email, especialitat).

## api.v1.operari_pwa.feines
### GET `/feines`
**Function**: `llistar_les_meves_feines`

### GET `/feines/{feina_id}`
**Function**: `obtenir_detall_feina`

### PUT `/feines/{feina_id}/iniciar-trajecte`
**Function**: `iniciar_trajecte`

Commuta el vehicle a Blau (En trànsit) i activa buffer de 25 min (Spec 013 RF-11).

### PUT `/feines/{feina_id}/comencar`
**Function**: `comencar_feina`

Comença el cronòmetre de la feina amb control de geovalla (Spec 013 RF-12, RF-12.1).

### POST `/feines/{feina_id}/fotos`
**Function**: `pujar_foto_qualitat`

Protocol obligatori de 3 fotos de control de qualitat (Spec 013 RF-13).

### GET `/feines/{feina_id}/fotos`
**Function**: `consultar_fotos_qualitat`

Consulta l'estat del protocol de 3 fotos (Spec 013 RF-13, RF-14).

### PUT `/feines/{feina_id}/finalitzar`
**Function**: `finalitzar_feina`

Finalitza la feina. Bloquejat si no s'han capturat les 3 fotos (Spec 013 RF-14, RF-17).

## api.v1.operari_pwa.incidencies
### GET `/incidencies`
**Function**: `llistar_incidencies_operari`

### POST `/incidencies`
**Function**: `reportar_incidencia`

## api.v1.operari_pwa.jornada
### POST `/inici`
**Function**: `iniciar_jornada`

### POST `/jornada/inici`
**Function**: `iniciar_jornada`

### GET `/activa`
**Function**: `get_jornada_activa`

### GET `/jornada/activa`
**Function**: `get_jornada_activa`

### POST `/{jornada_id}/fi`
**Function**: `finalitzar_jornada`

### POST `/jornada/{jornada_id}/fi`
**Function**: `finalitzar_jornada`

### POST `/{jornada_id}/vehicle`
**Function**: `assignar_vehicle_a_jornada`

Assigna un vehicle a l'operari per a la jornada actual i comprova odòmetre.

### POST `/jornada/{jornada_id}/vehicle`
**Function**: `assignar_vehicle_a_jornada`

Assigna un vehicle a l'operari per a la jornada actual i comprova odòmetre.

## api.v1.operari_pwa.picking
### POST ``
**Function**: `crear_fulla_picking_operari`

### POST `/{picking_id}/linies`
**Function**: `afegir_linia_picking_operari`

### PUT `/linies/{linia_id}`
**Function**: `actualitzar_linia_picking_operari`

## api.v1.operari_pwa.sync
### POST `/push`
**Function**: `bulk_sync_push`

Rep una llista d'accions encuades (Offline-First) i les processa seqüencialment.
(Spec 013 - RF-08)

## api.v1.operari_pwa.tiquets
### GET `/tiquets`
**Function**: `llistar_tiquets_operari`

### POST `/tiquets`
**Function**: `registrar_tiquet_carburant`

### POST `/tiquets/ocr`
**Function**: `pujar_tiquet_ocr`

(Spec 018) Rep una imatge de tiquet, simula extracció OCR i ho desa a DB.

## api.v1.operari_pwa.vehicles
### GET ``
**Function**: `llistar_vehicles_pwa`

### POST `/{vehicle_id}/danys`
**Function**: `reportar_dany_vehicle`

### POST `/{vehicle_id}/checkin`
**Function**: `vehicle_checkin`

### POST `/{vehicle_id}/repostatge`
**Function**: `vehicle_repostatge`

### POST `/{vehicle_id}/checkout`
**Function**: `vehicle_checkout`

## api.v1.superadmin.tenants
### GET ``
**Function**: `llistar_tenants`

### POST `/onboarding`
**Function**: `crear_nou_tenant`

### PUT `/{empresa_id}/estat`
**Function**: `canviar_estat_tenant`

### PUT `/{empresa_id}/quota`
**Function**: `canviar_quota_tenant`

### PUT `/{empresa_id}/feature-flags`
**Function**: `update_feature_flags`

## api.v1.webhooks.telegram
### POST ``
**Function**: `telegram_webhook`

Rep els missatges/updates de Telegram.

