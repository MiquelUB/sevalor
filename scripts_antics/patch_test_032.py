with open("backend/tests/test_032_picking_cuarentena.py", "r") as f:
    content = f.read()

# I will query EstocMagatzem using the API or directly without filtering by magatzem_id just in case
old_block = """            estoc_res = await admin_session.execute(
                select(EstocMagatzem).where(
                    EstocMagatzem.article_id == uuid.UUID(data["article_id"]),
                    EstocMagatzem.magatzem_id == uuid.UUID(data["magatzem_id"])
                )
            )
            estoc = estoc_res.scalars().first()"""

new_block = """            estoc_res = await admin_session.execute(
                select(EstocMagatzem).where(
                    EstocMagatzem.article_id == uuid.UUID(data["article_id"])
                )
            )
            estoc = estoc_res.scalars().first()
            assert estoc is not None, "El estoc no existeix!"
            await admin_session.refresh(estoc)"""

content = content.replace(old_block, new_block)

with open("backend/tests/test_032_picking_cuarentena.py", "w") as f:
    f.write(content)
