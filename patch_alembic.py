import re

with open('backend/alembic/versions/10fc5e1f1e4f_add_missing_phase4_tables.py', 'r') as f:
    content = f.read()

import_str = "from sqlalchemy.engine.reflection import Inspector\n"
if "Inspector" not in content:
    content = content.replace("import sqlalchemy as sa", "import sqlalchemy as sa\n" + import_str)

upgrade_logic = """def upgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    tables = inspector.get_table_names()
    
    if 'albarans_proveidor' not in tables:
        op.create_table('albarans_proveidor',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('empresa_id', sa.UUID(), nullable=False),
        sa.Column('proveidor_id', sa.UUID(), nullable=False),
        sa.Column('numero_albara', sa.String(length=100), nullable=False),
        sa.Column('data_albara', sa.Date(), nullable=False),
        sa.Column('fitxer_path', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['empresa_id'], ['empreses.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['proveidor_id'], ['proveidors.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('empresa_id', 'proveidor_id', 'numero_albara', name='uq_albarans_prov_empresa_num')
        )
        
    if 'moviments_estoc' not in tables:
        op.create_table('moviments_estoc',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('empresa_id', sa.UUID(), nullable=False),
        sa.Column('magatzem_id', sa.UUID(), nullable=False),
        sa.Column('article_id', sa.UUID(), nullable=False),
        sa.Column('tipus_moviment', sa.String(length=20), nullable=False),
        sa.Column('quantitat', sa.Numeric(precision=12, scale=3), nullable=False),
        sa.Column('referencia_document', sa.String(length=100), nullable=True),
        sa.Column('notes', sa.String(length=200), nullable=True),
        sa.Column('usuari_id', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['article_id'], ['articles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['empresa_id'], ['empreses.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['magatzem_id'], ['magatzems.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
        )
        
    if 'factures_proveidor_linies' not in tables:
        op.create_table('factures_proveidor_linies',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('empresa_id', sa.UUID(), nullable=False),
        sa.Column('factura_id', sa.UUID(), nullable=False),
        sa.Column('article_id', sa.UUID(), nullable=True),
        sa.Column('quantitat', sa.Numeric(precision=12, scale=3), nullable=True),
        sa.Column('preu_unitari', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.ForeignKeyConstraint(['article_id'], ['articles.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['empresa_id'], ['empreses.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['factura_id'], ['factures_proveidor.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
        )
"""

content = re.sub(r'def upgrade\(\) -> None:.*?(?=def downgrade\(\) -> None:)', upgrade_logic, content, flags=re.DOTALL)

with open('backend/alembic/versions/10fc5e1f1e4f_add_missing_phase4_tables.py', 'w') as f:
    f.write(content)
