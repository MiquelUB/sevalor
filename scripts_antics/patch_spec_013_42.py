with open("sdd_sevalor/specs/013-operari-feines.md", "r") as f:
    content = f.read()

new_detail = """- S'ha d'integrar un motor de Workbox Background Sync al Service Worker (`sw.js`). Qualsevol trucada `POST`, `PUT` o `PATCH` a la API que falli per manca de xarxa o "Modo Avión" ha de ser interceptada, catalogada i retinguda en la "Cola de Sincronització" (`sync_queue`), executant-se automàticament en segon pla (sync event) quan el dispositiu recuperi la cobertura."""

content = content + new_detail + "\n"

with open("sdd_sevalor/specs/013-operari-feines.md", "w") as f:
    f.write(content)
