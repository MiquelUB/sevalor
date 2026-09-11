"""Tests d'integració d'aïllament multi-tenant amb Row Level Security (RLS) de PostgreSQL."""

import unittest
import uuid
from sqlalchemy import select, text

from app.core.db import AsyncSessionLocal, set_tenant_context
from app.models.models import Client, Empresa


class TestMultiTenantRLS(unittest.IsolatedAsyncioTestCase):
    """Verifica que les polítiques RLS de PostgreSQL bloquegen de forma estricta l'accés entre inquilins."""

    async def asyncSetUp(self):
        """Prepara dos inquilins i dos clients associats amb privilegis administratius."""
        async with AsyncSessionLocal() as session:
            await set_tenant_context(session, None, is_superadmin=True)

            self.empresa_a = Empresa(
                id=uuid.uuid4(),
                nom="Instal·lacions Agràries A, SL",
                nif=f"B{uuid.uuid4().hex[:8].upper()}",
                subdomini=f"empresa-a-{uuid.uuid4().hex[:6]}",
            )
            self.empresa_b = Empresa(
                id=uuid.uuid4(),
                nom="Sistemes de Reg B, SL",
                nif=f"B{uuid.uuid4().hex[:8].upper()}",
                subdomini=f"empresa-b-{uuid.uuid4().hex[:6]}",
            )
            session.add_all([self.empresa_a, self.empresa_b])
            await session.flush()

            self.client_a = Client(
                id=uuid.uuid4(),
                empresa_id=self.empresa_a.id,
                codi="CLI-0001",
                rao_social="Finca Oliveres Mas Nou",
                nif="A11111111",
            )
            self.client_b = Client(
                id=uuid.uuid4(),
                empresa_id=self.empresa_b.id,
                codi="CLI-0001",
                rao_social="Celler Vall de Roures",
                nif="B22222222",
            )
            session.add_all([self.client_a, self.client_b])
            await session.commit()

    async def test_tenant_isolation_rls(self):
        """Verifica que l'Inquilí A mai veu les dades de l'Inquilí B sota cap circumstància."""
        # 1. Sessió autenticada com a Inquilí A
        async with AsyncSessionLocal() as session_a:
            await set_tenant_context(session_a, self.empresa_a.id, is_superadmin=False)

            # Consulta general: només ha de retornar el client de l'Empresa A
            result_all = await session_a.execute(select(Client))
            clients_visibles = result_all.scalars().all()

            self.assertEqual(len(clients_visibles), 1)
            self.assertEqual(clients_visibles[0].id, self.client_a.id)
            self.assertEqual(clients_visibles[0].empresa_id, self.empresa_a.id)

            # Intent d'accés fraudulent directe al client de l'Inquilí B per ID
            result_b = await session_a.execute(select(Client).where(Client.id == self.client_b.id))
            client_fraudulent = result_b.scalars().all()

            # Assert d'èxit: Ha de retornar una llista buida []
            self.assertEqual(client_fraudulent, [])

        # 2. Sessió autenticada com a Inquilí B
        async with AsyncSessionLocal() as session_b:
            await set_tenant_context(session_b, self.empresa_b.id, is_superadmin=False)

            # Consulta general: només ha de veure els clients de l'Empresa B
            result_all_b = await session_b.execute(select(Client))
            clients_visibles_b = result_all_b.scalars().all()

            self.assertEqual(len(clients_visibles_b), 1)
            self.assertEqual(clients_visibles_b[0].id, self.client_b.id)
            self.assertEqual(clients_visibles_b[0].empresa_id, self.empresa_b.id)

            # Intent d'accés al client de l'Inquilí A des de l'Inquilí B
            result_a_from_b = await session_b.execute(select(Client).where(Client.id == self.client_a.id))
            self.assertEqual(result_a_from_b.scalars().all(), [])


if __name__ == "__main__":
    unittest.main()
