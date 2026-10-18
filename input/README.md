# Eingabeordner

Alles in diesem Ordner außer dieser Datei und den Beispieldateien wird von Git ignoriert.

**Dateien:** PDF (`.pdf`), Webseiten (`.html`, `.htm`), Text (`.txt`, `.md`). Einfach hineinkopieren.

**URLs:** `urls.txt` anlegen, eine Adresse pro Zeile, Kommentare mit `#`. PDFs und Webseiten werden heruntergeladen und wie Dateien behandelt. Vorlage: `urls.example.txt`.

**Gruppen (optional):** `manifest.csv` anlegen, um Texte zu gruppieren und Gruppen im Bericht zu vergleichen. Vorlage: `manifest.example.csv`.

| Spalte | Inhalt |
|---|---|
| `source` | Dateiname oder URL, genau wie in diesem Ordner bzw. in `urls.txt` |
| `group` | Gruppenname, z. B. Zeitschrift, Jahrgang, Institut |
| `label` | kurzer Anzeigename im Bericht (sonst wird der erkannte Titel verwendet) |

Hinweis: PDFs liefern die besten Ergebnisse, weil nur bei ihnen Belegstellen automatisch ausgeschnitten werden. Bei HTML und Text erscheinen die Befunde mit Zitat, aber ohne Bild.
