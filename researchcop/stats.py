"""Aggregation: per-document metrics, verification outcome, reviewer agreement, groups."""
from __future__ import annotations

import re

CHARS_PER_PAGE = 3500   # standard page for HTML/text sources


def tokens(s: str) -> set[str]:
    return {w for w in re.findall(r"\w{3,}", (s or "").lower())}


def jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


def match_reviews(first: list[dict], second: list[dict], min_sim: float = 0.25) -> dict:
    """Greedy one-to-one matching of findings from two independent reviews.
    Two findings match if they are on the same or a neighbouring page and their quote/problem text overlaps."""
    pairs = []
    for a in first:
        ta = tokens(a.get("quote", "") + " " + a.get("anchor", "") + " " + a.get("problem", ""))
        for b in second:
            if abs(int(a.get("page_pdf") or 0) - int(b.get("page_pdf") or 0)) > 1:
                continue
            tb = tokens(b.get("quote", "") + " " + b.get("anchor", "") + " " + b.get("problem", ""))
            sim = jaccard(ta, tb) + (0.15 if a.get("k") == b.get("k") else 0)
            if sim >= min_sim:
                pairs.append((sim, a["id"], b["id"]))
    used_a, used_b, matches = set(), set(), []
    for sim, ia, ib in sorted(pairs, reverse=True):
        if ia not in used_a and ib not in used_b:
            used_a.add(ia); used_b.add(ib); matches.append({"first": ia, "second": ib, "sim": round(sim, 2)})
    return {
        "matches": matches,
        "only_first": [f["id"] for f in first if f["id"] not in used_a],
        "only_second": [f["id"] for f in second if f["id"] not in used_b],
        "n_first": len(first), "n_second": len(second),
    }


def apply_verification(findings: list[dict], verify: dict) -> list[dict]:
    """Attach verdicts; 'partly' with a corrected severity changes the severity; 'refuted' is kept but flagged."""
    out = []
    for f in findings:
        f = dict(f)
        v = verify.get(f["id"])
        if v:
            f["verdict"] = v["verdict"]
            f["verify_explanation"] = v["explanation"]
            f["verify_calc"] = v.get("calc", [])
            if v["verdict"] == "partly" and v.get("corrected_severity"):
                f["s_original"], f["s"] = f["s"], v["corrected_severity"]
        else:
            f["verdict"] = "not_checked"
        out.append(f)
    return out


def doc_metrics(meta: dict, findings: list[dict]) -> dict:
    pages = meta["n_pages"] if meta["kind"] == "pdf" else max(1.0, round(meta.get("chars", 0) / CHARS_PER_PAGE, 1))
    live = [f for f in findings if f.get("verdict") != "refuted"]
    by_s = {s: sum(1 for f in live if f["s"] == s) for s in (1, 2, 3)}
    by_k = {k: sum(1 for f in live if f["k"] == k) for k in ("K1", "K2", "K3", "K4", "K5", "K6")}
    worst_k = {k: max([f["s"] for f in live if f["k"] == k] or [0]) for k in by_k}
    return {
        "pages": pages, "n": len(live), "s1": by_s[1], "s2": by_s[2], "s3": by_s[3],
        "per_page": round(len(live) / pages, 3), "substantial_per_page": round((by_s[2] + by_s[3]) / pages, 3),
        "by_k": by_k, "worst_k": worst_k,
        "confirmed": sum(1 for f in findings if f.get("verdict") == "confirmed"),
        "partly": sum(1 for f in findings if f.get("verdict") == "partly"),
        "refuted": sum(1 for f in findings if f.get("verdict") == "refuted"),
        "unclear": sum(1 for f in findings if f.get("verdict") == "unclear"),
    }


def group_metrics(docs: list[dict]) -> list[dict]:
    groups = {}
    for d in docs:
        groups.setdefault(d["meta"].get("group") or "", []).append(d)
    out = []
    for g, ds in sorted(groups.items()):
        p = sum(d["metrics"]["pages"] for d in ds) or 1
        s = {k: sum(d["metrics"][k] for d in ds) for k in ("s1", "s2", "s3", "n")}
        out.append({"group": g or "(ohne Gruppe)", "docs": len(ds), "pages": round(p, 1), **s,
                    "per_page": round(s["n"] / p, 3), "substantial_per_page": round((s["s2"] + s["s3"]) / p, 3),
                    "s1_pp": round(s["s1"] / p, 3), "s2_pp": round(s["s2"] / p, 3), "s3_pp": round(s["s3"] / p, 3)})
    return out
