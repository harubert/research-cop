"""Deterministic source check: DOIs in the text and in the reference list are resolved at doi.org;
references without DOI are searched in Crossref. Typical finding: 'near-miss' DOIs that exist but
point to a different work (often the neighbouring article of the same issue)."""
from __future__ import annotations

import json
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from difflib import SequenceMatcher

DOI_RE = re.compile(r"10\.\d{4,9}/[^\s\"<>]+")
UA = "ResearchCop/0.1 (scholarly error analysis)"


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return " ".join(re.sub(r"[^a-z0-9 ]+", " ", s).split())


def similarity(a: str, b: str) -> float:
    a, b = norm(a), norm(b)
    if not a or not b:
        return 0.0
    if a in b or b in a:
        return 1.0
    return round(SequenceMatcher(None, a, b).ratio(), 2)


def clean_doi(d: str) -> str:
    d = re.sub(r"^(https?://)?(dx\.)?doi\.org/", "", (d or "").strip(), flags=re.I)
    d = d.rstrip(".,;]>")
    while d.endswith(")") and d.count("(") < d.count(")"):
        d = d[:-1]
    return d


def dois_in_text(pages: list[str]) -> list[dict]:
    """DOIs printed in the text. A DOI broken at a line end is joined with the next line's first token."""
    out, seen = [], set()
    for pno, txt in enumerate(pages, 1):
        lines = txt.split("\n")
        for i, ln in enumerate(lines):
            for m in DOI_RE.finditer(ln):
                variants = [clean_doi(m.group(0))]
                if m.end() >= len(ln.rstrip()) and i + 1 < len(lines) and lines[i + 1].strip():
                    variants.append(clean_doi(m.group(0) + lines[i + 1].strip().split()[0]))
                if variants[0] in seen:
                    continue
                seen.add(variants[0])
                out.append({"page": pno, "raw": m.group(0), "variants": variants,
                            "context": " ".join(lines[max(0, i - 4):i + 1])[-400:]})
    return out


def _get_json(url: str, accept: str = "application/json", contact: str = ""):
    headers = {"User-Agent": UA + (f" mailto:{contact}" if contact else ""), "Accept": accept}
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as r:
                return r.status, json.loads(r.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return 404, None
            time.sleep(2 * (attempt + 1))
        except Exception:
            time.sleep(2 * (attempt + 1))
    return -1, None


def _title(m: dict) -> str:
    t = m.get("title") or ""
    return t[0] if isinstance(t, list) and t else (t if isinstance(t, str) else "")


def _year(m: dict):
    for k in ("issued", "published-print", "published-online", "created"):
        try:
            return m[k]["date-parts"][0][0]
        except Exception:
            pass
    return None


def resolve(doi: str, contact: str = "") -> dict:
    q = urllib.parse.quote(doi, safe="/:;()._-")
    st, m = _get_json("https://doi.org/" + q, "application/vnd.citationstyles.csl+json", contact)
    if st == 200 and m:
        return {"status": "ok", "title": _title(m), "year": _year(m),
                "authors": [a.get("family", "") for a in m.get("author", [])][:4]}
    st2, h = _get_json("https://doi.org/api/handles/" + q)
    return {"status": "exists_no_meta" if (h and h.get("responseCode") == 1) else "not_found"}


def crossref_search(title: str, authors: str, contact: str = "") -> dict | None:
    q = urllib.parse.quote(f"{title} {authors[:80]}")
    st, j = _get_json(f"https://api.crossref.org/works?query.bibliographic={q}&rows=3&select=title,DOI,issued,author",
                      contact=contact)
    best = None
    for it in ((j or {}).get("message", {}).get("items", []) if j else []):
        t = (it.get("title") or [""])[0]
        sc = similarity(title, t)
        if not best or sc > best["similarity"]:
            best = {"similarity": sc, "title": t, "doi": it.get("DOI"), "year": _year(it)}
    return best


def classify(ref: dict, res: dict | None, search: dict | None) -> str:
    """confirmed | title_differs | near_miss | wrong_doi | doi_not_registered | not_found | unchecked"""
    if res:
        if res["status"] == "not_found":
            if search and search["similarity"] >= 0.85:
                return "near_miss" if search.get("doi") else "doi_not_registered"
            return "doi_not_registered"
        if res["status"] == "exists_no_meta":
            return "unchecked"
        sim = similarity(ref.get("title", ""), res.get("title", ""))
        if sim >= 0.8:
            return "confirmed"
        if search and search["similarity"] >= 0.85 and search.get("doi") and search["doi"].lower() != ref["doi"].lower():
            a, b = ref["doi"].lower(), search["doi"].lower()
            return "near_miss" if SequenceMatcher(None, a, b).ratio() >= 0.85 else "wrong_doi"
        return "title_differs" if sim >= 0.5 else "wrong_doi"
    if search:
        return "confirmed" if search["similarity"] >= 0.85 else "not_found"
    return "unchecked"


def check(references: list[dict], pages: list[str], cfg, log=print) -> dict:
    contact = cfg["sources"]["contact_email"]
    rows = []
    for i, ref in enumerate(references, 1):
        doi = clean_doi(ref.get("doi", ""))
        rec = {"n": i, **ref, "doi": doi}
        res = resolve(doi, contact) if (doi and cfg["sources"]["check_dois"]) else None
        search = None
        need_search = cfg["sources"]["crossref_search"] and ref.get("type") not in ("web",) and ref.get("title")
        if need_search and (not res or res["status"] != "ok" or similarity(ref.get("title", ""), res.get("title", "")) < 0.8):
            search = crossref_search(ref.get("title", ""), ref.get("authors", ""), contact)
            time.sleep(0.3)
        rec["resolved"], rec["search"] = res, search
        rec["class"] = classify(rec, res, search)
        rows.append(rec)
        time.sleep(0.2)
    in_text = dois_in_text(pages)
    known = {r["doi"].lower() for r in rows if r["doi"]}
    extra = []
    for d in in_text:   # DOIs printed in the text but missing from the extracted list
        if not any(v.lower() in known for v in d["variants"]):
            for v in d["variants"]:
                r = resolve(v, contact)
                if r["status"] == "ok":
                    break
            extra.append({**d, "doi": v, "resolved": r})
    counts = {}
    for r in rows:
        counts[r["class"]] = counts.get(r["class"], 0) + 1
    return {"references": rows, "text_dois": extra, "counts": counts}
