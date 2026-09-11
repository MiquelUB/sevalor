"""Suite de proves per al Microservei del Bot de Telegram (Spec 023) — condicionat a disponibilitat."""

import unittest
import sys

try:
    from aiogram import Bot, Dispatcher, types  # noqa: F401
    from bot.security import detectar_doble_extensio, validar_magic_bytes, RedisRateLimiter
    from bot.main import (
        registrar_token_invitacio,
        processar_missatge_text,
        processar_document_adjunt,
        processar_aprovacio_pressupost,
    )
    BOT_DISPONIBLE = True
except (ImportError, ModuleNotFoundError):
    BOT_DISPONIBLE = False


@unittest.skipIf(not BOT_DISPONIBLE, "Dependències del bot Telegram no disponibles al backend")
class TestBotTelegram(unittest.TestCase):
    def setUp(self):
        self.rate_limiter = RedisRateLimiter(limit_per_minut=3)

    def test_filtre_doble_extensio_maliciosa(self):
        """Spec 023 RF-16: Bloqueig immediat de fitxers amb doble extensió o executables."""
        arxius_maliciosos = [
            "tiquet.pdf.exe",
            "rebut.pdf.sh",
            "factura.jpg.bat",
            "evidencia.png.py",
            "informe.pdf.js",
            "script.sh",
            "foto.exe",
        ]
        for nom in arxius_maliciosos:
            es_malicios, motiu = detectar_doble_extensio(nom)
            self.assertTrue(es_malicios, f"El fitxer {nom} hauria d'haver estat blocat.")
            self.assertTrue(
                any(term in motiu.lower() for term in ["perillosa", "sospitosa", "autoritzada", "script"]),
                f"Motiu inesperat: {motiu}"
            )

    def test_filtre_fitxers_legitims(self):
        """Spec 023 RF-16: Admissió de fitxers vàlids d'obra (JPG, PNG, PDF, WebP)."""
        arxius_legitims = [
            "foto_avaria_bomba.jpg",
            "tiquet_gasoil_2026.pdf",
            "aspersor_trencat.png",
            "valvula_detall.webp",
            "albara_material.PDF",
        ]
        for nom in arxius_legitims:
            es_malicios, motiu = detectar_doble_extensio(nom)
            self.assertFalse(es_malicios, f"El fitxer {nom} hauria de ser vàlid. Motiu: {motiu}")
            self.assertEqual(motiu, "OK")

    def test_magic_bytes_validation(self):
        """Spec 023 RF-16: Validació de capçaleres binaris Magic Bytes."""
        self.assertTrue(validar_magic_bytes(b"\xff\xd8\xff\xe0\x00\x10JFIF", "jpg"))
        self.assertTrue(validar_magic_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR", "png"))
        self.assertTrue(validar_magic_bytes(b"%PDF-1.7\n%...", "pdf"))
        self.assertTrue(validar_magic_bytes(b"RIFF\x00\x00\x00\x00WEBPVP8 ", "webp"))
        self.assertFalse(validar_magic_bytes(b"MZ\x90\x00\x03\x00\x00\x00", "pdf"))

    def test_rate_limiter_exists(self):
        """Spec 023 RF-07: Verificar que RedisRateLimiter es pot instanciar."""
        self.assertIsNotNone(self.rate_limiter)
        self.assertEqual(self.rate_limiter.limit, 3)

    def test_rebuig_opac_usuaris_no_convidats(self):
        """Spec 023 RF-06: Blindatge d'accés i rebuig opac a usuaris sense token."""
        chat_id_desconegut = 88881111
        resposta = processar_missatge_text(chat_id_desconegut, "Hola, vull un pressupost")
        self.assertEqual(resposta["action"], "REBUIG_OPAC")
        self.assertIn("canal privat", resposta["text"].lower())

    def test_deep_linking_vinculacio_exitosa(self):
        """Spec 023 RF-05: Enllaç profund /start <token> i benvinguda camaleònica."""
        token_test = "tok_inv_12345"
        chat_id_client = 77772222
        registrar_token_invitacio(
            token=token_test,
            client_id="cli-001",
            empresa_id="emp-001",
            nom_client="Agropecuària del Penedès SL",
            nom_empresa="SEVALOR Regs",
        )
        res = processar_missatge_text(chat_id_client, f"/start {token_test}")
        self.assertEqual(res["action"], "VINCULACIO_OK")
        self.assertIn("SEVALOR Regs", res["text"])
        self.assertIn("Agropecuària del Penedès SL", res["text"])

        res_msg = processar_missatge_text(chat_id_client, "Quan arribarà l'equip tècnic?")
        self.assertEqual(res_msg["action"], "MISSATGE_CLIENT")
        self.assertEqual(res_msg["client_id"], "cli-001")

    def test_aprovacio_pressupost_1_clic(self):
        """Spec 023 RF-12, RF-13: Aprovació de pressupost a 1 clic amb confirmació immutable."""
        chat_id = 77772222
        registrar_token_invitacio(
            token="tok_pressupost_test",
            client_id="cli-001",
            empresa_id="emp-001",
            nom_client="Agropecuària del Penedès SL",
            nom_empresa="SEVALOR Regs",
        )
        processar_missatge_text(chat_id, "/start tok_pressupost_test")

        res_acceptat = processar_aprovacio_pressupost(chat_id, "PRE-2026-089", "ACCEPTAR")
        self.assertEqual(res_acceptat["status"], "ACCEPTAT")
        self.assertIn("acceptat", res_acceptat["text_actualitzat"].lower())
        self.assertIn("PRE-2026-089", res_acceptat["text_actualitzat"])

        res_modificar = processar_aprovacio_pressupost(chat_id, "PRE-2026-089", "MODIFICAR")
        self.assertEqual(res_modificar["status"], "DEMANA_CANVIS")
        self.assertIn("canvis", res_modificar["text_actualitzat"].lower())


if __name__ == "__main__":
    unittest.main()