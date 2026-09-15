# Fast Money Back

Der Antrag auf Abschlagszahlung wird jetzt **vollständig im Browser** erstellt.


## Was sich geändert hat
- **Browser-Oberfläche.** `index.html` startet eine Python-Laufzeit (Pyodide =
  Python als WebAssembly) und führt den unveränderten Kern `fmb_core.py` aus.

## Nutzung
1. `index.html` im Browser öffnen (Doppelklick genügt) — oder auf einer internen
   Seite bereitstellen.
2. Beim **ersten** Start werden Pyodide und die Pakete (pdfplumber, fpdf2, pypdf,
   Pillow) geladen — dafür ist **einmalig Internet** nötig (~10 MB, danach vom
   Browser zwischengespeichert). Danach ist keine Verbindung mehr erforderlich.
3. Abrechnungsantrag **und** alle Belege (PDF/PNG) auswählen → *Analysieren*.
4. Häkchen setzen (Häkchen = Beleg vorhanden), Prozentsatz/Zusatzkosten prüfen.
5. *Antrag erstellen* → das fertige, zusammengeführte PDF wird heruntergeladen.

## Dateien
- `index.html` — die komplette App (Kern ist eingebettet, ein Doppelklick reicht).
- `fmb_core.py` — der Kern (pdfplumber, in-memory). Läuft auch am Desktop:
  `parse_antrag(ordner)` bzw. die `browser_*`-Brücke.
- `build_html.py` — baut `index.html` neu und bettet `fmb_core.py` ein
  (nach Änderungen am Kern: `python build_html.py`).

## Am echten Antrag geprüft
Getestet gegen zwei echte Anträge (`Abrechnungsantrag_9850079.pdf` mit Komma-,
`Abrechnungsantrag_8955650.pdf` mit Punkt-Dezimaltrennung). Der Parser arbeitet
**beschriftungsbasiert** (sucht „Genehmigungsnummer“, „ÜK-Tag“, „Kosten“,
„Betrag“ … und liest die Nachbarzelle) und erkennt beide Formate ohne Änderung.
Korrekt gelesen: Antrags-/Genehmigungsnummer, Name, Personalnummer, Buchungs- und
KLR-Daten, alle Übernachtungen (Anreisetag mit 0 € übersprungen), Verkehrsmittel
und Nebenkosten. Beispiel Rom-Reise: Übernachtung 1.501,62 € + Verkehr 433,70 € +
Neben 1.168,29 € = 3.103,61 €, Abschlag 80 % = 2.482,89 €. Die Sektion
„Zugehörige Dateien“ wird ausgelesen; die Oberfläche markiert fehlende Belege.

## Stempel
Der amtliche THWS-Stempel (`stamp_blank.jpg`) ist **fest eingebettet** – kein
Upload nötig. Die Felder sind an das echte Raster gesetzt: Kapitel, Titel,
FB/Proj (Ebene 1), INS/A-Art (Ebene 2), KST/KTR (Kostenstelle), KOA (Kostenart),
€ (Abschlag, deutsches Format), Haushaltsjahr, Datum (TT.MM.JJJJ). Bei Bedarf
lässt sich im Feld „Stempel-Vorlage“ eine andere Vorlage laden.

## Bitte noch bestätigen
- **Inventarisierung:** Es wird automatisch **NEIN** angekreuzt (Reisekosten sind
  kein Inventar). Falls das anders gehandhabt wird, bitte melden.
- **Haushaltsjahr:** Standard ist das aktuelle Jahr; im Formular frei änderbar.
- **PKW-Fahrten** kamen in beiden Anträgen nicht vor; die km-Logik
  (0,30 / 0,40 €) ist übernommen, aber an echten PKW-Daten noch ungetestet.
- **Pyodide-Version** in `index.html` auf `v0.26.0` gepinnt – gern anheben.
- **Paket-Pins:** `pdfplumber==0.11.9`, `fpdf2==2.8.8`, `pypdf==6.18.1`. Grund:
  Pyodide 0.26.0 liefert Pillow 10.2.0 (Pillow kann nicht von PyPI kommen),
  aber pdfplumber 0.11.10 verlangt Pillow>=12.2.0. Wird Pyodide später auf eine
  Version mit neuerem Pillow angehoben, können die Pins entfernt werden.
- **Netz:** `cdn.jsdelivr.net` und `files.pythonhosted.org` müssen beim ersten
  Start einmalig erreichbar sein.
