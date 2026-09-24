# Data Model Schema

## Empresa
- `id`: `Mapped[uuid.UUID]`
- `nom`: `Mapped[str]`
- `nif`: `Mapped[str]`
- `adreca`: `Mapped[Optional[str]]`
- `subdomini`: `Mapped[Optional[str]]`
- `primari_hsl`: `Mapped[str]`
- `secundari_hsl`: `Mapped[str]`
- `accent_hsl`: `Mapped[str]`
- `logotip_path`: `Mapped[Optional[str]]`
- `favicon_path`: `Mapped[Optional[str]]`
- `pla_subscripcio`: `Mapped[str]`
- `estat_pagament`: `Mapped[str]`
- `quota_disc_bytes_autoritzada`: `Mapped[int]`
- `quota_disc_bytes_utilitzada`: `Mapped[int]`
- `telegram_bot_token`: `Mapped[Optional[str]]`
- `telegram_webhook_secret`: `Mapped[Optional[str]]`
- `telegram_bot_actiu`: `Mapped[bool]`
- `telegram_estat_connexio`: `Mapped[str]`
- `adn_marca_path`: `Mapped[Optional[str]]`
- `adn_paleta_proposta`: `Mapped[Optional[dict]]`
- `codis_recuperacio_2fa`: `Mapped[Optional[List[str]]]`
- `monograma`: `Mapped[Optional[str]]`
- `vertical`: `Mapped[str]`
- `node_ia_actiu`: `Mapped[bool]`
- `node_ia_url`: `Mapped[Optional[str]]`
- `feature_copilot_ia`: `Mapped[bool]`
- `feature_flota`: `Mapped[bool]`
- `feature_planols`: `Mapped[bool]`
- `feature_telegram`: `Mapped[bool]`
- `data_onboarding`: `Mapped[datetime]`
- `created_at`: `Mapped[datetime]`
- `updated_at`: `Mapped[datetime]`

## SlotJornada
- `id`: `Mapped[uuid.UUID]`
- `empresa_id`: `Mapped[uuid.UUID]`
- `nom`: `Mapped[str]`
- `modalitat`: `Mapped[str]`
- `hora_entrada_teorica`: `Mapped[time]`
- `hora_sortida_teorica`: `Mapped[time]`
- `hora_inici_dinar`: `Mapped[Optional[time]]`
- `hora_fi_dinar`: `Mapped[Optional[time]]`
- `hores_convenio_setmanals`: `Mapped[float]`
- `es_intensiva_estiu`: `Mapped[bool]`
- `data_inici_estiu`: `Mapped[Optional[date]]`
- `data_fi_estiu`: `Mapped[Optional[date]]`
- `hora_entrada_estiu`: `Mapped[Optional[time]]`
- `hora_sortida_estiu`: `Mapped[Optional[time]]`
- `created_at`: `Mapped[datetime]`
- `updated_at`: `Mapped[datetime]`

## Usuari
- `id`: `Mapped[uuid.UUID]`
- `empresa_id`: `Mapped[Optional[uuid.UUID]]`
- `nif`: `Mapped[str]`
- `nom`: `Mapped[str]`
- `cognoms`: `Mapped[str]`
- `email`: `Mapped[Optional[str]]`
- `telefon`: `Mapped[Optional[str]]`
- `password_hash`: `Mapped[Optional[str]]`
- `pin_hash`: `Mapped[Optional[str]]`
- `rol`: `Mapped[str]`
- `estat`: `Mapped[str]`
- `secret_2fa`: `Mapped[Optional[str]]`
- `totp_activat`: `Mapped[bool]`
- `slot_jornada_id`: `Mapped[Optional[uuid.UUID]]`
- `ip_allowlist`: `Mapped[Optional[List[str]]]`
- `vehicle_assignat_id`: `Mapped[Optional[uuid.UUID]]`
- `especialitat`: `Mapped[Optional[str]]`
- `estat_operatiu`: `Mapped[str]`
- `cap_de_grup_id`: `Mapped[Optional[uuid.UUID]]`
- `cost_hora_eur`: `Mapped[float]`
- `carnet_conduir`: `Mapped[str]`
- `carnet_caducitat`: `Mapped[Optional[date]]`
- `prl_certificat_vigencia`: `Mapped[Optional[date]]`
- `intents_pin_fallits`: `Mapped[int]`
- `pin_bloquejat`: `Mapped[bool]`
- `data_ultim_acces`: `Mapped[Optional[datetime]]`
- `created_at`: `Mapped[datetime]`
- `updated_at`: `Mapped[datetime]`

