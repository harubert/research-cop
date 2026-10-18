"""End-to-end run with a simulated model (no API calls): ingest -> review -> verify -> report."""
import json

from researchcop import config, ingest, llm, report, review

ARTICLE = """Eine kleine Studie

Befragt wurden 41 Lehrpersonen. Davon gaben 17 Personen an, digitale Medien täglich zu nutzen, das sind 47 %.

Die Ergebnisse zeigen, dass digitale Medien die Motivation erhöhen.

Literatur
Muster, A. (2020). Digitale Medien im Unterricht. Zeitschrift für Beispiele, 3, 1-10.
"""


def fake_structured(model, system, content, schema, **kw):
    if "verdict" in schema["properties"]:
        return ({"verdict": "confirmed", "corrected_severity": 0, "explanation": "17/41 = 41,5 %.", "calc": []},
                {"model": "fake", "request_id": None, "usage": {"input_tokens": 10, "output_tokens": 5}})
    data = {
        "article": {"title": "Eine kleine Studie", "authors": "N. N.", "venue": "Test", "year": "2026", "type": "empirical",
                    "design": "Befragung, n = 41", "profile": "Test.", "verdict": "Test.", "checked_count": 3,
                    "ok": [], "strengths": [], "limits": []},
        "findings": [
            {"id": "B1", "k": "K2", "s": 2, "c": "high", "page_pdf": 1, "page_print": "", "anchor": "das sind 47 %",
             "quote": "das sind 47 %", "problem": "17 von 41 sind 41,5 %, nicht 47 %.", "reported": "47 %", "expected": "41,5 %",
             "calc": ["17 / 41 = 0,4146"], "compare_page": 0, "compare_anchor": "", "compare_label": "", "evidence": "Nachgerechnet."},
            {"id": "B2", "k": "K4", "s": 1, "c": "medium", "page_pdf": 1, "page_print": "", "anchor": "", "quote": "erhöhen",
             "problem": "Kausale Sprache bei Querschnitt.", "reported": "", "expected": "", "calc": [], "compare_page": 0,
             "compare_anchor": "", "compare_label": "", "evidence": "Design."},
        ],
    }
    return data, {"model": "fake", "request_id": None, "usage": {"input_tokens": 100, "output_tokens": 50}}


def test_end_to_end(tmp_path, monkeypatch):
    (tmp_path / "input").mkdir()
    (tmp_path / "input" / "studie.md").write_text(ARTICLE, encoding="utf-8")
    (tmp_path / "input" / "manifest.csv").write_text("source,group,label\nstudie.md,Demo,Kleine Studie\n", encoding="utf-8")
    monkeypatch.setattr(llm, "structured", fake_structured)
    cfg = config.load(root=str(tmp_path))
    metas = ingest.ingest(cfg, log=lambda *_: None)
    assert len(metas) == 1 and metas[0]["group"] == "Demo"
    review.run_review(cfg, metas[0])
    review.run_verify(cfg, metas[0])
    verify = json.loads((tmp_path / "output" / "results" / metas[0]["id"] / "verify.json").read_text(encoding="utf-8"))
    assert list(verify) == ["B1"]                       # only severity >= 2 is re-checked
    data = report.collect(cfg, crops=False, log=lambda *_: None)
    doc = data["docs"][0]
    assert doc["metrics"]["s2"] == 1 and doc["metrics"]["confirmed"] == 1
    out = report.write(cfg, data)
    html = out.read_text(encoding="utf-8")
    assert "Eine kleine Studie" in html and "/*__DATA__*/null" not in html
