"""Script d'inicialització d'una empresa demo completa amb dades reals.

Crea de manera idempotent:
- Empresa 'AgroServeis Demo SL' (subdomini: 'demo', vertical: 'CampoPro')
- Configuració de Node IA sobirà (ordinador dedicat de la seu)
- Usuari BOSS (gestió d'oficina): director@demo.cat (Password123! / PIN 0000)
- Usuari ENGINYER (tècnic d'oficina): enginyer@demo.cat (Password123! / PIN 9999)
- 3 Operaris de camp amb PINs ràpids (1111, 2222, 3333)
- Magatzem central i 6 articles reals d'irrigació/agrícola amb estoc
- 3 Vehicles de flota assignats als operaris
- 2 Clients amb les seves ordres de treball
- 2 FAQ corporatives per al RAG del Copilot
"""

import asyncio
import os
import sys
import uuid
from datetime import date

import bcrypt
from sqlalchemy import func, select

# Afegir ruta del backend
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.api.v1.gestio.operaris import hash_pin
from app.core.db import AsyncSessionLocal
from app.models.models import (
    AlbaraProveidor,
    Article,
    Client,
    Empresa,
    EstocMagatzem,
    FaqCorporativaRag,
    Magatzem,
    OrdreTreball,
    Proveidor,
    Usuari,
    Vehicle,
)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


