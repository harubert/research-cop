"""The three model roles: review (first / blind second), verification of findings, reference extraction."""
from __future__ import annotations

import datetime as dt
import json
from importlib import resources
from pathlib import Path

from . import RUBRIC_VERSION, __version__, llm, schema


def prompt(name: str) -> str:
    return resources.files("researchcop").joinpath(f"prompts/{name}.md").read_text(encoding="utf-8")


def doc_dir(cfg, doc_id: str) -> Path:
    return cfg.out / "docs" / doc_id


def result_dir(cfg, doc_id: str) -> Path:
    d = cfg.out / "results" / doc_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def page_numbered_text(cfg, meta: dict) -> str:
    pdir = doc_dir(cfg, meta["id"]) / "pages"
    parts = []
    for i in range(1, meta["n_pages"] + 1):
        t = (pdir / f"p{i:03d}.txt").read_text(encoding="utf-8")
        parts.append(f"=== PAGE {i} ===\n{t}")
    return "\n\n".join(parts)


def _content(cfg, meta: dict, extra_text: str = "") -> list[dict]:
    blocks = []
    pdf = doc_dir(cfg, meta["id"]) / "source.pdf"
    if meta["kind"] == "pdf" and meta["n_pages"] <= cfg["review"]["max_pdf_pages"]:
        blocks.append(llm.pdf_block(pdf))
    src = f"Source: {meta['source']} ({meta['kind']}, {meta['n_pages']} pages)"
    blocks.append({"type": "text", "text": f"{src}\n\n{page_numbered_text(cfg, meta)}"})
    if extra_text:
        blocks.append({"type": "text", "text": extra_text})
    return blocks


def _stamp(meta_llm: dict, role: str) -> dict:
    return {"role": role, "model": meta_llm["model"], "request_id": meta_llm["request_id"],
            "usage": meta_llm["usage"], "tool_version": __version__, "rubric_version": RUBRIC_VERSION,
            "date": dt.datetime.now().isoformat(timespec="seconds")}


def run_review(cfg, meta: dict, role: str = "first", force: bool = False) -> Path:
    out = result_dir(cfg, meta["id"]) / ("review.json" if role == "first" else "second.json")
    if out.exists() and not force:
        return out
    system = prompt("rubric") + "\n\n" + prompt("review").replace("{language}", cfg["review"]["language"])
    tools = llm.tools_for(cfg["review"]["code_execution"], cfg["review"]["web_search"])
    data, m = llm.structured(cfg["models"]["review"], system, _content(cfg, meta), schema.REVIEW,
                             tools=tools, effort=cfg["models"]["effort"])
    data["run"] = _stamp(m, role)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


def run_verify(cfg, meta: dict, force: bool = False) -> Path | None:
    rdir = result_dir(cfg, meta["id"])
    review_file = rdir / "review.json"
    if not review_file.exists():
        return None
    out = rdir / "verify.json"
    done = json.loads(out.read_text(encoding="utf-8")) if out.exists() and not force else {}
    findings = json.loads(review_file.read_text(encoding="utf-8"))["findings"]
    todo = [f for f in findings if f["s"] >= cfg["review"]["verify_min_severity"] and f["id"] not in done]
    if not todo:
        return out
    system = prompt("verify").replace("{language}", cfg["review"]["language"])
    tools = llm.tools_for(cfg["review"]["code_execution"], False)
    for f in todo:
        finding = {k: f[k] for k in ("k", "s", "page_pdf", "quote", "problem", "reported", "expected", "calc", "evidence")}
        extra = "FINDING TO VERIFY:\n" + json.dumps(finding, ensure_ascii=False, indent=1)
        data, m = llm.structured(cfg["models"]["verify"], system, _content(cfg, meta, extra), schema.VERIFY,
                                 tools=tools, effort=cfg["models"]["effort"], max_tokens=32000)
        data["run"] = _stamp(m, "verify")
        done[f["id"]] = data
        out.write_text(json.dumps(done, ensure_ascii=False, indent=1), encoding="utf-8")  # save after each one
    return out


def run_references(cfg, meta: dict, force: bool = False) -> Path:
    out = result_dir(cfg, meta["id"]) / "references.json"
    if out.exists() and not force:
        return out
    data, m = llm.structured(cfg["models"]["references"], prompt("references"),
                             [{"type": "text", "text": page_numbered_text(cfg, meta)}], schema.REFERENCES,
                             effort="low", max_tokens=32000)
    data["run"] = _stamp(m, "references")
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return out
