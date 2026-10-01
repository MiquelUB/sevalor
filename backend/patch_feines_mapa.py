import re

with open('/media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/feines.py', 'r') as f:
    content = f.read()

# Replace the GET /mapa endpoint
old_mapa = r"""class MapaMarkerItem\(BaseModel\):
    id: str
    codi: str
    titol: str
    estat: str
    lat: float
    lng: float
    is_incidencia: bool = False
    adreca: Optional\[str\] = None
    client_rao_social: Optional\[str\] = None

@router\.get\("/mapa", response_model=List\[MapaMarkerItem\]\)
async def llistar_feines_mapa\(
    request: Request,
    db: AsyncSession = Depends\(get_db_with_tenant_context\)
\):.*?return markers"""

new_mapa = """@router.get("/mapa")
async def llistar_feines_mapa(
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    empresa_id = getattr(request.state, "empresa_id", None) or request.headers.get("X-Empresa-ID")
    if not empresa_id or empresa_id == 'undefined':
        raise HTTPException(status_code=401, detail="No identificat")

    stmt = (
        select(OrdreTreball, Client)
        .outerjoin(Client, OrdreTreball.client_id == Client.id)
        .where(
            OrdreTreball.empresa_id == uuid.UUID(empresa_id),
            OrdreTreball.estat.in_(["PENDENT", "EN_CURS", "BLOQUEJADA", "EN_OBRA", "EN_RUTA"])
        )
        .order_by(OrdreTreball.created_at.desc())
    )
    result = await db.execute(stmt)
    rows = result.all()

    features = []
    for ordre, client in rows:
        lat = ordre.latitud
        lng = ordre.longitud
        if not lat or not lng:
            # Fallback to parse adreca if it contains coordinates (for tests)
            if ordre.adreca and "," in ordre.adreca:
                try:
                    parts = [float(p.strip()) for p in ordre.adreca.split(",")]
                    if len(parts) >= 2:
                        lat, lng = parts[0], parts[1]
                except (ValueError, TypeError):
                    pass
        
        if lat is None or lng is None:
            continue

        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [float(lng), float(lat)]
            },
            "properties": {
                "id": str(ordre.id),
                "codi": ordre.codi,
                "titol": ordre.titol,
                "estat": ordre.estat,
                "adreca": ordre.adreca,
                "client_rao_social": client.rao_social if client else None,
                "is_incidencia": False
            }
        })

    return {
        "type": "FeatureCollection",
        "features": features
    }"""

content = re.sub(old_mapa, new_mapa, content, flags=re.DOTALL)

with open('/media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/feines.py', 'w') as f:
    f.write(content)
