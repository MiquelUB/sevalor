import uuid

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token
from app.models.models import Empresa, Usuari


@pytest.mark.asyncio
async def test_gestio_configuracio_retorna_subdomini_i_adreca_reals(
    async_client: AsyncClient, db_session
):
    """Verifica que /gestio/configuracio/empresa retorna el subdomini, domini_custom i adreça reals sota RLS."""
    emp_id = uuid.uuid4()
    sub_real = f"sevalormante-{emp_id.hex[:6]}"
    nif_emp = f"B{uuid.uuid4().int % 10000000:07d}A"

    emp = Empresa(
        id=emp_id,
        nom="Sevalormante SL",
        nif=nif_emp,
        adreca="Polígon Industrial Sud, Nau 4, Amposta",
        subdomini=sub_real,
        domini_custom=f"app.{sub_real}.cat",
    )
    db_session.add(emp)

    user_id = uuid.uuid4()
    boss = Usuari(
        id=user_id,
        empresa_id=emp_id,
        nif="47891234X",
        nom="Miquel",
        cognoms="pons",
        email=f"miquel_{emp_id.hex[:6]}@sevalormante.cat",
        telefon="+34611223344",
        rol="BOSS",
        estat="ACTIU",
        totp_activat=True,
    )
    db_session.add(boss)
    await db_session.commit()

    token = create_access_token(
        {"sub": str(user_id), "empresa_id": str(emp_id), "rol": "BOSS", "totp_activat": True}
    )
    resp = await async_client.get(
        "/api/v1/gestio/configuracio/empresa",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["subdomini"] == sub_real
    assert body["domini_custom"] == f"app.{sub_real}.cat"
    assert body["adreca"] == "Polígon Industrial Sud, Nau 4, Amposta"
    assert "penedes" not in str(body).lower()
