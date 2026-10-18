"""PDF access via pypdfium2: page text, word boxes (top-left origin, PDF points), rendering."""
from __future__ import annotations

from dataclasses import dataclass

import pypdfium2 as pdfium


@dataclass
class Word:
    x0: float
    y0: float
    x1: float
    y1: float
    text: str


def page_count(pdf_path: str) -> int:
    pdf = pdfium.PdfDocument(pdf_path)
    try:
        return len(pdf)
    finally:
        pdf.close()


def page_texts(pdf_path: str) -> list[str]:
    pdf = pdfium.PdfDocument(pdf_path)
    try:
        out = []
        for i in range(len(pdf)):
            tp = pdf[i].get_textpage()
            out.append(tp.get_text_range().replace("\r\n", "\n").replace("\r", "\n"))
        return out
    finally:
        pdf.close()


def page_words(pdf_path: str, page_no: int) -> tuple[float, float, list[Word]]:
    """page_no is 1-based. Returns page width, height and words with top-origin boxes."""
    pdf = pdfium.PdfDocument(pdf_path)
    try:
        page = pdf[page_no - 1]
        w, h = page.get_size()
        tp = page.get_textpage()
        words: list[Word] = []
        cur, box = [], None
        for i in range(tp.count_chars()):
            ch = tp.get_text_range(i, 1)
            if not ch or ch.isspace():
                if cur:
                    words.append(Word(box[0], h - box[3], box[2], h - box[1], "".join(cur)))
                cur, box = [], None
                continue
            l, b, r, t = tp.get_charbox(i)
            if r <= l and t <= b:          # zero-size glyph (generated), keep text only
                if cur:
                    cur.append(ch)
                continue
            if box and (l < box[0] - 30 or abs(b - box[1]) > max(4.0, (t - b))):  # jumped to another line/column
                words.append(Word(box[0], h - box[3], box[2], h - box[1], "".join(cur)))
                cur, box = [], None
            cur.append(ch)
            box = (l, b, r, t) if box is None else (min(box[0], l), min(box[1], b), max(box[2], r), max(box[3], t))
        if cur and box:
            words.append(Word(box[0], h - box[3], box[2], h - box[1], "".join(cur)))
        return w, h, words
    finally:
        pdf.close()


def render(pdf_path: str, page_no: int, dpi: int = 140):
    pdf = pdfium.PdfDocument(pdf_path)
    try:
        return pdf[page_no - 1].render(scale=dpi / 72).to_pil().convert("RGB")
    finally:
        pdf.close()
