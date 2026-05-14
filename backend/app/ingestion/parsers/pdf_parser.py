"""
PDF Parser using PyMuPDF (fitz).
Best free PDF parser — C++ backend, fast, good text ordering.
"""
import fitz  # PyMuPDF
from pathlib import Path


class PDFParser:

    def parse(self, filepath: str) -> dict:
        doc = fitz.open(filepath)

        pages = []
        toc = doc.get_toc()

        for page_num, page in enumerate(doc):
            blocks = page.get_text("dict")["blocks"]

            page_content = {
                "page_number": page_num + 1,
                "text": "",
                "headings": [],
            }

            for block in blocks:
                if block["type"] == 0:  # Text block
                    for line in block["lines"]:
                        for span in line["spans"]:
                            text = span["text"].strip()
                            font_size = span["size"]

                            # Heuristic: large font = heading
                            if font_size > 14:
                                page_content["headings"].append(text)
                            if text:
                                page_content["text"] += text + " "
            
            # Fallback if no blocks found (e.g. simple layout or minor issues)
            if not page_content["text"].strip():
                page_content["text"] = page.get_text("text")

            pages.append(page_content)

        doc.close()

        return {
            "pages": pages,
            "toc": toc,
            "num_pages": len(pages),
            "full_text": "\n".join(p["text"].strip() for p in pages if p["text"].strip()),
            "headings": [h for p in pages for h in p["headings"]],
            "title": Path(filepath).stem if not filepath.endswith('.pdf') else 'Document',
        }