## RegistreJornadaLaboral
- `id`: `Mapped[uuid.UUID]`
- `empresa_id`: `Mapped[uuid.UUID]`
- `usuari_id`: `Mapped[uuid.UUID]`
- `data_jornada`: `Mapped[date]`
- `hora_inici`: `Mapped[datetime]`
- `hora_fi`: `Mapped[Optional[datetime]]`
- `geolocalitzacio_inici`: `Mapped[Optional[str]]`
- `geolocalitzacio_fi`: `Mapped[Optional[str]]`
- `estat`: `Mapped[str]`
- `tancament_automatic`: `Mapped[bool]`
- `motiu_incidencia`: `Mapped[Optional[str]]`
- `hores_ordinaries`: `Mapped[float]`
- `hores_extraordinaries`: `Mapped[float]`
- `auditat_per_usuari_id`: `Mapped[Optional[uuid.UUID]]`
- `auditoria_data`: `Mapped[Optional[datetime]]`
- `auditoria_motiu`: `Mapped[Optional[str]]`
- `version_id`: `Mapped[int]`
- `created_at`: `Mapped[datetime]`
- `updated_at`: `Mapped[datetime]`

## AuditoriaRegistreJornada
- `id`: `Mapped[uuid.UUID]`
- `empresa_id`: `Mapped[uuid.UUID]`
- `shift_id`: `Mapped[uuid.UUID]`
- `modificat_per_id`: `Mapped[uuid.UUID]`
- `valors_anteriors`: `Mapped[dict]`
- `nous_valors`: `Mapped[dict]`
- `motiu_justificatiu`: `Mapped[str]`
- `created_at`: `Mapped[datetime]`

## Client
- `id`: `Mapped[uuid.UUID]`
- `empresa_id`: `Mapped[uuid.UUID]`
- `codi`: `Mapped[str]`
- `rao_social`: `Mapped[str]`
- `nif`: `Mapped[str]`
- `telefon`: `Mapped[Optional[str]]`
- `email`: `Mapped[Optional[str]]`
- `adreca_fiscal`: `Mapped[Optional[str]]`
- `estat_canal_telegram`: `Mapped[str]`
- `telegram_chat_id`: `Mapped[Optional[int]]`
- `iban_xifrat_simetric`: `Mapped[Optional[str]]`
- `mandat_sepa_path`: `Mapped[Optional[str]]`
- `actiu`: `Mapped[bool]`
- `created_at`: `Mapped[datetime]`
- `updated_at`: `Mapped[datetime]`

## Article
- `id`: `Mapped[uuid.UUID]`
- `empresa_id`: `Mapped[uuid.UUID]`
- `referencia_inventari`: `Mapped[str]`
- `nom`: `Mapped[str]`
- `unitat_mesura`: `Mapped[str]`
- `familia`: `Mapped[str]`
- `estoc_optim`: `Mapped[float]`
- `estoc_minim`: `Mapped[float]`
- `es_lot_caducable`: `Mapped[bool]`
- `parent_material_id`: `Mapped[Optional[uuid.UUID]]`
- `preu_cost`: `Mapped[float]`
- `preu_venda`: `Mapped[float]`
- `actiu`: `Mapped[bool]`
- `created_at`: `Mapped[datetime]`
- `updated_at`: `Mapped[datetime]`

## Magatzem
- `id`: `Mapped[uuid.UUID]`
- `empresa_id`: `Mapped[uuid.UUID]`
- `nom`: `Mapped[str]`
- `tipus`: `Mapped[str]`
- `vehicle_id`: `Mapped[Optional[uuid.UUID]]`
- `adreca`: `Mapped[Optional[str]]`
- `actiu`: `Mapped[bool]`
- `created_at`: `Mapped[datetime]`
- `updated_at`: `Mapped[datetime]`

