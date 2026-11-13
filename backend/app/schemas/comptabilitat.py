import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


# --- DTOs SANITITZATS PER A ENGINYERIA (RESOLUCIÓ C-05 ZERO-TRUST) ---
class ClientRiscSanititzatDTO(BaseModel):
    """Retorna únicament l'estat operatiu i el cost hora teòric, sense revelar € de deute ni IBAN."""

    client_id: uuid.UUID
    estat_risc_operatiu: str
    pot_obrir_ot_i_picking: bool
    missatge_operatiu: str


class FacturaConsultaTecnicaDTO(BaseModel):
    """DTO purgat per a consulta des d'obres per part de l'Enginyer (RF-05.4)."""

    id: uuid.UUID
    numero_factura: int
    serie: str
    data_emissio: datetime
    estat_document: str
    descripcions_linies: List[str]


# --- DTOs D'EMISSIÓ DE FACTURA VERI*FACTU ---
class FacturaLiniaCreateDTO(BaseModel):
    obra_id: Optional[uuid.UUID] = None
    centre_de_cost_id: str = "CC-GENERAL"
    article_id: Optional[uuid.UUID] = None
    concepte: str
    compte_pgc: str = "700000"
    quantitat: Decimal = Field(gt=Decimal("0"))
    quantitat_merma: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0"))
    preu_venda_unitari: Decimal = Field(ge=Decimal("0"))
    descompte_aplicat_pct: Decimal = Field(
        default=Decimal("0.00"), ge=Decimal("0"), le=Decimal("100")
    )
    tipus_iva_pct: Decimal = Field(default=Decimal("21.00"))


class FacturaEmissioCreateDTO(BaseModel):
    client_id: uuid.UUID
    serie: str = "F"
    data_emissio: date
    data_venciment: date
    metode_pagament: str = "TRANSFERENCIA"
    es_inversio_subjecte_passiu: bool = False
    retencio_irpf_pct: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0"))
    retencio_garantia_pct: Decimal = Field(
        default=Decimal("0.00"), ge=Decimal("0"), le=Decimal("20")
    )
    justificant_suplerts_pdf_path: Optional[str] = None
    factura_rectificada_id: Optional[uuid.UUID] = None
    motiu_rectificacio: Optional[str] = None
    linies: List[FacturaLiniaCreateDTO]


# --- DTOs DE LES 6 MILLORES I SUITE ECONÒMICA ---
class WIPItemDTO(BaseModel):
    ordre_treball_id: uuid.UUID
    codi_ot: str
    client_id: uuid.UUID
    dies_en_wip: int
    valor_wip_pvp: Decimal
    cost_wip_avancat: Decimal
    es_wip_envellit_alerta: bool


class WIPControlResponseDTO(BaseModel):
    total_wip_valorat_pvp: Decimal
    total_cost_wip_avancat: Decimal
    nombre_ots_en_wip: int
    nombre_ots_envellides_critiques: int
    items: List[WIPItemDTO]


class RetencioGarantiaDTO(BaseModel):
    id: uuid.UUID
    tipus: str
    factura_client_id: Optional[uuid.UUID] = None
    import_retingut: Decimal
    data_retencio: date
    data_venciment_garantia: date
    dies_fins_venciment: int
    estat: str
    alerta_venciment_proper: bool


class OverrideRiscRequestDTO(BaseModel):
    motiu: str = Field(min_length=5, max_length=500)


class Art80ReclamacioRequestDTO(BaseModel):
    justificant_notarial_path: str = Field(min_length=3, max_length=500)


class Art80ItemDTO(BaseModel):
    factura_id: uuid.UUID
    numero_factura: int
    serie: str
    client_id: uuid.UUID
    data_emissio: date
    data_limit_art80: date
    base_imposable: Decimal
    quota_iva: Decimal
    dies_impagada: int
    estat_art80: str


class TiquetAuditoriaRequestDTO(BaseModel):
    accio: str  # APROVAT, REBUTJAT
    custodia_paper_confirmada: Optional[bool] = None
    ordre_treball_id: Optional[uuid.UUID] = None


