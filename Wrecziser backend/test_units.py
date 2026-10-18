import unittest
from schemas import SummarizeRequest, SummarizeResponse, HealthResponse
from summarizer import extract_json_from_text
from pydantic import ValidationError

class TestSchemasAndExtraction(unittest.TestCase):
    def test_summarize_request_valid(self):
        req = SummarizeRequest(
            title="Test Page",
            url="https://example.com",
            content="This is a valid webpage content for testing summarization."
        )
        self.assertEqual(req.title, "Test Page")
        self.assertTrue(len(req.content) >= 10)

    def test_summarize_request_too_short(self):
        with self.assertRaises(ValidationError):
            SummarizeRequest(title="Test", url="https://example.com", content="")

    def test_extract_json_clean(self):
        raw = '{"title": "Test", "summary": "A summary", "key_points": ["Point 1"], "important_facts": ["Fact 1"]}'
        parsed = extract_json_from_text(raw)
        self.assertEqual(parsed["title"], "Test")
        self.assertEqual(parsed["summary"], "A summary")
        self.assertEqual(len(parsed["key_points"]), 1)

    def test_extract_json_with_markdown_fences(self):
        raw = '```json\n{"title": "Markdown Test", "summary": "Inside fence", "key_points": ["P1"], "important_facts": ["F1"]}\n```'
        parsed = extract_json_from_text(raw)
        self.assertEqual(parsed["title"], "Markdown Test")
        self.assertEqual(parsed["summary"], "Inside fence")

    def test_extract_json_with_surrounding_prose(self):
        raw = 'Here is the summary in JSON format:\n{"title": "Embedded", "summary": "Surrounded by text", "key_points": ["K1"], "important_facts": ["I1"]}\nHope this helps!'
        parsed = extract_json_from_text(raw)
        self.assertEqual(parsed["title"], "Embedded")
        self.assertEqual(parsed["summary"], "Surrounded by text")

    def test_extract_json_invalid(self):
        raw = "This is not json at all."
        with self.assertRaises(ValueError):
            extract_json_from_text(raw)

if __name__ == "__main__":
    unittest.main()