## EstocMagatzem
- `id`: `Mapped[uuid.UUID]`
- `empresa_id`: `Mapped[uuid.UUID]`
- `article_id`: `Mapped[uuid.UUID]`
- `magatzem_id`: `Mapped[uuid.UUID]`
- `quantitat_fisica`: `Mapped[float]`
- `quantitat_virtual_reservada`: `Mapped[float]`
- `quantitat_cuarentena`: `Mapped[float]`
- `ubicacio_passadis`: `Mapped[Optional[str]]`
- `created_at`: `Mapped[datetime]`
- `updated_at`: `Mapped[datetime]`

## Vehicle
- `id`: `Mapped[uuid.UUID]`
- `empresa_id`: `Mapped[uuid.UUID]`
- `matricula`: `Mapped[str]`
- `marca`: `Mapped[str]`
- `model`: `Mapped[str]`
- `tipus`: `Mapped[str]`
- `horometre_acumulat`: `Mapped[float]`
- `odometre_acumulat`: `Mapped[int]`
- `distintiu_ambiental`: `Mapped[Optional[str]]`
- `estat`: `Mapped[str]`
- `conductor_habitual_id`: `Mapped[Optional[uuid.UUID]]`
- `magatzem_id`: `Mapped[Optional[uuid.UUID]]`
- `data_proxima_itv`: `Mapped[Optional[date]]`
- `created_at`: `Mapped[datetime]`
- `updated_at`: `Mapped[datetime]`

## RegistreEsdevenimentsSIF
- `id`: `Mapped[uuid.UUID]`
- `empresa_id`: `Mapped[uuid.UUID]`
- `codi_esdeveniment`: `Mapped[str]`
- `usuari_id`: `Mapped[Optional[uuid.UUID]]`
- `descripcio`: `Mapped[str]`
- `hash_anterior`: `Mapped[Optional[str]]`
- `hash_sello`: `Mapped[str]`
- `dades_event`: `Mapped[dict[str, Any]]`
- `data_creacio`: `Mapped[datetime]`

## Finca
- `id`: `Mapped[uuid.UUID]`
- `empresa_id`: `Mapped[uuid.UUID]`
- `client_id`: `Mapped[uuid.UUID]`
- `nom`: `Mapped[str]`
- `adreca`: `Mapped[Optional[str]]`
- `codi_candat_en_memoria`: `Mapped[Optional[str]]`
- `dades_sigpac`: `Mapped[dict[str, Any]]`
- `superficie_ha`: `Mapped[Optional[float]]`
- `actiu`: `Mapped[bool]`
- `created_at`: `Mapped[datetime]`
- `updated_at`: `Mapped[datetime]`

## EinaCustodia
- `id`: `Mapped[uuid.UUID]`
- `empresa_id`: `Mapped[uuid.UUID]`
- `referencia_fabricant`: `Mapped[Optional[str]]`
- `nom`: `Mapped[str]`
- `model`: `Mapped[Optional[str]]`
- `numero_serie`: `Mapped[str]`
- `estat`: `Mapped[str]`
- `custodiat_per_operari_id`: `Mapped[Optional[uuid.UUID]]`
- `magatzem_id`: `Mapped[Optional[uuid.UUID]]`
- `data_ultima_calibracio`: `Mapped[Optional[date]]`
- `data_propera_calibracio`: `Mapped[Optional[date]]`
- `created_at`: `Mapped[datetime]`
- `updated_at`: `Mapped[datetime]`

## TiquetCarburant
- `id`: `Mapped[uuid.UUID]`
- `empresa_id`: `Mapped[uuid.UUID]`
- `vehicle_id`: `Mapped[uuid.UUID]`
- `operari_id`: `Mapped[uuid.UUID]`
- `tiquet_foto_path`: `Mapped[str]`
- `odometre_foto_path`: `Mapped[str]`
- `litres`: `Mapped[float]`
- `import_`: `Mapped[float]`
- `data_repostatge`: `Mapped[datetime]`
- `odometre_valor`: `Mapped[int]`
- `estat_ocr`: `Mapped[str]`
- `created_at`: `Mapped[datetime]`
- `updated_at`: `Mapped[datetime]`

