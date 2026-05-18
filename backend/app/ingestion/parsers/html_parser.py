"""
HTML Parser using BeautifulSoup.
Extracts clean text from HTML, removes noise elements.
"""
from bs4 import BeautifulSoup
import re


class HTMLParser:
    NOISE_TAGS = [
        "script", "style", "nav", "footer", "header",
        "aside", "advertisement", "cookie-banner", "noscript",
        "form", "svg", "canvas",
    ]
    NOISE_SELECTOR_RE = re.compile(
        "cookie|banner|modal|popup|subscribe|newsletter|advert|ads|promo|sidebar|share|social",
        re.IGNORECASE,
    )

    def parse(self, html: str, url: str = "", title: str = "") -> dict:
        soup = BeautifulSoup(html, "lxml")

        # Remove noise
        for tag in self.NOISE_TAGS:
            for el in soup.find_all(tag):
                el.decompose()
        for el in soup.find_all(attrs={"class": self.NOISE_SELECTOR_RE}):
            el.decompose()
        for el in soup.find_all(attrs={"id": self.NOISE_SELECTOR_RE}):
            el.decompose()

        # Extract structure
        headings = {}
        for i in range(1, 7):
            headings[f"h{i}"] = [h.get_text(strip=True) for h in soup.find_all(f"h{i}")]

        # Main content heuristic: article > main > div.content > body
        main = (
            soup.find("article")
            or soup.find("main")
            or soup.find(attrs={"role": "main"})
            or soup.find("div", {"class": re.compile("content|article|post|entry|body", re.IGNORECASE)})
            or soup.find("section", {"class": re.compile("content|article|post|entry|body", re.IGNORECASE)})
            or soup.find("body")
        )

        text = ""
        if main:
            text = self._clean_text(main.get_text(separator="\n"))

        extracted_title = title
        if not extracted_title:
            title_tag = soup.find("title")
            if title_tag:
                extracted_title = title_tag.get_text(strip=True)

        return {
            "text": text,
            "headings": headings,
            "title": extracted_title,
            "meta_description": self._get_meta(soup, "description"),
            "url": url,
            "full_text": text,
        }

    def _clean_text(self, text: str) -> str:
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r" {2,}", " ", text)
        return text.strip()

    def _get_meta(self, soup, name: str) -> str:
        tag = soup.find("meta", {"name": name})
        return tag["content"] if tag and "content" in tag.attrs else ""
