import unittest
from unittest.mock import patch

from pulse import translate


class LanguageDetectionTests(unittest.TestCase):
    def test_detects_spanish_headline(self):
        self.assertEqual(
            translate.detect_language(
                "El presidente anunció nuevas medidas para los estudiantes en la universidad"
            ),
            "es",
        )

    def test_keeps_english_with_foreign_names_english(self):
        self.assertEqual(
            translate.detect_language(
                "The president met Mexico's leader in São Paulo to discuss the new policy"
            ),
            "en",
        )

    def test_detects_scripts(self):
        self.assertEqual(translate.detect_language("政府宣布了新的教育政策"), "zh")
        self.assertEqual(translate.detect_language("حكومة جديدة تعلن عن خطط التعليم"), "ar")


class OverviewTranslationTests(unittest.TestCase):
    @patch.object(translate, "translate_text", return_value=("English summary@@PULSE@@Point one@@PULSE@@Point two@@PULSE@@Why it matters", "google"))
    def test_translates_every_overview_field(self, _mock):
        overview = {
            "engine": "extractive",
            "summary": "Resumen",
            "key_points": ["Punto uno", "Punto dos"],
            "why_it_matters": "Por qué importa",
        }
        result = translate.translate_overview(overview, "es")
        self.assertEqual(result["summary"], "English summary")
        self.assertEqual(result["key_points"], ["Point one", "Point two"])
        self.assertEqual(result["why_it_matters"], "Why it matters")
        self.assertTrue(result["translated"])

    @patch.object(translate, "_cache_get", return_value="English title@@PULSE@@English summary")
    def test_cached_translation_is_applied_to_a_card(self, _mock):
        card = {"title": "Título en español", "summary": "Resumen en español", "preview": "Resumen"}
        translate.decorate(card)
        self.assertTrue(card["translated"])
        self.assertEqual(card["title"], "English title")
        self.assertEqual(card["title_original"], "Título en español")
        self.assertEqual(card["language"], "es")


if __name__ == "__main__":
    unittest.main()


class FullArticleTranslationTests(unittest.TestCase):
    @patch.object(translate, "_full_cache_get", return_value=None)
    @patch.object(translate, "_full_cache_put")
    @patch.object(translate, "_cache_get", return_value=None)
    @patch.object(translate, "_cache_put")
    @patch.object(translate, "_google", return_value=("Encabezado en inglés@@PULSE@@Primer párrafo en inglés@@PULSE@@Segundo párrafo en inglés", None))
    def test_translates_every_block_and_keeps_types(self, *_mocks):
        article = {
            "id": 987654,
            "title": "Título",
            "summary": "Resumen",
            "language": "es",
            "blocks": [
                {"type": "h2", "text": "Encabezado"},
                {"type": "p", "text": "Primer párrafo"},
                {"type": "p", "text": "Segundo párrafo"},
            ],
        }
        result = translate.full_article_translation(article, "es")
        self.assertTrue(result["translated"])
        self.assertEqual(result["language"], "es")
        self.assertEqual(result["blocks"][0]["type"], "h2")
        self.assertEqual(result["blocks"][0]["text"], "Encabezado en inglés")
        self.assertEqual(result["blocks"][2]["text"], "Segundo párrafo en inglés")
        self.assertFalse(result["partial"])

    @patch.object(translate, "_full_cache_get", return_value=None)
    @patch.object(translate, "_cache_get", return_value=None)
    @patch.object(translate, "_cache_put")
    @patch.object(translate, "_mymemory", return_value=None)
    @patch.object(translate, "_google", return_value=(None, None))
    def test_reports_busy_service_without_inventing_text(self, *_mocks):
        article = {
            "id": 987655,
            "title": "Título",
            "summary": "Resumen",
            "language": "es",
            "blocks": [{"type": "p", "text": "Texto original"}],
        }
        result = translate.full_article_translation(article, "es")
        self.assertFalse(result["translated"])
        self.assertIn("busy", result["error"].lower())
        self.assertEqual(result["blocks"][0]["text"], "Texto original")

    def test_never_translates_an_english_article(self):
        result = translate.full_article_translation(
            {"id": 1, "language": "en", "blocks": [{"type": "p", "text": "Hello"}]},
            "en",
        )
        self.assertFalse(result["translated"])
        self.assertIn("already in English", result["error"])


if __name__ == "__main__":
    unittest.main()