## Proveidor
- `id`: `Mapped[uuid.UUID]`
- `empresa_id`: `Mapped[uuid.UUID]`
- `codi`: `Mapped[str]`
- `rao_social`: `Mapped[str]`
- `nif`: `Mapped[str]`
- `telefon`: `Mapped[Optional[str]]`
- `email`: `Mapped[Optional[str]]`
- `especialitat`: `Mapped[str]`
- `es_recc`: `Mapped[bool]`
- `aplica_isp_defecte`: `Mapped[bool]`
- `iban_xifrat_simetric`: `Mapped[Optional[str]]`
- `actiu`: `Mapped[bool]`
- `created_at`: `Mapped[datetime]`
- `updated_at`: `Mapped[datetime]`

## DocumentCAERC
- `id`: `Mapped[uuid.UUID]`
- `empresa_id`: `Mapped[uuid.UUID]`
- `proveidor_id`: `Mapped[uuid.UUID]`
- `tipus_document`: `Mapped[str]`
- `data_caducitat`: `Mapped[date]`
- `fitxer_path`: `Mapped[str]`
- `estat`: `Mapped[str]`
- `created_at`: `Mapped[datetime]`
- `updated_at`: `Mapped[datetime]`

## FacturaProveidor
- `id`: `Mapped[uuid.UUID]`
- `empresa_id`: `Mapped[uuid.UUID]`
- `proveidor_id`: `Mapped[uuid.UUID]`
- `numero_factura`: `Mapped[str]`
- `data_factura`: `Mapped[date]`
- `base_imposable`: `Mapped[float]`
- `quota_iva`: `Mapped[float]`
- `total`: `Mapped[float]`
- `albara_numero`: `Mapped[Optional[str]]`
- `estat`: `Mapped[str]`
- `comanda_numero`: `Mapped[Optional[str]]`
- `estat_conciliacio`: `Mapped[str]`
- `desviacio_percent`: `Mapped[float]`
- `fitxer_pdf_path`: `Mapped[Optional[str]]`
- `created_at`: `Mapped[datetime]`
- `updated_at`: `Mapped[datetime]`

## OrdreTreball
- `id`: `Mapped[uuid.UUID]`
- `empresa_id`: `Mapped[uuid.UUID]`
- `codi`: `Mapped[str]`
- `client_id`: `Mapped[uuid.UUID]`
- `finca_id`: `Mapped[Optional[uuid.UUID]]`
- `titol`: `Mapped[str]`
- `adreca`: `Mapped[str]`
- `descripcio`: `Mapped[Optional[str]]`
- `estat`: `Mapped[str]`
- `data_planificacio`: `Mapped[date]`
- `hora_inici_prevista`: `Mapped[Optional[datetime]]`
- `hora_fi_prevista`: `Mapped[Optional[datetime]]`
- `version_id`: `Mapped[int]`
- `cap_de_colla_id`: `Mapped[Optional[uuid.UUID]]`
- `vehicle_id`: `Mapped[Optional[uuid.UUID]]`
- `created_at`: `Mapped[datetime]`
- `updated_at`: `Mapped[datetime]`

## FullaPicking
- `id`: `Mapped[uuid.UUID]`
- `empresa_id`: `Mapped[uuid.UUID]`
- `ordre_treball_id`: `Mapped[uuid.UUID]`
- `vehicle_id`: `Mapped[Optional[uuid.UUID]]`
- `estat_picking`: `Mapped[str]`
- `created_at`: `Mapped[datetime]`
- `updated_at`: `Mapped[datetime]`

## LiniaPicking
- `id`: `Mapped[uuid.UUID]`
- `empresa_id`: `Mapped[uuid.UUID]`
- `picking_id`: `Mapped[uuid.UUID]`
- `article_id`: `Mapped[uuid.UUID]`
- `quantitat_prevista`: `Mapped[float]`
- `quantitat_carregada_pick_in`: `Mapped[float]`
- `quantitat_retornada_pick_out`: `Mapped[float]`
- `quantitat_mermada`: `Mapped[float]`
- `created_at`: `Mapped[datetime]`
- `updated_at`: `Mapped[datetime]`

