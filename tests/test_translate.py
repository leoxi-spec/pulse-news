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
