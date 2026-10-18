"""Collect documents from the input folder (files, urls.txt, optional manifest.csv)."""
from __future__ import annotations

import csv
import hashlib
import html
import json
import re
import shutil
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

from . import pdftext

PDF_EXT = {".pdf"}
HTML_EXT = {".html", ".htm"}
TEXT_EXT = {".txt", ".md"}
CHUNK = 3500  # characters per pseudo-page for HTML/text sources
UA = "ResearchCop/0.1 (+https://github.com; scholarly error analysis)"


def slug(name: str, extra: str = "") -> str:
    base = re.sub(r"[^A-Za-z0-9]+", "-", Path(name).stem).strip("-")[:40] or "doc"
    h = hashlib.sha1((name + extra).encode("utf-8")).hexdigest()[:6]
    return f"{base}-{h}"


class _Text(HTMLParser):
    SKIP = {"script", "style", "nav", "header", "footer", "noscript", "svg"}
    BLOCK = {"p", "div", "br", "li", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "section", "article", "table", "blockquote"}

    def __init__(self):
        super().__init__()
        self.parts, self.skip, self.title, self._in_title = [], 0, "", False

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        if tag == "title":
            self._in_title = True
        if tag in self.BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip:
            self.skip -= 1
        if tag == "title":
            self._in_title = False
        if tag in self.BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif not self.skip:
            self.parts.append(data)


def html_to_text(raw: str) -> tuple[str, str]:
    p = _Text()
    p.feed(raw)
    text = html.unescape("".join(p.parts))
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text).strip()
    return p.title.strip(), text


def chunk(text: str, size: int = CHUNK) -> list[str]:
    paras, pages, cur = text.split("\n\n"), [], ""
    for para in paras:
        if cur and len(cur) + len(para) > size:
            pages.append(cur.strip()); cur = ""
        cur += para + "\n\n"
    if cur.strip():
        pages.append(cur.strip())
    return pages or [""]


def download(url: str, dest_dir: Path) -> Path:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read()
        ctype = r.headers.get("Content-Type", "").lower()
    ext = ".pdf" if ("pdf" in ctype or data[:5] == b"%PDF-") else ".html"
    dest_dir.mkdir(parents=True, exist_ok=True)
    path = dest_dir / (slug(url.rstrip("/").split("/")[-1] or "page", url) + ext)
    path.write_bytes(data)
    return path


def read_manifest(input_dir: Path) -> dict[str, dict]:
    m = input_dir / "manifest.csv"
    if not m.exists():
        return {}
    with open(m, encoding="utf-8-sig", newline="") as f:
        return {row["source"].strip(): row for row in csv.DictReader(f) if row.get("source")}


def _register(path: Path, source: str, docs_dir: Path, manifest: dict) -> dict:
    doc_id = slug(path.name, source)
    ddir = docs_dir / doc_id
    ddir.mkdir(parents=True, exist_ok=True)
    meta_file = ddir / "meta.json"
    if meta_file.exists():
        return json.loads(meta_file.read_text(encoding="utf-8"))
    ext = path.suffix.lower()
    title_hint = ""
    if ext in PDF_EXT:
        kind = "pdf"
        shutil.copyfile(path, ddir / "source.pdf")
        pages = pdftext.page_texts(str(ddir / "source.pdf"))
    else:
        raw = path.read_text(encoding="utf-8", errors="replace")
        if ext in HTML_EXT:
            kind = "html"
            title_hint, text = html_to_text(raw)
        else:
            kind = "text"
            text = raw
        pages = chunk(text)
    pdir = ddir / "pages"
    pdir.mkdir(exist_ok=True)
    for i, t in enumerate(pages, 1):
        (pdir / f"p{i:03d}.txt").write_text(t, encoding="utf-8")
    row = manifest.get(source) or manifest.get(path.name) or {}
    meta = {
        "id": doc_id, "kind": kind, "source": source, "file": path.name,
        "n_pages": len(pages), "title_hint": title_hint,
        "group": (row.get("group") or "").strip(), "label": (row.get("label") or "").strip(),
        "chars": sum(len(t) for t in pages),
    }
    meta_file.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    return meta


def ingest(cfg, log=print) -> list[dict]:
    inp = cfg.path("input")
    inp.mkdir(parents=True, exist_ok=True)
    docs_dir = cfg.dir("docs")
    manifest = read_manifest(inp)
    metas = []
    control = {"readme.md", "urls.txt"}
    for f in sorted(inp.iterdir()):
        if f.name.lower() in control or ".example." in f.name.lower():
            continue
        if f.is_file() and f.suffix.lower() in PDF_EXT | HTML_EXT | TEXT_EXT:
            metas.append(_register(f, f.name, docs_dir, manifest))
    urls = inp / "urls.txt"
    if urls.exists():
        for line in urls.read_text(encoding="utf-8").splitlines():
            url = line.strip()
            if not url or url.startswith("#"):
                continue
            cached = next((m for m in _existing(docs_dir) if m["source"] == url), None)
            if cached:
                metas.append(cached); continue
            try:
                path = download(url, cfg.dir("downloads"))
                metas.append(_register(path, url, docs_dir, manifest))
            except Exception as e:  # keep going, report at the end
                log(f"  ! download failed: {url} ({e})")
    for m in metas:
        log(f"  {m['id']:<48} {m['kind']:<5} {m['n_pages']:>4} p.  {m.get('group') or ''}")
    return metas


def _existing(docs_dir: Path):
    for mf in docs_dir.glob("*/meta.json"):
        yield json.loads(mf.read_text(encoding="utf-8"))