class TiquetDespesaResponseDTO(BaseModel):
    id: uuid.UUID
    categoria: str
    usuari_id: uuid.UUID
    vehicle_id: Optional[uuid.UUID] = None
    ordre_treball_id: Optional[uuid.UUID] = None
    data_tiquet: date
    nif_emissor: Optional[str] = None
    rao_social: Optional[str] = None
    base_imposable: Decimal
    iva_pct: Decimal
    quota_iva: Decimal
    import_total: Decimal
    estat_aprovacio: str
    estat_fiscal: str
    requereix_aprovacio_boss: bool
    custodia_paper_confirmada: bool


class Norma43ConciliarRequestDTO(BaseModel):
    contingut_c43: str = Field(min_length=10)
    confirmar_conciliacio_hitl: bool = False


class Norma43MovimentDTO(BaseModel):
    data_operacio: date
    concepte: str
    import_moviment: Decimal
    saldo_resultant: Decimal
    huella_sha256: str
    duplicat_rebutjat: bool = False
    factura_suggerida_id: Optional[uuid.UUID] = None


class OperariCostEfectiuDTO(BaseModel):
    usuari_id: uuid.UUID
    nom_complet: str
    cost_hora_referencia: Decimal
    salari_brut_i_ss_visible: Optional[str]  # "***" per a Secretaria si és Alta Direcció
    hores_fitxades_mes: Decimal
    hores_imputades_ot_mes: Decimal
    ratio_eficiencia_pct: Decimal
    cost_hora_efectiu_mensual: Optional[Decimal]
    alerta_improductivitat: bool


class ContracteMRRAuditoriaDTO(BaseModel):
    contracte_id: uuid.UUID
    codi_contracte: str
    client_id: uuid.UUID
    quota_mensual_mrr: Decimal
    cost_real_ots_periode: Decimal
    marge_net_contracte: Decimal
    sinistralitat_pct: Decimal
    semafor: str  # RENDIBLE, ALERTA_EROSIO, DEFICITARI_CRITIC


class AlertaErosioMargeDTO(BaseModel):
    article_id: uuid.UUID
    referencia: str
    nom: str
    preu_cost_mitja: Decimal
    preu_cost_ultim: Decimal
    preu_venda_tarifa: Decimal
    marge_actual_pct: Decimal
    llindar_minim_pct: Decimal


class DashboardEconomicResponseDTO(BaseModel):
    # Bloc A: P&L i Break-Even
    facturacio_neta: Decimal
    cost_directe_obra: Decimal
    marge_brut_eur: Decimal
    marge_brut_pct: Decimal
    despeses_fixes_estructura: Decimal
    ebitda_operatiu_eur: Decimal
    ebitda_operatiu_pct: Decimal
    break_even_facturacio_necessaria: Decimal
    break_even_assolit: bool

    # Bloc B: Marges de Producte i Estoc
    alertes_erosio_marge: List[AlertaErosioMargeDTO]
    capital_immobilitzat_90d_eur: Decimal

    # Bloc C: Tresoreria 30/60/90d i Guardacaixa IVA
    cash_flow_operatiu_real: Decimal
    burn_rate_mes_seguent: Decimal
    guardacaixa_fiscal_iva_303: Decimal
    projeccio_tresoreria_30d: Decimal
    projeccio_tresoreria_60d: Decimal
    projeccio_tresoreria_90d: Decimal
    dso_dies_mitjana_cobrament: Decimal
    aging_impagats: Dict[str, Decimal]
    total_retencions_garantia_4308_excloses_aging: Decimal

    # Bloc D & E: Flota, MRR i Risc Pareto
    cost_flota_eur_km_mitja: Decimal
    mrr_mensual_actiu: Decimal
    cobertura_estructura_mrr_pct: Decimal
    alerta_concentracio_pareto_25pct: bool
    waterfall_mensual: Dict[str, Decimal]
    evolucio_12m: List[Dict[str, object]]
    marges_per_vertical: List[Dict[str, object]]