## Incidencia
- `id`: `Mapped[uuid.UUID]`
- `empresa_id`: `Mapped[uuid.UUID]`
- `ordre_treball_id`: `Mapped[Optional[uuid.UUID]]`
- `vehicle_id`: `Mapped[Optional[uuid.UUID]]`
- `operari_id`: `Mapped[Optional[uuid.UUID]]`
- `ambit`: `Mapped[str]`
- `estat`: `Mapped[str]`
- `audio_path`: `Mapped[Optional[str]]`
- `foto_path`: `Mapped[Optional[str]]`
- `text_observacions`: `Mapped[Optional[str]]`
- `created_at`: `Mapped[datetime]`
- `updated_at`: `Mapped[datetime]`

## CapaAnotacio
- `id`: `Mapped[uuid.UUID]`
- `empresa_id`: `Mapped[uuid.UUID]`
- `ordre_treball_id`: `Mapped[uuid.UUID]`
- `nom_capa`: `Mapped[str]`
- `fitxer_vectorial_path`: `Mapped[str]`
- `operari_id`: `Mapped[Optional[uuid.UUID]]`
- `estat_capa`: `Mapped[str]`
- `created_at`: `Mapped[datetime]`
- `updated_at`: `Mapped[datetime]`

## FacturaCapcalera
- `id`: `Mapped[uuid.UUID]`
- `empresa_id`: `Mapped[uuid.UUID]`
- `numero_factura`: `Mapped[int]`
- `serie`: `Mapped[str]`
- `client_id`: `Mapped[uuid.UUID]`
- `data_emissio`: `Mapped[datetime]`
- `base_imposable`: `Mapped[float]`
- `quota_iva`: `Mapped[float]`
- `import_retencio`: `Mapped[float]`
- `import_suplits`: `Mapped[float]`
- `liquid_exigible`: `Mapped[float]`
- `estat_cobrament`: `Mapped[str]`
- `estat_enviament`: `Mapped[str]`
- `hash_anterior`: `Mapped[Optional[str]]`
- `hash_sha256`: `Mapped[str]`
- `qr_code_path`: `Mapped[Optional[str]]`
- `pdf_path`: `Mapped[Optional[str]]`
- `created_at`: `Mapped[datetime]`
- `updated_at`: `Mapped[datetime]`

## FacturaLinia
- `id`: `Mapped[uuid.UUID]`
- `empresa_id`: `Mapped[uuid.UUID]`
- `factura_id`: `Mapped[uuid.UUID]`
- `centre_de_cost_id`: `Mapped[Optional[str]]`
- `obra_id`: `Mapped[Optional[uuid.UUID]]`
- `article_id`: `Mapped[Optional[uuid.UUID]]`
- `concepte`: `Mapped[str]`
- `quantitat`: `Mapped[float]`
- `preu_venda_unitari`: `Mapped[float]`
- `tipus_iva`: `Mapped[float]`
- `subtotal`: `Mapped[float]`
- `created_at`: `Mapped[datetime]`

## OutboxEnviamentAEAT
- `id`: `Mapped[uuid.UUID]`
- `empresa_id`: `Mapped[uuid.UUID]`
- `factura_id`: `Mapped[uuid.UUID]`
- `payload_xml_path`: `Mapped[str]`
- `hash_sha256`: `Mapped[str]`
- `intents_enviament`: `Mapped[int]`
- `estat_enviament`: `Mapped[str]`
- `darrera_resposta_soap`: `Mapped[Optional[str]]`
- `data_creacio`: `Mapped[datetime]`
- `data_actualitzacio`: `Mapped[datetime]`

## CarpetaPlanol
- `id`: `Mapped[uuid.UUID]`
- `empresa_id`: `Mapped[uuid.UUID]`
- `nom`: `Mapped[str]`
- `categoria`: `Mapped[str]`
- `client_id`: `Mapped[Optional[uuid.UUID]]`
- `municipi`: `Mapped[Optional[str]]`
- `descripcio`: `Mapped[Optional[str]]`
- `parent_id`: `Mapped[Optional[uuid.UUID]]`
- `created_at`: `Mapped[datetime]`
- `updated_at`: `Mapped[datetime]`

