
with open("app/api/v1/gestio/magatzem.py", "r") as f:
    content = f.read()

old_picking = """        if payload.quantitat_prevista > disponible:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Stock insuficient per a l'article. Necessitat: {payload.quantitat_prevista}, Disponible: {disponible}",
            )"""

new_picking = """        if payload.quantitat_prevista > disponible:
            from app.api.v1.gestio.copilot import cridar_lm_studio
            # RF-18 / RF-33: Intervenció del Copilot per avaluar Backorders o falta d'estoc
            avís_ia = await cridar_lm_studio(
                pregunta=f"S'ha intentat extreure {payload.quantitat_prevista} unitats de l'article {estoc.article_id}, però només hi ha {disponible} disponibles físicament. Si no hi ha comandes en trànsit, adverteix el cap de magatzem de forma tècnica i concisa.",
                vertical="LOGISTICA",
                context_addicional="El teu objectiu és bloquejar el picking i advertir del trencament d'estoc."
            )
            if not avís_ia:
                avís_ia = f"Comanda amb entrega parcial detectada (falta estoc): {disponible} unitats disponibles físiques. Bloqueig de picking matinal activat (Copilot Offline)."
                
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"❌ Copilot IA: {avís_ia}",
            )"""

content = content.replace(old_picking, new_picking)

with open("app/api/v1/gestio/magatzem.py", "w") as f:
    f.write(content)
