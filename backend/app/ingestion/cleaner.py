"""
Text Cleaning Pipeline.
Applied after parsing, before chunking. Order matters.
"""
import re
import unicodedata


class TextCleaner:

    def clean(self, text: str, source_type: str = "unknown") -> str:
        if not text:
            return ""
        text = self._remove_control_chars(text)
        text = self._normalize_unicode(text)
        text = self._fix_whitespace(text)
        text = self._remove_boilerplate(text, source_type)
        text = self._fix_hyphenation(text)
        return text

    def _remove_control_chars(self, text: str) -> str:
        return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)

    def _normalize_unicode(self, text: str) -> str:
        return unicodedata.normalize("NFKC", text)

    def _fix_whitespace(self, text: str) -> str:
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def _remove_boilerplate(self, text: str, source_type: str) -> str:
        if source_type == "web":
            patterns = [
                r"Cookie Policy.*?Accept",
                r"Subscribe to our newsletter.*?\n",
                r"Share this article.*?\n",
                r"©\s*\d{4}.*?reserved\.",
            ]
            for pat in patterns:
                text = re.sub(pat, "", text, flags=re.IGNORECASE | re.DOTALL)
        return text

    def _fix_hyphenation(self, text: str) -> str:
        return re.sub(r"(\w+)-\n(\w+)", r"\1\2", text)
