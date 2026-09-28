path = "/media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/magatzem.py"
with open(path, "r") as f:
    text = f.read()

target = """        for linia in payload.linies:
            stmt_art = select(Article).where(Article.referencia_inventari == linia.referencia)
            article = (await db.execute(stmt_art)).scalars().first()

            nou_preu = float(linia.preu) * (1.0 - (float(linia.descompte_percent)/100.0))
            if not article:
                article = Article(
                    empresa_id=empresa_id,
                    referencia_inventari=linia.referencia,
                    nom=linia.nom,
                    unitat_mesura="UNITAT",
                    familia="EINA" if linia.tipus == "EINA" else "GENERAL",
                    preu_cost=nou_preu
                )
                db.add(article)
                await db.flush()
                articles_creats += 1
            else:
                # Calcular PMP (Preu Mitjà Ponderat)
                estoc_res = await db.execute(select(EstocMagatzem).where(EstocMagatzem.article_id == article.id))
                estocs_actuals = estoc_res.scalars().all()
                estoc_total_actual = sum(float(e.quantitat_fisica) for e in estocs_actuals)

                if estoc_total_actual + float(linia.quantitat) > 0 and nou_preu > 0:
                    valor_actual = estoc_total_actual * float(article.preu_cost)
                    valor_entrada = float(linia.quantitat) * nou_preu
                    pmp = (valor_actual + valor_entrada) / (estoc_total_actual + float(linia.quantitat))
                    article.preu_cost = pmp
                elif nou_preu > 0 and estoc_total_actual <= 0:
                    article.preu_cost = nou_preu
            stmt_estoc = select(EstocMagatzem).where(EstocMagatzem.magatzem_id == magatzem.id, EstocMagatzem.article_id == article.id)
            estoc = (await db.execute(stmt_estoc)).scalars().first()
            if not estoc:
                estoc = EstocMagatzem(
                    empresa_id=empresa_id,
                    magatzem_id=magatzem.id,
                    article_id=article.id,
                    quantitat_fisica=0.0
                )
                db.add(estoc)
                await db.flush()

            moviment = MovimentEstoc(
                empresa_id=empresa_id,
                magatzem_id=magatzem.id,
                article_id=article.id,
                tipus_moviment="ENTRADA",
                quantitat=linia.quantitat,
                usuari_id=None,
                referencia_document=payload.numero_document,
                notes="Albarà Proveïdor OCR"
            )
            db.add(moviment)
            estoc.quantitat_fisica = float(estoc.quantitat_fisica) + linia.quantitat
            moviments_creats += 1

        await db.commit()"""

replacement = """        for linia in payload.linies:
            nou_preu = float(linia.preu) * (1.0 - (float(linia.descompte_percent)/100.0))
            
            if linia.tipus == "EINA":
                # Spec 004 RF-07: Les Eines es custodien per Serial Number i no sumen stock genèric d'Article
                import uuid
                quantitat = int(linia.quantitat) if linia.quantitat > 0 else 1
                for _ in range(quantitat):
                    eina_ocr = EinaCustodia(
                        empresa_id=empresa_id,
                        referencia_fabricant=linia.referencia,
                        nom=linia.nom,
                        model="OCR pendent revisió",
                        numero_serie=f"PENDENT_SN_{uuid.uuid4().hex[:8].upper()}",
                        estat="DISPONIBLE"
                    )
                    db.add(eina_ocr)
                await db.flush()
                # Les eines no sumen al moviment d'estoc de materials ni al preu PMP.
                continue

            stmt_art = select(Article).where(Article.referencia_inventari == linia.referencia)
            article = (await db.execute(stmt_art)).scalars().first()

            if not article:
                article = Article(
                    empresa_id=empresa_id,
                    referencia_inventari=linia.referencia,
                    nom=linia.nom,
                    unitat_mesura="UNITAT",
                    familia="GENERAL",
                    preu_cost=nou_preu
                )
                db.add(article)
                await db.flush()
                articles_creats += 1
            else:
                # Calcular PMP (Preu Mitjà Ponderat)
                estoc_res = await db.execute(select(EstocMagatzem).where(EstocMagatzem.article_id == article.id))
                estocs_actuals = estoc_res.scalars().all()
                estoc_total_actual = sum(float(e.quantitat_fisica) for e in estocs_actuals)

                if estoc_total_actual + float(linia.quantitat) > 0 and nou_preu > 0:
                    valor_actual = estoc_total_actual * float(article.preu_cost)
                    valor_entrada = float(linia.quantitat) * nou_preu
                    pmp = (valor_actual + valor_entrada) / (estoc_total_actual + float(linia.quantitat))
                    article.preu_cost = pmp
                elif nou_preu > 0 and estoc_total_actual <= 0:
                    article.preu_cost = nou_preu
            
            stmt_estoc = select(EstocMagatzem).where(EstocMagatzem.magatzem_id == magatzem.id, EstocMagatzem.article_id == article.id)
            estoc = (await db.execute(stmt_estoc)).scalars().first()
            if not estoc:
                estoc = EstocMagatzem(
                    empresa_id=empresa_id,
                    magatzem_id=magatzem.id,
                    article_id=article.id,
                    quantitat_fisica=0.0
                )
                db.add(estoc)
                await db.flush()

            moviment = MovimentEstoc(
                empresa_id=empresa_id,
                magatzem_id=magatzem.id,
                article_id=article.id,
                tipus_moviment="ENTRADA",
                quantitat=linia.quantitat,
                usuari_id=None,
                referencia_document=payload.numero_document,
                notes="Albarà Proveïdor OCR"
            )
            db.add(moviment)
            estoc.quantitat_fisica = float(estoc.quantitat_fisica) + linia.quantitat
            moviments_creats += 1

        await db.commit()"""

if target in text:
    text = text.replace(target, replacement)
    print("Replaced!")
else:
    print("Target not found!")

with open(path, "w") as f:
    f.write(text)
