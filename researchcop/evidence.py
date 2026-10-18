"""Locate a finding's anchor phrase on its PDF page and save a highlighted crop as evidence."""
from __future__ import annotations

import html
import re
import unicodedata

from PIL import Image, ImageDraw

from . import pdftext

DPI = 140
FIG = re.compile(r"(?i)\s*(abb|fig|grafik|diagramm|chart|figure)")
TAB = re.compile(r"(?i)\s*(tab)")


def norm(t: str) -> str:
    t = unicodedata.normalize("NFKC", html.unescape(t)).lower()
    return re.sub(r"[^\w%]+", "", t)


def locate(words: list[pdftext.Word], anchor: str):
    """Greedy match of the anchor words; tolerates hyphenation splits. Returns (score, box, matched words)."""
    ws = [w for w in words if norm(w.text)]
    keys = [norm(w.text) for w in ws]
    target = [norm(t) for t in anchor.split() if norm(t)]
    if not target or not ws:
        return None
    best = (0, None)
    n = len(target)
    for i in range(len(ws)):
        j, k, hit = i, 0, 0
        while k < n and j < len(ws):
            w = keys[j]
            if w == target[k]:
                hit += 1; j += 1; k += 1
            elif j + 1 < len(ws) and target[k] == w + keys[j + 1]:   # word split by hyphenation
                hit += 1; j += 2; k += 1
            else:
                break
        if hit > best[0]:
            best = (hit, (i, j))
        if hit == n:
            break
    hit, span = best
    if not span or hit < max(2, int(0.6 * n)):
        return None
    sel = ws[span[0]:span[1]]
    box = (min(w.x0 for w in sel), min(w.y0 for w in sel), max(w.x1 for w in sel), max(w.y1 for w in sel))
    return hit / n, box, sel


def column(words: list[pdftext.Word], box, pw: float, band: float = 140, gutter: float = 9) -> tuple[float, float]:
    """Horizontal extent of the text column that contains the hit: merge the x-ranges of nearby words;
    columns stay separate because of the gutter between them."""
    near = sorted((w.x0, w.x1) for w in words if w.y1 > box[1] - band and w.y0 < box[3] + band)
    spans = []
    for x0, x1 in near:
        if spans and x0 <= spans[-1][1] + gutter:
            spans[-1][1] = max(spans[-1][1], x1)
        else:
            spans.append([x0, x1])
    cx = (box[0] + box[2]) / 2
    for x0, x1 in spans:
        if x0 - 1 <= cx <= x1 + 1:
            return min(x0, box[0]), max(x1, box[2])
    return 0.0, pw


def crop(pdf: str, page: int, anchor: str, out_png: str) -> dict:
    """Save a crop around the anchor (yellow words, red frame). Falls back to the full page."""
    pw, ph, words = pdftext.page_words(pdf, page)
    img = pdftext.render(pdf, page, DPI)
    s = img.width / pw
    res = locate(words, anchor) if anchor else None
    if not res:
        img.thumbnail((1100, 1600))
        img.save(out_png, optimize=True)
        return {"ok": False, "mode": "page", "page": page}
    score, box, sel = res
    cx0, cx1 = column(words, box, pw)
    if TAB.match(anchor):
        region = [cx0 - 8, box[1] - 20, cx1 + 8, box[3] + 520]
    elif FIG.match(anchor):
        region = [cx0 - 8, box[1] - 300, cx1 + 8, box[3] + 300]
    else:
        region = [cx0 - 8, box[1] - 120, cx1 + 8, box[3] + 120]
    region = [max(0, region[0]), max(0, region[1]), min(pw, region[2]), min(ph, region[3])]
    ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    for w in sel:
        d.rectangle([w.x0 * s - 2, w.y0 * s - 2, w.x1 * s + 2, w.y1 * s + 2], fill=(255, 196, 0, 90))
    d.rectangle([box[0] * s - 5, box[1] * s - 5, box[2] * s + 5, box[3] * s + 5], outline=(200, 30, 30, 255), width=3)
    img = Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")
    img.crop(tuple(int(v * s) for v in region)).save(out_png, optimize=True)
    return {"ok": True, "mode": "anchor", "page": page, "score": round(score, 2)}


def crop_with_neighbours(pdf: str, page: int, anchor: str, out_png: str, n_pages: int) -> dict:
    """Agents sometimes cite the page off by one; try the neighbours before falling back."""
    page = max(1, min(int(page or 1), n_pages))
    if anchor:
        for p in (page, page - 1, page + 1):
            if 1 <= p <= n_pages:
                r = crop(pdf, p, anchor, out_png)
                if r["ok"]:
                    return r
    return crop(pdf, page, "", out_png)
