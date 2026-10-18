"""Build the interactive HTML dashboard (single file plus evidence images)."""
from __future__ import annotations

import datetime as dt
import json
from importlib import resources
from pathlib import Path

from . import __version__, evidence, stats


def _load(p: Path, default=None):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def collect(cfg, crops: bool = True, log=print) -> dict:
    docs_dir, res_dir = cfg.out / "docs", cfg.out / "results"
    ev_dir = cfg.dir("report") / "evidence"
    ev_dir.mkdir(exist_ok=True)
    docs, models, usage = [], set(), {"input_tokens": 0, "output_tokens": 0, "cache_read_input_tokens": 0}
    for mf in sorted(docs_dir.glob("*/meta.json")):
        meta = json.loads(mf.read_text(encoding="utf-8"))
        r = res_dir / meta["id"]
        review = _load(r / "review.json")
        if not review:
            continue
        verify = _load(r / "verify.json", {})
        for part in [review] + list(verify.values()) + [x for x in (_load(r / "second.json"), _load(r / "references.json")) if x]:
            run = part.get("run") or {}
            if run.get("model"):
                models.add(run["model"])
            for k in usage:
                usage[k] += (run.get("usage") or {}).get(k, 0)
        findings = stats.apply_verification(review["findings"], verify)
        pdf = mf.parent / "source.pdf"
        for f in findings:
            f["img"] = f["img2"] = None
            if crops and meta["kind"] == "pdf" and pdf.exists():
                tag = f"{meta['id']}_{f['id']}"
                out = ev_dir / f"{tag}.png"
                try:
                    if not out.exists():
                        evidence.crop_with_neighbours(str(pdf), f.get("page_pdf") or 1, f.get("anchor", ""), str(out), meta["n_pages"])
                    f["img"] = f"evidence/{tag}.png"
                    if f.get("compare_page"):
                        out2 = ev_dir / f"{tag}_cmp.png"
                        if not out2.exists():
                            evidence.crop_with_neighbours(str(pdf), f["compare_page"], f.get("compare_anchor", ""), str(out2), meta["n_pages"])
                        f["img2"] = f"evidence/{tag}_cmp.png"
                except Exception as e:
                    log(f"  ! evidence {tag}: {e}")
        second = _load(r / "second.json")
        agreement = stats.match_reviews(review["findings"], second["findings"]) if second else None
        src = _load(r / "sources.json")
        docs.append({
            "meta": meta, "article": review["article"], "findings": findings,
            "metrics": stats.doc_metrics(meta, findings), "agreement": agreement,
            "sources": src, "run": review.get("run", {}),
        })
    return {
        "docs": docs, "groups": stats.group_metrics(docs), "models": sorted(models), "usage": usage,
        "generated": dt.datetime.now().isoformat(timespec="minutes"), "version": __version__,
        "language": cfg["review"]["language"],
    }


def write(cfg, data: dict) -> Path:
    tpl = resources.files("researchcop").joinpath("templates/report.html").read_text(encoding="utf-8")
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    out = cfg.dir("report") / "index.html"
    out.write_text(tpl.replace("/*__DATA__*/null", payload), encoding="utf-8")
    return out
