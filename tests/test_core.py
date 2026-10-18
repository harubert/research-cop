from researchcop import evidence, sources, stats
from researchcop.pdftext import Word


def words(text, y=100.0):
    out, x = [], 50.0
    for t in text.split():
        out.append(Word(x, y, x + 8 * len(t), y + 10, t)); x += 8 * len(t) + 4
    return out


def test_locate_exact_and_hyphenated():
    ws = words("Die Ergebnisse zeigen einen deutlichen Zuwachs der Lern- motivation in Klasse 7")
    score, box, sel = evidence.locate(ws, "zeigen einen deutlichen Zuwachs")
    assert score == 1.0 and [w.text for w in sel] == ["zeigen", "einen", "deutlichen", "Zuwachs"]
    score, _, sel = evidence.locate(ws, "Zuwachs der Lernmotivation in Klasse")
    assert score == 1.0 and sel[-1].text == "Klasse"


def test_locate_rejects_weak_match():
    assert evidence.locate(words("ganz anderer Text auf dieser Seite"), "zeigen einen deutlichen Zuwachs") is None


def test_column_detection_keeps_hit_column():
    left = words("links steht ein Absatz mit Text", y=100) + words("noch eine Zeile links", y=114)
    right = [Word(w.x0 + 300, w.y0, w.x1 + 300, w.y1, w.text) for w in words("rechte Spalte mit anderem Inhalt", y=100)]
    x0, x1 = evidence.column(left + right, (50, 100, 90, 110), 600)
    assert x0 >= 49 and x1 < 340


def test_doi_cleaning_and_line_break():
    assert sources.clean_doi("https://doi.org/10.1000/abc.123).") == "10.1000/abc.123"
    found = sources.dois_in_text(["Text https://doi.org/10.1016/j.edurev.2013.\n02.002 weiter"])
    assert "10.1016/j.edurev.2013.02.002" in found[0]["variants"]


def test_classify_near_miss():
    ref = {"title": "A meta-analysis of cooperative learning", "doi": "10.1016/j.edurev.2013.01.002"}
    res = {"status": "ok", "title": "The use of scoring rubrics revisited"}
    search = {"similarity": 0.98, "title": "A meta-analysis of cooperative learning", "doi": "10.1016/j.edurev.2013.02.002"}
    assert sources.classify(ref, res, search) == "near_miss"
    assert sources.classify({"title": "X", "doi": "10.1/x"}, {"status": "ok", "title": "X"}, None) == "confirmed"


def f(i, page, quote, k="K2", s=2):
    return {"id": i, "page_pdf": page, "quote": quote, "anchor": "", "problem": quote, "k": k, "s": s}


def test_match_reviews():
    a = [f("B1", 3, "47 Prozent der Befragten stimmen zu"), f("B2", 9, "Literaturverzeichnis fehlt Eintrag Müller")]
    b = [f("Z1", 3, "47 Prozent der Befragten stimmen zu laut Text"), f("Z2", 12, "völlig anderer Befund")]
    m = stats.match_reviews(a, b)
    assert m["matches"][0]["first"] == "B1" and m["matches"][0]["second"] == "Z1"
    assert m["only_first"] == ["B2"] and m["only_second"] == ["Z2"]


def test_verification_changes_counts():
    fs = stats.apply_verification([f("B1", 1, "x", s=3), f("B2", 1, "y", s=2), f("B3", 1, "z", s=1)],
                                  {"B1": {"verdict": "partly", "corrected_severity": 2, "explanation": ""},
                                   "B2": {"verdict": "refuted", "corrected_severity": 0, "explanation": ""}})
    m = stats.doc_metrics({"kind": "pdf", "n_pages": 2}, fs)
    assert (m["s1"], m["s2"], m["s3"], m["refuted"]) == (1, 1, 0, 1)
    assert m["per_page"] == 1.0
