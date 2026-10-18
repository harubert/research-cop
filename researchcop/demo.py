"""Fictional demo data to try the dashboard without an API key. All texts, authors and findings are invented."""
from __future__ import annotations

import json
import random
import shutil
from pathlib import Path

from . import config, report

TEXTS = [
    ("Gruppe A", "empirical", "Lernmotivation im Mathematikunterricht der Sekundarstufe", "A. Muster & B. Beispiel", 14),
    ("Gruppe A", "empirical", "Feedback in der Schreibdidaktik: eine Interventionsstudie", "C. Probe", 11),
    ("Gruppe A", "practice report", "Lesepatenschaften an einer Volksschule", "D. Fiktiv", 5),
    ("Gruppe B", "conceptual", "Digitale Grundbildung zwischen Anspruch und Praxis", "E. Erfunden", 9),
    ("Gruppe B", "empirical", "Belastungserleben im Berufseinstieg", "F. Demo & G. Test", 16),
    ("Gruppe B", "review", "Forschendes Lernen in der Lehrkräftebildung: ein Überblick", "H. Platzhalter", 12),
    ("Gruppe B", "method note", "Planspiele im Wirtschaftsunterricht", "I. Modell", 3),
]
PROBLEMS = {
    "K1": ("Im Text zitiert, fehlt im Literaturverzeichnis.", "", ""),
    "K2": ("Der Prozentwert passt nicht zur angegebenen Basis.", "43 % (17 von 41)", "41,5 % (17 / 41)"),
    "K3": ("Die Reliabilität der Skala wird nicht berichtet; die Stichprobe ist ausschließlich selbstselektiert.", "", ""),
    "K4": ("Kausale Formulierung („bewirkt“) bei querschnittlichem Design ohne Kontrollgruppe.", "", ""),
    "K5": ("Die zitierte Quelle stützt die Aussage nicht; dort wird ein anderer Befund berichtet.", "", ""),
    "K6": ("Längere Passage nahezu wörtlich aus einer nicht genannten Quelle.", "", ""),
}


def build(outdir: Path) -> Path:
    rnd = random.Random(7)
    if outdir.exists():
        shutil.rmtree(outdir)
    for i, (group, typ, title, authors, pages) in enumerate(TEXTS, 1):
        doc_id = f"demo-{i:02d}"
        ddir, rdir = outdir / "docs" / doc_id, outdir / "results" / doc_id
        ddir.mkdir(parents=True); rdir.mkdir(parents=True)
        meta = {"id": doc_id, "kind": "pdf", "source": f"demo/{doc_id}.pdf", "file": f"{doc_id}.pdf", "n_pages": pages,
                "title_hint": "", "group": group, "label": title + " (fiktiv)", "chars": pages * 3500}
        (ddir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
        weights = [0.32, 0.18, 0.18, 0.14, 0.12, 0.06]
        n = rnd.randint(max(2, pages // 3), pages + 3)
        findings, verify = [], {}
        for j in range(1, n + 1):
            k = rnd.choices(list(PROBLEMS), weights)[0]
            s = rnd.choices([1, 2, 3], [0.55, 0.37, 0.08] if group == "Gruppe A" else [0.6, 0.35, 0.05])[0]
            if k == "K1":
                s = 1
            prob, rep, exp = PROBLEMS[k]
            findings.append({
                "id": f"B{j}", "k": k, "s": s, "c": rnd.choice(["high", "high", "medium", "low"]),
                "page_pdf": rnd.randint(1, pages), "page_print": "", "anchor": "", "quote": "Beispielzitat aus dem fiktiven Text",
                "problem": prob, "reported": rep if k == "K2" else "", "expected": exp if k == "K2" else "",
                "calc": ["17 / 41 = 0,4146 → 41,5 %"] if k == "K2" else [],
                "compare_page": 0, "compare_anchor": "", "compare_label": "",
                "evidence": "Nachgerechnet mit den Werten aus Tabelle 2." if k == "K2" else "Abgleich Text ↔ Literaturverzeichnis.",
            })
            if s >= 2:
                v = rnd.choices(["confirmed", "partly", "refuted", "unclear"], [0.78, 0.1, 0.07, 0.05])[0]
                verify[f"B{j}"] = {"verdict": v, "corrected_severity": 1 if v == "partly" else 0,
                                   "explanation": {"confirmed": "Am Original nachvollzogen.", "partly": "Problem besteht, ist aber formal.",
                                                   "refuted": "Der Wert steht korrekt in Tabelle 3; Lesefehler des Erstgutachtens.",
                                                   "unclear": "Mit dem vorliegenden Material nicht entscheidbar."}[v], "calc": []}
        run = {"role": "first", "model": "demo (fiktive Daten)", "usage": {"input_tokens": 0, "output_tokens": 0}, "date": "2026-01-01T00:00"}
        review = {"article": {"title": title + " (fiktiv)", "authors": authors, "venue": "Beispielzeitschrift", "year": "2025", "type": typ,
                              "design": "Fiktives Design für die Demo.", "profile": "Fiktiver Inhalt.", "verdict": "Fiktive Gesamteinschätzung.",
                              "checked_count": rnd.randint(15, 45), "ok": ["Summen in Tabelle 1 korrekt."], "strengths": ["Klare Fragestellung."],
                              "limits": ["Rohdaten nicht verfügbar."]}, "findings": findings, "run": run}
        (rdir / "review.json").write_text(json.dumps(review, ensure_ascii=False), encoding="utf-8")
        (rdir / "verify.json").write_text(json.dumps(verify, ensure_ascii=False), encoding="utf-8")
        refs = []
        for r in range(rnd.randint(8, 25)):
            cls = rnd.choices(["confirmed", "title_differs", "near_miss", "wrong_doi", "doi_not_registered", "not_found"],
                              [0.8, 0.06, 0.05, 0.03, 0.02, 0.04])[0]
            refs.append({"n": r + 1, "title": f"Fiktiver Titel {r + 1}", "authors": "Autor, X.", "year": "2020",
                         "doi": f"10.0000/demo.{100 + r}" if cls in ("near_miss", "wrong_doi", "confirmed") else "", "type": "journal",
                         "class": cls, "resolved": {"status": "ok", "title": "Ein anderes Werk im selben Heft"} if cls in ("near_miss", "wrong_doi") else None,
                         "search": {"similarity": 0.97, "title": f"Fiktiver Titel {r + 1}", "doi": f"10.0000/demo.{101 + r}"} if cls == "near_miss" else None})
        counts = {}
        for r in refs:
            counts[r["class"]] = counts.get(r["class"], 0) + 1
        (rdir / "sources.json").write_text(json.dumps({"references": refs, "text_dois": [], "counts": counts}, ensure_ascii=False), encoding="utf-8")
        if i in (1, 5):   # blind second review for two texts
            second = [dict(f, id=f"Z{n}") for n, f in enumerate(rnd.sample(findings, max(1, int(len(findings) * 0.7))), 1)]
            second += [dict(findings[0], id="Z99", page_pdf=pages, quote="anderes Zitat", problem="Nur im Zweitgutachten gefunden.")]
            (rdir / "second.json").write_text(json.dumps({"article": review["article"], "findings": second, "run": run}, ensure_ascii=False), encoding="utf-8")
    cfg = config.load(root=str(outdir), overrides={"paths": {"output": "."}})
    return report.write(cfg, report.collect(cfg, crops=False, log=lambda *_: None))