async def seed_demo():
    print("🌱 [SEED DEMO] Inicialitzant Empresa Demo a Sevalor Suite...")

    async with AsyncSessionLocal() as session:
        # Desactivar RLS per al script d'administració
        from sqlalchemy import text
        await session.execute(text("RESET ROLE;"))
        await session.execute(text("SET LOCAL app.is_superadmin = 'true';"))
        await session.execute(text("SET LOCAL app.current_user_role = 'SUPERADMIN';"))

        # 1. Empresa Demo
        subdomini = "demo"
        stmt_emp = select(Empresa).where(
            (Empresa.subdomini == subdomini) | (Empresa.nif == "B98765432")
        )
        res_emp = await session.execute(stmt_emp)
        empresa = res_emp.scalars().first()

        default_node_ia = os.getenv("NODE_IA_URL", "http://127.0.0.1:1234/v1")

        if not empresa:
            empresa = Empresa(
                id=uuid.uuid4(),
                nom="AgroServeis Demo SL",
                nif="B98765432",
                subdomini=subdomini,
                estat_domini="NO_CONFIGURAT",
                pla_subscripcio="ENTERPRISE",
                estat_pagament="ACTIU",
                vertical="CampoPro",
                node_ia_url=default_node_ia,
                node_ia_actiu=True,
                feature_copilot_ia=True,
                feature_flota=True,
                feature_planols=True,
                feature_telegram=True,
                quota_disc_bytes_autoritzada=53687091200,  # 50 GB
                primari_hsl="142 71% 25%",  # Verd corporatiu agrícola
                secundari_hsl="38 92% 50%",
                accent_hsl="160 84% 39%",
            )
            session.add(empresa)
            await session.flush()
            print(f"🏢 Empresa creada: {empresa.nom} (Subdomini: {empresa.subdomini})")
        else:
            empresa.node_ia_url = default_node_ia
            empresa.node_ia_actiu = True
            empresa.feature_copilot_ia = True
            empresa.feature_flota = True
            empresa.feature_planols = True
            empresa.feature_telegram = True
            print(f"🏢 Empresa actualitzada: {empresa.nom} (ID: {empresa.id})")

        empresa_id = empresa.id

        # 2. Usuaris d'Oficina (BOSS & ENGINYER)
        pass_comu = hash_password("Password123!")

        # 2.1 BOSS (Director d'operacions)
        stmt_boss = select(Usuari).where(
            Usuari.empresa_id == empresa_id,
            func.lower(Usuari.email) == "director@demo.cat",
        )
        boss = (await session.execute(stmt_boss)).scalars().first()
        if not boss:
            boss = Usuari(
                id=uuid.uuid4(),
                empresa_id=empresa_id,
                nif="44556677A",
                nom="Carles",
                cognoms="Roca Font",
                email="director@demo.cat",
                telefon="+34600112233",
                password_hash=pass_comu,
                pin_hash=hash_pin("0000"),
                rol="BOSS",
                estat="ACTIU",
                totp_activat=False,
            )
            session.add(boss)
            print("👔 BOSS creat: director@demo.cat (PIN: 0000 | Pwd: Password123!)")
        else:
            boss.password_hash = pass_comu
            boss.pin_hash = hash_pin("0000")
            print("👔 BOSS actualitzat: director@demo.cat")

        # 2.2 ENGINYER (Tècnic de suport)
        stmt_eng = select(Usuari).where(
            Usuari.empresa_id == empresa_id,
            func.lower(Usuari.email) == "enginyer@demo.cat",
        )
        eng = (await session.execute(stmt_eng)).scalars().first()
        if not eng:
            eng = Usuari(
                id=uuid.uuid4(),
                empresa_id=empresa_id,
                nif="55667788B",
                nom="Marta",
                cognoms="Soler Vives",
                email="enginyer@demo.cat",
                telefon="+34600223344",
                password_hash=pass_comu,
                pin_hash=hash_pin("9999"),
                rol="ENGINYER",
                estat="ACTIU",
                totp_activat=False,
            )
            session.add(eng)
            print("📐 ENGINYER creat: enginyer@demo.cat (PIN: 9999 | Pwd: Password123!)")

        # 3. Operaris de Camp (Tècnics PWA)
        operaris_demo = [
            {
                "nif": "11223344C",
                "nom": "Marc",
                "cognoms": "Vila Puig",
                "telefon": "+34611001100",
                "pin": "1111",
                "especialitat": "SISTEMES_REG",
            },
            {
                "nif": "22334455D",
                "nom": "Pau",
                "cognoms": "Serra Batlle",
                "telefon": "+34622002200",
                "pin": "2222",
                "especialitat": "BOMBAMENT_ELECTRICA",
            },
            {
                "nif": "33445566E",
                "nom": "Laia",
                "cognoms": "Martí Bosch",
                "telefon": "+34633003300",
                "pin": "3333",
                "especialitat": "FONTANERIA_CAMP",
            },
        ]

        operaris_db = {}
        for op_data in operaris_demo:
            stmt_op = select(Usuari).where(
                Usuari.empresa_id == empresa_id,
                Usuari.nif == op_data["nif"],
            )
            op = (await session.execute(stmt_op)).scalars().first()
            if not op:
                op = Usuari(
                    id=uuid.uuid4(),
                    empresa_id=empresa_id,
                    nif=op_data["nif"],
                    nom=op_data["nom"],
                    cognoms=op_data["cognoms"],
                    telefon=op_data["telefon"],
                    pin_hash=hash_pin(op_data["pin"]),
                    password_hash=pass_comu,
                    rol="OPERARI",
                    estat="ACTIU",
                    especialitat=op_data["especialitat"],
                    cost_hora_eur=24.50,
                )
                session.add(op)
                print(f"🚜 Operari creat: {op.nom} {op.cognoms} (NIF: {op.nif} | PIN: {op_data['pin']})")
            else:
                op.pin_hash = hash_pin(op_data["pin"])
                op.estat = "ACTIU"
            operaris_db[op_data["nom"]] = op

        await session.flush()

        # 4. Magatzem Central
        stmt_mag = select(Magatzem).where(
            Magatzem.empresa_id == empresa_id,
            Magatzem.tipus == "NAU_CENTRAL",
        )
        magatzem = (await session.execute(stmt_mag)).scalars().first()
        if not magatzem:
            magatzem = Magatzem(
                id=uuid.uuid4(),
                empresa_id=empresa_id,
                nom="Magatzem Central Agrari",
                tipus="NAU_CENTRAL",
                adreca="Polígon Industrial Agro, Nau 4, Lleida",
                actiu=True,
            )
            session.add(magatzem)
            await session.flush()
            print(f"📦 Magatzem creat: {magatzem.nom}")

        # 4.1 Proveïdor de Materials Agrícoles
        stmt_prov = select(Proveidor).where(
            Proveidor.empresa_id == empresa_id,
            Proveidor.nif == "A25123456",
        )
        prov = (await session.execute(stmt_prov)).scalars().first()
        if not prov:
            prov = Proveidor(
                id=uuid.uuid4(),
                empresa_id=empresa_id,
                codi="PRV-001",
                rao_social="Suministros Agrícolas del Segre SL",
                nif="A25123456",
                telefon="+34 973 22 11 00",
                email="comandes@segresuministros.cat",
                especialitat="MATERIALS",
                actiu=True,
            )
            session.add(prov)
            await session.flush()
            print(f"🏭 Proveïdor creat: {prov.rao_social} (NIF: {prov.nif})")
        else:
            print(f"🏭 Proveïdor existent: {prov.rao_social}")

        # 4.2 Albarà de Proveïdor inicial (Entrada a Magatzem)
        stmt_alb = select(AlbaraProveidor).where(
            AlbaraProveidor.empresa_id == empresa_id,
            AlbaraProveidor.numero_albara == "ALB-2026-9042",
        )
        alb = (await session.execute(stmt_alb)).scalars().first()
        if not alb:
            alb = AlbaraProveidor(
                id=uuid.uuid4(),
                empresa_id=empresa_id,
                proveidor_id=prov.id,
                numero_albara="ALB-2026-9042",
                data_albara=date(2026, 3, 15),
                estat="CONCILIAT",
            )
            session.add(alb)
            await session.flush()
            print(f"📄 Albarà de proveïdor creat: {alb.numero_albara}")

        # 5. Articles d'Inventari i Estoc Real
        articles_demo = [
            {
                "ref": "VALV-ELEC-2",
                "nom": "Electrovàlvula Bermad 2 Polzades 24VAC",
                "familia": "VALVULERIA",
                "unitat": "UNITAT",
                "preu_cost": 45.0,
                "preu_venda": 78.50,
                "minim": 5,
                "optim": 20,
                "quantitat": 14,
                "ubicacio": "Passadís A - Estant 2",
            },
            {
                "ref": "TUB-PE-32-10",
                "nom": "Tub Polietilè Agrícola DN 32mm PN10 (Rotllo 100m)",
                "familia": "CANONADA",
                "unitat": "METRE",
                "preu_cost": 0.45,
                "preu_venda": 0.85,
                "minim": 200,
                "optim": 1000,
                "quantitat": 650,
                "ubicacio": "Pati Exterior - Zona B",
            },
            {
                "ref": "ASP-SECT-360",
                "nom": "Aspersor d'Impacte Sectorial 1/2 Polzada",
                "familia": "ASPERSORS",
                "unitat": "UNITAT",
                "preu_cost": 6.20,
                "preu_venda": 11.90,
                "minim": 20,
                "optim": 100,
                "quantitat": 48,
                "ubicacio": "Passadís A - Estant 4",
            },
            {
                "ref": "BOMBA-ESP-15CV",
                "nom": "Electrobomba Submergible 15CV 400V Trifàsica",
                "familia": "BOMBAMENT",
                "unitat": "UNITAT",
                "preu_cost": 1250.0,
                "preu_venda": 1890.0,
                "minim": 1,
                "optim": 3,
                "quantitat": 2,
                "ubicacio": "Zona Pesada - Palet 1",
            },
            {
                "ref": "FILT-ANEL-3",
                "nom": "Filtre d'Anelles Manual 3 Polzades 130 Micres",
                "familia": "FILTRATGE",
                "unitat": "UNITAT",
                "preu_cost": 85.0,
                "preu_venda": 140.0,
                "minim": 2,
                "optim": 8,
                "quantitat": 5,
                "ubicacio": "Passadís B - Estant 1",
            },
            {
                "ref": "MANOMETRE-0-10",
                "nom": "Manòmetre amb Glicerina 0-10 Bar Rosc 1/4",
                "familia": "CONTROL",
                "unitat": "UNITAT",
                "preu_cost": 8.50,
                "preu_venda": 16.0,
                "minim": 5,
                "optim": 25,
                "quantitat": 19,
                "ubicacio": "Passadís C - Calaix 12",
            },
        ]

        for art_data in articles_demo:
            stmt_art = select(Article).where(
                Article.empresa_id == empresa_id,
                Article.referencia_inventari == art_data["ref"],
            )
            art = (await session.execute(stmt_art)).scalars().first()
            if not art:
                art = Article(
                    id=uuid.uuid4(),
                    empresa_id=empresa_id,
                    proveidor_id=prov.id,
                    referencia_inventari=art_data["ref"],
                    nom=art_data["nom"],
                    familia=art_data["familia"],
                    unitat_mesura=art_data["unitat"],
                    preu_cost=art_data["preu_cost"],
                    estoc_minim=art_data["minim"],
                    estoc_optim=art_data["optim"],
                )
                session.add(art)
                await session.flush()

                # Afegir estoc al magatzem
                estoc = EstocMagatzem(
                    id=uuid.uuid4(),
                    empresa_id=empresa_id,
                    article_id=art.id,
                    magatzem_id=magatzem.id,
                    quantitat_fisica=art_data["quantitat"],
                    ubicacio_passadis=art_data["ubicacio"],
                )
                session.add(estoc)
                print(f"🔧 Article afegit amb estoc i proveïdor: {art.nom} ({art_data['quantitat']} {art.unitat_mesura})")
            else:
                art.proveidor_id = prov.id
                print(f"🔧 Article actualitzat amb proveïdor: {art.nom}")

        # 6. Vehicles de Flota
        vehicles_demo = [
            {
                "matricula": "1234-LMN",
                "marca": "Ford",
                "model": "Transit Custom 2.0 TDCi",
                "odometre": 68400,
                "assignat_a": "Marc",
            },
            {
                "matricula": "5678-PKR",
                "marca": "Toyota",
                "model": "Hilux 4x4 Doble Cabina",
                "odometre": 94100,
                "assignat_a": "Pau",
            },
            {
                "matricula": "9012-TRK",
                "marca": "Nissan",
                "model": "NV400 Furgó Taller",
                "odometre": 43200,
                "assignat_a": "Laia",
            },
        ]

        for v_data in vehicles_demo:
            stmt_v = select(Vehicle).where(
                Vehicle.empresa_id == empresa_id,
                Vehicle.matricula == v_data["matricula"],
            )
            v = (await session.execute(stmt_v)).scalars().first()
            op_assignat = operaris_db.get(v_data["assignat_a"])
            op_id = op_assignat.id if op_assignat else None

            if not v:
                v = Vehicle(
                    id=uuid.uuid4(),
                    empresa_id=empresa_id,
                    matricula=v_data["matricula"],
                    marca=v_data["marca"],
                    model=v_data["model"],
                    tipus="THERMIC",
                    estat="ASSIGNAT" if op_id else "OPERATIU",
                    odometre_acumulat=v_data["odometre"],
                    conductor_habitual_id=op_id,
                    data_proxima_itv=date(2027, 4, 15),
                    estat_itv="FAVORABLE",
                )
                session.add(v)
                print(f"🚐 Vehicle creat: {v.matricula} ({v.marca} {v.model}) -> Assignat a {v_data['assignat_a']}")
            else:
                v.conductor_habitual_id = op_id
                v.estat = "ASSIGNAT" if op_id else "OPERATIU"

        # 7. Clients
        clients_demo = [
            {
                "codi": "CLI-001",
                "rao_social": "Finca Mas dels Olius SL",
                "nif": "B25889911",
                "telefon": "+34973112233",
                "email": "administracio@masdelsolius.cat",
                "adreca": "Carretera d'Artesa km 4, Balaguer",
            },
            {
                "codi": "CLI-002",
                "rao_social": "Cooperativa Agrícola del Segrià",
                "nif": "F25112233",
                "telefon": "+34973445566",
                "email": "tecnic@coopsegria.cat",
                "adreca": "Avinguda del Regadiu 12, Alcarràs",
            },
        ]

        clients_db = {}
        for c_data in clients_demo:
            stmt_c = select(Client).where(
                Client.empresa_id == empresa_id,
                Client.codi == c_data["codi"],
            )
            c = (await session.execute(stmt_c)).scalars().first()
            if not c:
                c = Client(
                    id=uuid.uuid4(),
                    empresa_id=empresa_id,
                    codi=c_data["codi"],
                    rao_social=c_data["rao_social"],
                    nif=c_data["nif"],
                    telefon=c_data["telefon"],
                    email=c_data["email"],
                    adreca_fiscal=c_data["adreca"],
                    actiu=True,
                )
                session.add(c)
                print(f"👥 Client creat: {c.rao_social} ({c.codi})")
            clients_db[c_data["codi"]] = c

        await session.flush()

        # 8. Ordres de Treball (Feines per a la PWA de l'operari)
        cli1 = clients_db.get("CLI-001")
        cli2 = clients_db.get("CLI-002")
        op_marc = operaris_db.get("Marc")
        op_pau = operaris_db.get("Pau")

        ordres_demo = [
            {
                "codi": "OT-2026-001",
                "client": cli1,
                "titol": "Reparació fuga a canonada principal sector Nord",
                "adreca": "Finca Mas dels Olius - Parcel·la 14B, Balaguer",
                "descripcio": "S'ha detectat pèrdua de pressió de 2.5 bar al col·lector de 32mm. Cal substituir tram de tub i revisar electrovàlvula.",
                "estat": "EN_CURS",
                "operari": op_marc,
            },
            {
                "codi": "OT-2026-002",
                "client": cli2,
                "titol": "Manteniment preventiu quadre elèctric i bomba 15CV",
                "adreca": "Estació de bombament Canal d'Urgell, Alcarràs",
                "descripcio": "Revisió d'intensitats del motor submergible, neteja de sondes de nivell i comprovació de pressostats.",
                "estat": "PENDENT",
                "operari": op_pau,
            },
        ]

        for ot_data in ordres_demo:
            if not ot_data["client"]:
                continue
            stmt_ot = select(OrdreTreball).where(
                OrdreTreball.empresa_id == empresa_id,
                OrdreTreball.codi == ot_data["codi"],
            )
            ot = (await session.execute(stmt_ot)).scalars().first()
            if not ot:
                ot = OrdreTreball(
                    id=uuid.uuid4(),
                    empresa_id=empresa_id,
                    codi=ot_data["codi"],
                    client_id=ot_data["client"].id,
                    titol=ot_data["titol"],
                    adreca=ot_data["adreca"],
                    descripcio=ot_data["descripcio"],
                    estat=ot_data["estat"],
                    cap_de_colla_id=ot_data["operari"].id if ot_data["operari"] else None,
                    data_planificacio=date.today(),
                )
                session.add(ot)
                print(f"📋 Ordre de Treball creada: {ot.codi} - {ot.titol}")

        # 9. FAQ / RAG Corporatiu per al Copilot
        faqs = [
            {
                "pregunta": "Com procedir davant d'una fallada per sobreintensitat a la bomba de reg?",
                "resposta": "Abans de rearmar el tèrmic al quadre, comprovar la tensió entre fases (400V +/-5%), la llibertat de gir de l'eix i verificar que el filtre d'aspiració no estigui colmatat.",
            },
            {
                "pregunta": "Quin és el procediment de purgat d'aire en xarxa de degoteig després d'una reparació?",
                "resposta": "Obrir les vàlvules de neteja dels finals de línia, engegar la bomba a baixa freqüència (35 Hz), esperar que l'aigua surti transparent i sense bombolles durant 2 minuts, i tancar gradualment.",
            },
        ]
        for faq_data in faqs:
            stmt_faq = select(FaqCorporativaRag).where(
                FaqCorporativaRag.empresa_id == empresa_id,
                FaqCorporativaRag.pregunta == faq_data["pregunta"],
            )
            faq = (await session.execute(stmt_faq)).scalars().first()
            if not faq:
                faq = FaqCorporativaRag(
                    id=uuid.uuid4(),
                    empresa_id=empresa_id,
                    pregunta=faq_data["pregunta"],
                    resposta=faq_data["resposta"],
                    categoria="PROTOCOL_TECNIC",
                )
                session.add(faq)
                print(f"🧠 FAQ Corporativa (RAG Copilot) afegida: '{faq.pregunta[:40]}...'")

        await session.commit()
        print("\n✨ [ÈXIT] Empresa Demo inicialitzada completament!")
        print(f"   🏢 Empresa: AgroServeis Demo SL (ID: {empresa_id})")
        print("   🌐 Accés Gestió: Subdomini 'demo' (o header X-Empresa-ID: " + str(empresa_id) + ")")
        print("   🔑 BOSS Oficina: director@demo.cat | Password123! | PIN 0000")
        print("   🔑 ENGINYER:     enginyer@demo.cat | Password123! | PIN 9999")
        print("   🚜 OPERARIS PWA:")
        print("      - Marc Vila:  NIF 11223344C | PIN 1111 | Ford Transit 1234-LMN")
        print("      - Pau Serra:  NIF 22334455D | PIN 2222 | Toyota Hilux 5678-PKR")
        print("      - Laia Martí: NIF 33445566E | PIN 3333 | Nissan NV400 9012-TRK")
        print("   📦 Magatzem: 6 articles amb estocs actius")
        print("   📋 Feines actives: OT-2026-001 (En curs) i OT-2026-002 (Pendent)")
        print(f"   🤖 Node IA Sobirà: {default_node_ia} (Actiu: True)")


if __name__ == "__main__":
    asyncio.run(seed_demo())