## PlanolBase
- `id`: `Mapped[uuid.UUID]`
- `empresa_id`: `Mapped[uuid.UUID]`
- `carpeta_id`: `Mapped[uuid.UUID]`
- `client_id`: `Mapped[Optional[uuid.UUID]]`
- `titol`: `Mapped[str]`
- `codi_referencia`: `Mapped[str]`
- `tipus_fitxer`: `Mapped[str]`
- `es_georeferenciat`: `Mapped[bool]`
- `fitxer_path`: `Mapped[str]`
- `mida_bytes`: `Mapped[int]`
- `bounds_wgs84`: `Mapped[Optional[dict]]`
- `projeccio_origen`: `Mapped[str]`
- `created_at`: `Mapped[datetime]`
- `updated_at`: `Mapped[datetime]`

## CapaVectorial
- `id`: `Mapped[uuid.UUID]`
- `empresa_id`: `Mapped[uuid.UUID]`
- `planol_base_id`: `Mapped[uuid.UUID]`
- `nom`: `Mapped[str]`
- `disciplina`: `Mapped[str]`
- `ordre_treball_id`: `Mapped[Optional[uuid.UUID]]`
- `es_immutable`: `Mapped[bool]`
- `color_hex`: `Mapped[str]`
- `gruix_linia`: `Mapped[int]`
- `opacitat_percent`: `Mapped[int]`
- `visible`: `Mapped[bool]`
- `geometries_geojson`: `Mapped[dict]`
- `version_id`: `Mapped[int]`
- `creat_per_usuari_id`: `Mapped[Optional[uuid.UUID]]`
- `created_at`: `Mapped[datetime]`
- `updated_at`: `Mapped[datetime]`

## PinIncidenciaPlanol
- `id`: `Mapped[uuid.UUID]`
- `empresa_id`: `Mapped[uuid.UUID]`
- `capa_id`: `Mapped[uuid.UUID]`
- `latitud`: `Mapped[float]`
- `longitud`: `Mapped[float]`
- `titol`: `Mapped[str]`
- `descripcio`: `Mapped[Optional[str]]`
- `simbol`: `Mapped[str]`
- `estat`: `Mapped[str]`
- `audio_nota_path`: `Mapped[Optional[str]]`
- `foto_evidencia_path`: `Mapped[Optional[str]]`
- `operari_id`: `Mapped[Optional[uuid.UUID]]`
- `created_at`: `Mapped[datetime]`

## ExportacioPdfPlanol
- `id`: `Mapped[uuid.UUID]`
- `empresa_id`: `Mapped[uuid.UUID]`
- `planol_base_id`: `Mapped[uuid.UUID]`
- `titol_report`: `Mapped[str]`
- `client_id`: `Mapped[Optional[uuid.UUID]]`
- `capes_incloses_ids`: `Mapped[List[uuid.UUID]]`
- `escala_grafica`: `Mapped[str]`
- `pdf_generat_path`: `Mapped[Optional[str]]`
- `estat`: `Mapped[str]`
- `caixeti_dades`: `Mapped[Optional[dict]]`
- `created_at`: `Mapped[datetime]`

## TokenInvitacioTelegram
- `id`: `Mapped[uuid.UUID]`
- `empresa_id`: `Mapped[uuid.UUID]`
- `client_id`: `Mapped[uuid.UUID]`
- `token_hash`: `Mapped[str]`
- `expira_a`: `Mapped[datetime]`
- `utilitzat`: `Mapped[bool]`
- `utilitzat_a`: `Mapped[Optional[datetime]]`
- `created_at`: `Mapped[datetime]`

