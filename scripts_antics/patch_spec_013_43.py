with open("sdd_sevalor/specs/013-operari-feines.md", "r") as f:
    content = f.read()

new_detail = """- S'ha de desenvolupar un endpoint d'agregació `POST /api/v1/operari_pwa/sync/push` al backend que actuï com a embús de dades. Aquest rebrà un JSON Array de la `sync_queue` de l'operari amb blocs atòmics de 5 tipus d'accions diferents (`FITXAR_JORNADA`, `CREAR_TIQUET`, `REPORTAR_INCIDENCIA`, `INICIAR_TRAJECTE`, `FINALITZAR_ORDRE`). Ha de processar-les seqüencialment aplicant les regles de negoci i retornar `200 OK` (RF-08)."""

content = content + new_detail + "\n"

with open("sdd_sevalor/specs/013-operari-feines.md", "w") as f:
    f.write(content)
