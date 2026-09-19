import sys

with open("app/api/v1/gestio/magatzem.py", "r") as f:
    content = f.read()

content = content.replace("for c in art_db.__table__.columns}", "for c in art.__table__.columns}") # Reset
content = content.replace("art_dict = {c.name: getattr(art, c.name) for c in art.__table__.columns}", "art_dict = {c.name: getattr(art, c.name) for c in art.__table__.columns}")

# Fix the one inside Modificar_article which uses art_db
content = content.replace("art_dict = {c.name: getattr(art_db, c.name) for c in art.__table__.columns}", "art_dict = {c.name: getattr(art_db, c.name) for c in art_db.__table__.columns}")

with open("app/api/v1/gestio/magatzem.py", "w") as f:
    f.write(content)
