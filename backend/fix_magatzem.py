
with open("app/api/v1/gestio/magatzem.py", "r") as f:
    content = f.read()

# 1. Update ArticleResponse
content = content.replace(
"""class ArticleResponse(ArticleCreate):
    id: uuid.UUID
    actiu: bool""",
"""class ArticleResponse(ArticleCreate):
    id: uuid.UUID
    actiu: bool
    estoc_real: float = 0.0""")

# 2. Update llistar_articles to return estoc_real
old_llistar = """    result = await db.execute(stmt)
    articles = result.scalars().all()
    return articles"""

new_llistar = """    result = await db.execute(stmt)
    articles = result.scalars().all()
    
    # Calcular l'estoc real de cada article sumant quantitat_fisica als magatzems
    # Fem una query agrupada per obtenir l'estoc de tots els articles
    stmt_estoc = select(EstocMagatzem.article_id, func.sum(EstocMagatzem.quantitat_fisica)).where(
        EstocMagatzem.empresa_id == uuid.UUID(empresa_id)
    ).group_by(EstocMagatzem.article_id)
    estocs = (await db.execute(stmt_estoc)).all()
    estoc_map = {str(row[0]): float(row[1]) for row in estocs}
    
    articles_resp = []
    for art in articles:
        art_dict = {c.name: getattr(art, c.name) for c.table.columns}
        art_dict["estoc_real"] = estoc_map.get(str(art.id), 0.0)
        articles_resp.append(art_dict)
        
    return articles_resp"""

content = content.replace(old_llistar, new_llistar)

with open("app/api/v1/gestio/magatzem.py", "w") as f:
    f.write(content)
