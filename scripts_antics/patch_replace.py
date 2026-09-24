files = ["backend/app/api/v1/gestio/magatzem.py", "backend/app/api/v1/gestio/proveidors.py"]

for fpath in files:
    with open(fpath, "r") as f:
        content = f.read()

    # Just standard exact replacements for the ones found in these two files:
    
    reps = [
        (".where(Proveidor.empresa_id == uuid.UUID(empresa_id))", ""),
        (".where(Proveidor.empresa_id == uuid.UUID(empresa_id), Proveidor.nif == proveidor.nif)", ".where(Proveidor.nif == proveidor.nif)"),
        (".where(Proveidor.empresa_id == uuid.UUID(empresa_id), Proveidor.codi == proveidor.codi)", ".where(Proveidor.codi == proveidor.codi)"),
        (".where(Proveidor.id == proveidor_id, Proveidor.empresa_id == uuid.UUID(empresa_id))", ".where(Proveidor.id == proveidor_id)"),
        
        (".where(Article.empresa_id == uuid.UUID(empresa_id))", ""),
        (".where(Article.empresa_id == uuid.UUID(empresa_id), Article.referencia_inventari == article.referencia_inventari)", ".where(Article.referencia_inventari == article.referencia_inventari)"),
        (".where(Proveidor.empresa_id == empresa_id, Proveidor.nif == payload.proveidor.nif)", ".where(Proveidor.nif == payload.proveidor.nif)"),
        (".where(Magatzem.empresa_id == empresa_id, Magatzem.tipus == \"NAU_CENTRAL\")", ".where(Magatzem.tipus == \"NAU_CENTRAL\")"),
        (".where(AlbaraProveidor.empresa_id == empresa_id, AlbaraProveidor.numero_albara == num_albara)", ".where(AlbaraProveidor.numero_albara == num_albara)"),
        (".where(FacturaProveidor.empresa_id == empresa_id, FacturaProveidor.proveidor_id == prov.id, FacturaProveidor.numero_factura == payload.numero_document)", ".where(FacturaProveidor.proveidor_id == prov.id, FacturaProveidor.numero_factura == payload.numero_document)"),
        (".where(AlbaraProveidor.empresa_id == empresa_id, AlbaraProveidor.proveidor_id == prov.id, AlbaraProveidor.numero_albara == payload.numero_document)", ".where(AlbaraProveidor.proveidor_id == prov.id, AlbaraProveidor.numero_albara == payload.numero_document)"),
        (".where(Article.empresa_id == empresa_id, Article.referencia_inventari == linia.referencia)", ".where(Article.referencia_inventari == linia.referencia)"),
        (".where(Article.id == article_id, Article.empresa_id == uuid.UUID(empresa_id))", ".where(Article.id == article_id)")
    ]

    for old, new in reps:
        content = content.replace(old, new)

    with open(fpath, "w") as f:
        f.write(content)
