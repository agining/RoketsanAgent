import unittest

from app.answer_formatting import clean_markdown, format_distance, format_duration, join_nonempty, render_table_if_needed


class AnswerFormattingTest(unittest.TestCase):
    def test_clean_markdown_removes_empty_artifacts(self):
        text = clean_markdown("**T0078** (None / 15:20, null)\n\n## \n- \nDurum ·  · YUKSEK []")
        self.assertNotIn("None", text)
        self.assertNotIn("null", text)
        self.assertNotIn("[]", text)
        self.assertNotIn("·  ·", text)
        self.assertIn("YÜKSEK", text)

    def test_formats_numbers_for_turkish_display(self):
        self.assertEqual(format_distance(3522.412), "3.522 m")
        self.assertEqual(format_duration(19.1428), "19,1 dk")
        self.assertIn("3.522 m", clean_markdown("mesafe 3522.412 m"))
        self.assertIn("19,1 dk", clean_markdown("ETA 19.1428 dk"))

    def test_join_and_table_skip_empty_values(self):
        self.assertEqual(join_nonempty(["T0078", None, "", "15:20"]), "T0078 · 15:20")
        self.assertEqual(render_table_if_needed(["İz", "Risk"], [["T0078", "YUKSEK"], [None, None]]), "")
        table = render_table_if_needed(["İz", "Risk"], [["T0078", "YUKSEK"], ["T0122", "ORTA"], [None, None]])
        self.assertIn("| İz | Risk |", table)
        self.assertIn("| T0078 | YUKSEK |", table)
        self.assertNotIn("None", table)


if __name__ == "__main__":
    unittest.main()
