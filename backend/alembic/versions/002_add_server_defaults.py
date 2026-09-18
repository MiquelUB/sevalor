"""Add server defaults for all required columns and update vertical enum

Revision ID: 002_add_server_defaults
Revises: baseline_esquema
Create Date: 2026-09-18 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '002_add_server_defaults'
down_revision: Union[str, None] = 'baseline_esquema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add server_default to empreses.vertical
    op.alter_column('empreses', 'vertical', server_default='SEVALOR')
    
    # Add gen_random_uuid() to all UUID primary keys
    tables = [
        'empreses', 'usuaris', 'sessions_operari', 'api_keys',
        'clients', 'finques', 'historic_noms_finques', 'articles',
        'magatzems', 'estocs_magatzem', 'moviments_estoc', 'vehicles',
        'revisions_vehicles', 'historic_assignacions_vehicles',
        'proveidors', 'certificats_cae', 'ordres_treball', 'incidencies_ot',
        'fotos_incidencia', 'materials_ot', 'operaris_ot', 'jornades_operari',
        'picking_materials', 'tiquets_carburant', 'factures', 'pagaments',
        'factures_proveidor', 'notificacions', 'missatges_conversa',
        'converses_suport', 'projectes_planols', 'capes_vectorials',
        'marcadors_planol', 'projectes_superadmin', 'sif_inmutable_log'
    ]
    for table in tables:
        try:
            op.alter_column(table, 'id', server_default=sa.text('gen_random_uuid()'))
        except Exception:
            pass


def downgrade() -> None:
    pass