## ConversaNotificacio
- `id`: `Mapped[uuid.UUID]`
- `empresa_id`: `Mapped[uuid.UUID]`
- `client_id`: `Mapped[uuid.UUID]`
- `ordre_treball_id`: `Mapped[Optional[uuid.UUID]]`
- `estat`: `Mapped[str]`
- `titol`: `Mapped[str]`
- `ultim_missatge_text`: `Mapped[Optional[str]]`
- `ultim_missatge_data`: `Mapped[datetime]`
- `num_missatges_sense_llegir`: `Mapped[int]`
- `es_arxivada`: `Mapped[bool]`
- `created_at`: `Mapped[datetime]`
- `updated_at`: `Mapped[datetime]`

## MissatgeNotificacio
- `id`: `Mapped[uuid.UUID]`
- `empresa_id`: `Mapped[uuid.UUID]`
- `conversa_id`: `Mapped[uuid.UUID]`
- `remitent_tipus`: `Mapped[str]`
- `remitent_usuari_id`: `Mapped[Optional[uuid.UUID]]`
- `canal`: `Mapped[str]`
- `contingut_text`: `Mapped[str]`
- `tipus_esdeveniment`: `Mapped[str]`
- `adjunt_url`: `Mapped[Optional[str]]`
- `adjunt_tipus`: `Mapped[Optional[str]]`
- `adjunt_mida_bytes`: `Mapped[Optional[int]]`
- `token_aprobacio`: `Mapped[Optional[str]]`
- `estat_aprobacio`: `Mapped[str]`
- `token_descarrega_factura`: `Mapped[Optional[str]]`
- `token_descarrega_expira_a`: `Mapped[Optional[datetime]]`
- `created_at`: `Mapped[datetime]`

## FaqCorporativaRag
- `id`: `Mapped[uuid.UUID]`
- `empresa_id`: `Mapped[uuid.UUID]`
- `pregunta`: `Mapped[str]`
- `resposta`: `Mapped[str]`
- `categoria`: `Mapped[str]`
- `paraules_clau`: `Mapped[Optional[str]]`
- `actiu`: `Mapped[bool]`
- `created_at`: `Mapped[datetime]`

## MemorandumTecnicCopilot
- `id`: `Mapped[uuid.UUID]`
- `empresa_id`: `Mapped[uuid.UUID]`
- `ordre_treball_id`: `Mapped[Optional[uuid.UUID]]`
- `incidencia_id`: `Mapped[Optional[uuid.UUID]]`
- `transcripcio_audio`: `Mapped[Optional[str]]`
- `confianca_acustica`: `Mapped[float]`
- `avis_soroll_sever`: `Mapped[bool]`
- `analisi_visual`: `Mapped[Optional[str]]`
- `dictamen_pericial`: `Mapped[str]`
- `motiu_dictamen`: `Mapped[str]`
- `estimacio_temps_extra_minuts`: `Mapped[int]`
- `estimacio_materials_extra`: `Mapped[list]`
- `cost_estimat_total`: `Mapped[float]`
- `validat_per_enginyer`: `Mapped[bool]`
- `enginyer_validador_id`: `Mapped[Optional[uuid.UUID]]`
- `data_validacio`: `Mapped[Optional[datetime]]`
- `observacions_enginyer`: `Mapped[Optional[str]]`
- `estat`: `Mapped[str]`
- `created_at`: `Mapped[datetime]`
- `updated_at`: `Mapped[datetime]`

## AuditoriaPostObra
- `id`: `Mapped[uuid.UUID]`
- `empresa_id`: `Mapped[uuid.UUID]`
- `ordre_treball_id`: `Mapped[uuid.UUID]`
- `desviacio_hores`: `Mapped[float]`
- `desviacio_materials`: `Mapped[list]`
- `desviacio_km`: `Mapped[float]`
- `despeses_camp`: `Mapped[float]`
- `marge_previst_percentatge`: `Mapped[float]`
- `marge_real_liquidat_percentatge`: `Mapped[float]`
- `alerta_merma_operativa`: `Mapped[bool]`
- `detall_merma`: `Mapped[Optional[str]]`
- `bloqueig_consum_excessiu`: `Mapped[bool]`
- `bloqueig_sync_pendent`: `Mapped[bool]`
- `pressupost_corregit_proposta`: `Mapped[dict]`
- `estat`: `Mapped[str]`
- `enginyer_id`: `Mapped[Optional[uuid.UUID]]`
- `data_aprovacio`: `Mapped[Optional[datetime]]`
- `created_at`: `Mapped[datetime]`
- `updated_at`: `Mapped[datetime]`

