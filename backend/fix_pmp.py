
with open("app/api/v1/gestio/magatzem.py", "r") as f:
    content = f.read()

old_pmp = """            if not article:
                article = Article(
                    empresa_id=empresa_id,
                    referencia_inventari=linia.referencia,
                    nom=linia.nom,
                    unitat_mesura="UNITAT",
                    familia="EINA" if linia.tipus == "EINA" else "GENERAL",
                    preu_cost=linia.preu * (1 - (linia.descompte_percent/100))
                )
                db.add(article)
                await db.flush()
                articles_creats += 1
            else:
                # Actualitza el preu automàticament (HMM)
                nou_preu = linia.preu * (1 - (linia.descompte_percent/100))
                if nou_preu > 0:
                    article.preu_cost = nou_preu"""

new_pmp = """            nou_preu = float(linia.preu) * (1.0 - (float(linia.descompte_percent)/100.0))
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
                    article.preu_cost = nou_preu"""

content = content.replace(old_pmp, new_pmp)

with open("app/api/v1/gestio/magatzem.py", "w") as f:
    f.write(content)