## AlertaGarantiaRecompra
- `id`: `Mapped[uuid.UUID]`
- `empresa_id`: `Mapped[uuid.UUID]`
- `ordre_treball_id`: `Mapped[Optional[uuid.UUID]]`
- `tipus_alerta`: `Mapped[str]`
- `article_id`: `Mapped[Optional[uuid.UUID]]`
- `numero_serie`: `Mapped[Optional[str]]`
- `proveidor_id`: `Mapped[Optional[uuid.UUID]]`
- `missatge`: `Mapped[str]`
- `data_fi_garantia`: `Mapped[Optional[date]]`
- `estat`: `Mapped[str]`
- `dades_comanda_proposta`: `Mapped[dict]`
- `created_at`: `Mapped[datetime]`
- `updated_at`: `Mapped[datetime]`

## ConsultaXatCopilot
- `id`: `Mapped[uuid.UUID]`
- `empresa_id`: `Mapped[uuid.UUID]`
- `usuari_id`: `Mapped[uuid.UUID]`
- `pregunta`: `Mapped[str]`
- `resposta`: `Mapped[str]`
- `vertical`: `Mapped[str]`
- `node_ia_actiu`: `Mapped[bool]`
- `node_ia_url`: `Mapped[Optional[str]]`
- `feature_copilot_ia`: `Mapped[bool]`
- `feature_flota`: `Mapped[bool]`
- `feature_planols`: `Mapped[bool]`
- `feature_telegram`: `Mapped[bool]`
- `data_onboarding`: `Mapped[datetime]`
- `temps_inferencia_ms`: `Mapped[int]`
- `enllacos_relacionats`: `Mapped[list]`
- `es_error_timeout`: `Mapped[bool]`
- `denegat_per_rol`: `Mapped[bool]`
- `tool_name`: `Mapped[Optional[str]]`
- `tool_args`: `Mapped[Optional[dict]]`
- `tool_result`: `Mapped[Optional[dict]]`
- `created_at`: `Mapped[datetime]`

## MovimentEstoc
- `id`: `Mapped[uuid.UUID]`
- `empresa_id`: `Mapped[uuid.UUID]`
- `magatzem_id`: `Mapped[uuid.UUID]`
- `article_id`: `Mapped[uuid.UUID]`
- `tipus_moviment`: `Mapped[str]`
- `quantitat`: `Mapped[float]`
- `referencia_document`: `Mapped[Optional[str]]`
- `notes`: `Mapped[Optional[str]]`
- `usuari_id`: `Mapped[Optional[uuid.UUID]]`
- `created_at`: `Mapped[datetime]`

## AlbaraProveidor
- `id`: `Mapped[uuid.UUID]`
- `empresa_id`: `Mapped[uuid.UUID]`
- `proveidor_id`: `Mapped[uuid.UUID]`
- `numero_albara`: `Mapped[str]`
- `data_albara`: `Mapped[date]`
- `fitxer_path`: `Mapped[Optional[str]]`
- `created_at`: `Mapped[datetime]`

## FacturaProveidorLinia
- `id`: `Mapped[uuid.UUID]`
- `empresa_id`: `Mapped[uuid.UUID]`
- `factura_id`: `Mapped[uuid.UUID]`
- `article_id`: `Mapped[Optional[uuid.UUID]]`
- `quantitat`: `Mapped[float]`
- `preu_unitari`: `Mapped[float]`

## Pressupost
- `id`: `Mapped[uuid.UUID]`
- `empresa_id`: `Mapped[uuid.UUID]`
- `client_id`: `Mapped[uuid.UUID]`
- `numero`: `Mapped[str]`
- `total`: `Mapped[float]`
- `estat`: `Mapped[str]`
- `token_signatura`: `Mapped[Optional[str]]`
- `created_at`: `Mapped[datetime]`
- `updated_at`: `Mapped[datetime]`

