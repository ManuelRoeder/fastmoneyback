"""
fmb_core.py -- Fast Money Back core, Java-free and browser-ready.

  * PDF tables are read with **pdfplumber** (pure Python, no Java runtime).
  * Every function works on in-memory bytes -> same code on desktop and in the
    browser (Pyodide).
  * The parser is **label-based**, tuned against a real Abrechnungsantrag: fields
    are located by their caption ("Genehmigungsnummer", "ÜK-Tag", "Kosten",
    "Betrag", ...) and read from the neighbouring cell, so it tolerates the exact
    column count / ordering of the THWS form and small layout drift.
"""

from __future__ import annotations

import io
import json
import logging
import os
import re
from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont
from pypdf import PdfReader, PdfWriter
from fpdf import FPDF

log = logging.getLogger("fmb")

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

UEKOSTEN_LABEL = "ÜK-Tag"          # per-day accommodation cost column
KOSTEN_LABEL = "Kosten"            # Verkehrsmittel cost column
BETRAG_LABEL = "Betrag"            # Nebenkosten amount column
PKW_RATE = 0.30
PKW_RATE_TRIFTIG = 0.40

RECIPIENT_NAME = "Hochschulservice Finanzen"
RECIPIENT_STREET = "Ignatz-Schön-Str. 11"
RECIPIENT_CITY = "97421 Schweinfurt"

FONT_CANDIDATES = [
    "arial.ttf", "Arial.ttf",
    "C:\\Windows\\Fonts\\arial.ttf",
    "/Library/Fonts/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
]

STAMP_POSITIONS = {
    "kapitel": (150, 66), "titel": (470, 66),
    "proj": (330, 120), "art": (350, 172), "kst": (350, 228),
    "koa": (120, 330), "jahr": (255, 434), "datum": (120, 486),
    "abschlag": (415, 356), "x": (620, 539),
}
STAMP_FONT_SIZE = 27
STAMP_SIZE = (1038, 636)

_DATE_RE = re.compile(r"\b\d{1,2}\.\d{1,2}\.\d{2,4}\b")


# --------------------------------------------------------------------------- #
# Errors
# --------------------------------------------------------------------------- #

class FmbError(Exception):
    """Expected, user-presentable error."""


class AntragNotFound(FmbError):
    pass


class PdfReadError(FmbError):
    pass


# --------------------------------------------------------------------------- #
# Data model
# --------------------------------------------------------------------------- #

@dataclass
class LineItem:
    datum: str = ""
    beschreibung: str = ""
    betrag: float = 0.0
    raw: str = ""
    present: bool = True
    is_pkw: bool = False
    pkw_triftig: bool = False
    km: Optional[float] = None
    ort: str = ""

    @property
    def label(self) -> str:
        return "  ".join(p for p in (self.datum, self.beschreibung) if p).strip()


@dataclass
class HeaderData:
    antragsnummer: str = ""
    antragsdatum: str = ""
    reisezusammenfassung: str = ""
    genehmigungsnummer: str = ""


@dataclass
class SenderData:
    name: str = ""
    personalnummer: str = ""
    tel: str = ""
    mail: str = ""


@dataclass
class BookingData:
    kapitel: str = ""
    titel: str = ""
    ebene1: str = ""
    ebene2: str = ""
    kostenart: str = ""
    kostenstelle: str = ""


@dataclass
class ParsedAntrag:
    antrag_pdf: str = ""
    header: HeaderData = field(default_factory=HeaderData)
    sender: SenderData = field(default_factory=SenderData)
    booking: BookingData = field(default_factory=BookingData)
    reisetage: List[LineItem] = field(default_factory=list)
    verkehrsmittel: List[LineItem] = field(default_factory=list)
    nebenkosten: List[LineItem] = field(default_factory=list)
    zugehoerige_dateien: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class Totals:
    reisetage: float = 0.0
    verkehrsmittel: float = 0.0
    nebenkosten: float = 0.0
    zusatz: float = 0.0
    gesamt: float = 0.0
    abschlag: float = 0.0
    pkw_kosten: float = 0.0
    pkw_triftig: bool = False


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def parse_amount(text) -> Optional[float]:
    """Tolerant money parser: '12,50', '1.234,56', '1,234.56', '42 EUR', ints."""
    if text is None:
        return None
    m = re.search(r"\d[\d.,]*\d|\d", str(text))
    if not m:
        return None
    tok = m.group(0)
    if "," in tok and "." in tok:
        tok = tok.replace(".", "").replace(",", ".") if tok.rfind(",") > tok.rfind(".") \
            else tok.replace(",", "")
    elif "," in tok:
        tok = tok.replace(",", ".")
    elif tok.count(".") > 1:
        tok = tok.replace(".", "")
    try:
        return float(tok)
    except ValueError:
        return None


def _safe(text) -> str:
    """latin-1 clamp so fpdf core fonts never crash on stray glyphs."""
    return str(text).encode("latin-1", "replace").decode("latin-1")


def _to_bytes(x) -> bytes:
    """Coerce bytes / bytearray / memoryview / Pyodide JsProxy(Uint8Array)."""
    if x is None:
        return b""
    try:
        return bytes(x)
    except TypeError:
        return bytes(x.to_py())


def _is_date(s: str) -> bool:
    return bool(s and _DATE_RE.search(s))


def _load_font(size: int = STAMP_FONT_SIZE):
    for cand in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(cand, size)
        except (OSError, IOError):
            continue
    try:
        return ImageFont.load_default(size)   # Pillow >= 10.1: scalable default
    except TypeError:
        log.warning("Old Pillow: stamp text falls back to small bitmap font.")
        return ImageFont.load_default()


def _eur_de(x: float) -> str:
    """Format 2482.89 -> '2.482,89' (German)."""
    s = f"{x:,.2f}"  # 2,482.89
    return s.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


# --------------------------------------------------------------------------- #
# Grid: a label-addressable view over one pdfplumber table (all rows kept)
# --------------------------------------------------------------------------- #

class Grid:
    def __init__(self, rows: List[List[Optional[str]]]):
        self.rows = [[self._norm(c) for c in (r or [])] for r in (rows or [[]])]

    @staticmethod
    def _norm(v) -> str:
        if v is None:
            return ""
        return re.sub(r"\s+", " ", str(v)).strip()

    @property
    def title(self) -> str:
        return self.rows[0][0] if self.rows and self.rows[0] else ""

    def cell(self, r: int, c: int, default: str = "") -> str:
        try:
            v = self.rows[r][c]
            return v if v not in (None, "") else default
        except IndexError:
            return default

    def find(self, label: str, exact: bool = True) -> Optional[Tuple[int, int]]:
        L = label.strip().lower()
        for r, row in enumerate(self.rows):
            for c, v in enumerate(row):
                vv = (v or "").strip().lower()
                if (vv == L) if exact else (L in vv):
                    return (r, c)
        return None

    def below(self, label: str, default: str = "") -> str:
        pos = self.find(label)
        return self.cell(pos[0] + 1, pos[1], default) if pos else default

    def right(self, label: str, default: str = "") -> str:
        pos = self.find(label)
        return self.cell(pos[0], pos[1] + 1, default) if pos else default

    def col_map(self, header_row: int) -> Dict[str, int]:
        return {v: c for c, v in enumerate(self.rows[header_row]) if v}


# --------------------------------------------------------------------------- #
# Reading tables (pdfplumber -- no Java)
# --------------------------------------------------------------------------- #

def read_grids(pdf_bytes: bytes) -> List[Grid]:
    try:
        import pdfplumber
    except ImportError as e:
        raise PdfReadError("pdfplumber ist nicht installiert (pip install pdfplumber).") from e
    grids: List[Grid] = []
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                for tbl in page.extract_tables():
                    if tbl:
                        grids.append(Grid(tbl))
    except Exception as e:
        raise PdfReadError(f"PDF konnte nicht gelesen werden: {e}") from e
    if not grids:
        raise PdfReadError("Im PDF wurden keine Tabellen gefunden.")
    return grids


# --------------------------------------------------------------------------- #
# Classification
# --------------------------------------------------------------------------- #

def _classify(grids: List[Grid]) -> dict:
    found: dict = {}
    for i, g in enumerate(grids):
        c = g.title
        if "zusätzliche" in c:
            continue
        if "Antragsnummer" in c:
            found.setdefault("header", g)
        elif "Antragstellerdaten" in c:
            found.setdefault("sender", g)
        elif "Buchungsdaten" in c:
            found.setdefault("booking1", g)
        elif "KLR-Daten" in c:
            found.setdefault("booking2", g)
        elif "Hauptreisedaten" in c:
            found.setdefault("reise", g)
        elif "Verkehrsmittel" in c:
            found.setdefault("verkehr", g)
            if i + 1 < len(grids) and "Mitreisende" not in grids[i + 1].title:
                found["verkehr2"] = grids[i + 1]
        elif "Nebenkosten" in c:
            found.setdefault("neben", g)
        elif "Dateien" in c:
            found.setdefault("dateien", g)
    return found


# --------------------------------------------------------------------------- #
# Extraction (label-based)
# --------------------------------------------------------------------------- #

def _iter_rows_under(g: Grid, header_row: int, date_col: int):
    """Yield data rows after the header until a blank row or the next sub-header
    (a row whose first column is not a date)."""
    for r in range(header_row + 1, len(g.rows)):
        datum = g.cell(r, date_col, "")
        rest = any(g.cell(r, c) for c in range(len(g.rows[r])))
        if not rest:
            continue
        if not _is_date(datum):
            break
        yield r, datum


def _extract_reisetage(g: Grid) -> List[LineItem]:
    pos = g.find(UEKOSTEN_LABEL)
    if not pos:
        return []
    hr, kc = pos
    items: List[LineItem] = []
    for r, datum in _iter_rows_under(g, hr, date_col=0):
        betrag = parse_amount(g.cell(r, kc, ""))
        if not betrag:  # skip missing / 0,00 days
            continue
        items.append(LineItem(datum=datum, beschreibung="Übernachtung (ÜK-Tag)",
                              betrag=betrag, raw=g.cell(r, kc, "")))
    return items


def _extract_verkehr(g: Grid) -> List[LineItem]:
    pos = g.find(KOSTEN_LABEL)
    if not pos:
        return []
    hr, kc = pos
    cmap = g.col_map(hr)
    dc = cmap.get("Datum", 0)
    ac = cmap.get("Verkehrsmittel", 1)
    kmc = cmap.get("km", kc - 1)
    voni = cmap.get("von")
    nachi = cmap.get("nach")
    items: List[LineItem] = []
    for r, datum in _iter_rows_under(g, hr, date_col=dc):
        art = g.cell(r, ac, "")
        raw = g.cell(r, kc, "")
        von = g.cell(r, voni, "") if voni is not None else ""
        nach = g.cell(r, nachi, "") if nachi is not None else ""
        ort = (f"{von} → {nach}".strip(" →") if (von or nach) else "")
        if "PKW" in art:
            km = parse_amount(g.cell(r, kmc, ""))
            triftig = "triftig" in art.lower()
            rate = PKW_RATE_TRIFTIG if triftig else PKW_RATE
            items.append(LineItem(datum=datum, beschreibung=art or "PKW-Fahrt",
                                  betrag=round((km or 0.0) * rate, 2), raw=raw,
                                  is_pkw=True, pkw_triftig=triftig, km=km, ort=ort))
        else:
            betrag = parse_amount(raw)
            if not betrag:
                continue
            items.append(LineItem(datum=datum, beschreibung=art or "Verkehrsmittel",
                                  betrag=betrag, raw=raw, ort=ort))
    return items


def _extract_nebenkosten(g: Grid) -> List[LineItem]:
    pos = g.find(BETRAG_LABEL)
    if not pos:
        return []
    hr, bc = pos
    cmap = g.col_map(hr)
    dc = cmap.get("Datum", 0)
    tc = cmap.get("Nebenkosten(Typ)", 1)
    items: List[LineItem] = []
    for r, datum in _iter_rows_under(g, hr, date_col=dc):
        betrag = parse_amount(g.cell(r, bc, ""))
        if not betrag:
            continue
        items.append(LineItem(datum=datum, beschreibung=g.cell(r, tc, "Nebenkosten"),
                              betrag=betrag, raw=g.cell(r, bc, "")))
    return items


def _extract_dateien(g: Grid) -> List[str]:
    names = []
    for r in range(1, len(g.rows)):
        v = g.cell(r, 0, "")
        if v:
            names.append(v)
    return names


def _extract_orte(g: Grid) -> Dict[str, str]:
    """Map each date to its Geschäftsort (city) from the Hauptreisedaten block."""
    pos = g.find("Geschäftsort(e)")
    if not pos:
        return {}
    hr, oc = pos
    out: Dict[str, str] = {}
    for r in range(hr + 1, len(g.rows)):
        datum = g.cell(r, 0, "")
        if not _is_date(datum):
            continue
        ort = g.cell(r, oc, "")
        if ort:
            out[datum] = ort.split(";")[0].strip()
    return out


def parse_antrag_bytes(pdf_bytes: bytes, name: str = "") -> ParsedAntrag:
    grids = read_grids(pdf_bytes)
    t = _classify(grids)
    p = ParsedAntrag(antrag_pdf=name)

    if "header" in t:
        g = t["header"]
        p.header = HeaderData(antragsnummer=g.below("Antragsnummer"),
                              antragsdatum=g.below("Antragsdatum"),
                              reisezusammenfassung=g.below("Reisezusammenfassung"),
                              genehmigungsnummer=g.below("Genehmigungsnummer"))
    else:
        p.warnings.append("Kopfdaten (Antragsnummer) nicht gefunden.")

    if "sender" in t:
        g = t["sender"]
        vor, nach = g.right("Vorname"), g.right("Name")
        p.sender = SenderData(name=f"{vor} {nach}".strip(),
                              tel=g.below("Telefonnummer"),
                              mail=g.below("E-Mail-Adresse"),
                              personalnummer=g.below("Personalnummer"))
    else:
        p.warnings.append("Antragstellerdaten nicht gefunden.")

    if "booking1" in t:
        g = t["booking1"]
        p.booking.kapitel = g.below("Kapitel")
        p.booking.titel = g.below("Titel")
        p.booking.ebene1 = g.below("Ebene 1")
        p.booking.ebene2 = g.below("Ebene 2")
    else:
        p.warnings.append("Buchungsdaten nicht gefunden.")

    if "booking2" in t:
        g = t["booking2"]
        p.booking.kostenart = g.below("Kostenart")
        p.booking.kostenstelle = g.below("Kostenstelle")
    else:
        p.warnings.append("KLR-Daten nicht gefunden.")

    if "reise" in t:
        p.reisetage = _extract_reisetage(t["reise"])
        orte = _extract_orte(t["reise"])
        for it in p.reisetage:
            it.ort = orte.get(it.datum, "")
    else:
        p.warnings.append("Hauptreisedaten nicht gefunden.")
        orte = {}

    verkehr: List[LineItem] = []
    if "verkehr" in t:
        verkehr += _extract_verkehr(t["verkehr"])
    if "verkehr2" in t:
        verkehr += _extract_verkehr(t["verkehr2"])
    p.verkehrsmittel = verkehr

    if "neben" in t:
        p.nebenkosten = _extract_nebenkosten(t["neben"])
        for it in p.nebenkosten:
            it.ort = orte.get(it.datum, "")

    if "dateien" in t:
        p.zugehoerige_dateien = _extract_dateien(t["dateien"])

    return p


# --------------------------------------------------------------------------- #
# Calculation
# --------------------------------------------------------------------------- #

def compute_totals(parsed: ParsedAntrag, percent: float, zusatz: float = 0.0,
                   manual_total: Optional[float] = None) -> Totals:
    def s(items):
        return round(sum(it.betrag for it in items if it.present and it.betrag), 2)

    rt = round(s(parsed.reisetage) + zusatz, 2)
    vk = s(parsed.verkehrsmittel)
    nk = s(parsed.nebenkosten)
    pkw = round(sum(it.betrag for it in parsed.verkehrsmittel
                    if it.present and it.is_pkw), 2)
    triftig = any(it.pkw_triftig for it in parsed.verkehrsmittel
                  if it.present and it.is_pkw)
    gesamt = manual_total if manual_total is not None else round(rt + vk + nk, 2)
    return Totals(rt, vk, nk, zusatz, gesamt, round(gesamt * percent, 2), pkw, triftig)


# --------------------------------------------------------------------------- #
# Output: stamp -> cover letter -> merge (all in memory)
# --------------------------------------------------------------------------- #

def generate_stamp_image(booking: BookingData, abschlag_str: str, jahr: int,
                         datum: Optional[date] = None,
                         template_bytes: Optional[bytes] = None) -> Image.Image:
    datum = datum or date.today()
    if template_bytes:
        img = Image.open(io.BytesIO(template_bytes)).convert("RGB")
    else:
        img = Image.new("RGB", STAMP_SIZE, "white")
        ImageDraw.Draw(img).rectangle([2, 2, STAMP_SIZE[0] - 3, STAMP_SIZE[1] - 3],
                                      outline="black", width=2)
    img.info.pop("icc_profile", None)  # Pyodide Pillow has no ImageCms/_imagingcms
    draw = ImageDraw.Draw(img)
    font = _load_font()
    datum_str = datum.strftime("%d.%m.%Y")
    P = STAMP_POSITIONS
    for key, val in (("kapitel", booking.kapitel), ("titel", booking.titel),
                     ("proj", booking.ebene1), ("art", booking.ebene2),
                     ("kst", booking.kostenstelle), ("koa", booking.kostenart),
                     ("jahr", jahr), ("datum", datum_str),
                     ("abschlag", abschlag_str), ("x", "X")):
        draw.text(P[key], _safe(val), font=font, fill="black")
    return img


def _appendix_text(display_names: List[str], antrag_name: str) -> str:
    lines = ["Anbei:"]
    if antrag_name:
        lines.append("   - " + antrag_name)
    lines += ["   - " + n for n in display_names]
    return "\n".join(lines)


def build_letter_pdf_bytes(parsed: ParsedAntrag, totals: Totals, percent: float,
                           sachbearbeiter: str, appendix_names: List[str],
                           stamp_img: Image.Image) -> bytes:
    h, s = parsed.header, parsed.sender

    to_lines = [RECIPIENT_NAME]
    if sachbearbeiter.strip():
        to_lines.append("z.H. " + sachbearbeiter.strip())
    to_lines += [RECIPIENT_STREET, RECIPIENT_CITY]
    to_str = "\n".join(to_lines)
    sender_str = "\n".join([s.name, "Pers.Nr.: " + s.personalnummer,
                            "Tel: " + s.tel, "Mail: " + s.mail])
    header_str = ("Antrag auf Abschlagszahlung für die Reise mit der "
                  "Genehmigungsnummer " + h.genehmigungsnummer)

    percent_str = "%.0f" % (percent * 100)
    body = ["Sehr geehrte Damen und Herren,", "",
            f"für meine {h.reisezusammenfassung} (GN-Nr.{h.genehmigungsnummer}) stelle ich hiermit",
            f"einen Antrag auf Abschlagszahlung zu {percent_str} Prozent der angefügten "
            "Rechnungen und Belege."]
    if totals.pkw_kosten > 0:
        rate = PKW_RATE_TRIFTIG if totals.pkw_triftig else PKW_RATE
        km = totals.pkw_kosten / rate if rate else 0
        grund = " (triftiger Grund)" if totals.pkw_triftig else ""
        body.append(f"Die Berechnung enthält PKW-Kosten{grund} in Höhe von "
                    f"{_eur_de(totals.pkw_kosten)} Euro ({km:.0f} km × {_eur_de(rate)} Euro/km).")
    body += [f"Der Gesamtbetrag beläuft sich insgesamt auf {_eur_de(totals.gesamt)} Euro.",
             f"Somit ergibt sich eine Abschlagszahlung von {_eur_de(totals.abschlag)} Euro.",
             "Zur Erleichterung der Bearbeitung habe ich den zugehörigen "
             "Abrechnungsantrag angehängt."]
    main_txt = "\n".join(body)
    finish_str = "Mit freundlichen Grüßen\n\n\n" + s.name
    appendix_str = _appendix_text(appendix_names, parsed.antrag_pdf.rsplit(".pdf", 1)[0])

    stamp_rgb = stamp_img.convert("RGB")
    stamp_rgb.info.pop("icc_profile", None)  # avoid fpdf's ImageCms path in Pyodide
    w, hpx = stamp_rgb.size
    w_mm, h_mm = w * 0.264583 * 0.4, hpx * 0.264583 * 0.4

    pdf = FPDF()
    pdf.add_page()
    pdf.image(stamp_rgb, x=80, y=200, w=w_mm, h=h_mm)
    pdf.set_font("Helvetica", size=10)
    pdf.set_xy(10, 10);  pdf.multi_cell(0, 5, _safe(to_str))
    pdf.set_xy(140, 10); pdf.multi_cell(0, 5, _safe(sender_str))
    pdf.set_font("Helvetica", size=10, style="B")
    pdf.set_xy(10, 55);  pdf.multi_cell(0, 5, _safe(header_str))
    pdf.set_font("Helvetica", size=10)
    pdf.set_xy(10, 72);  pdf.multi_cell(0, 5, _safe(main_txt))
    pdf.set_xy(10, 120); pdf.multi_cell(0, 5, _safe(finish_str))
    pdf.set_xy(10, 140); pdf.multi_cell(0, 5, _safe(appendix_str))
    return bytes(pdf.output())


def png_to_pdf_bytes(png_bytes: bytes) -> bytes:
    buf = io.BytesIO()
    Image.open(io.BytesIO(png_bytes)).convert("RGB").save(buf, "PDF", quality=100)
    return buf.getvalue()


def merge_pdfs_bytes(base_pdf: bytes, appended: List[bytes]) -> bytes:
    writer = PdfWriter()
    for chunk in [base_pdf] + appended:
        try:
            for page in PdfReader(io.BytesIO(chunk)).pages:
                writer.add_page(page)
        except Exception as e:
            log.warning("Segment übersprungen: %s", e)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def _sanitize_filename(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", (name or "unbekannt")).strip("_")


# --------------------------------------------------------------------------- #
# Browser bridge (called from JS via Pyodide). All crossings are str/bytes.
# --------------------------------------------------------------------------- #

_SESSION: Dict[str, object] = {}


def _parsed_to_dict(p: ParsedAntrag) -> dict:
    def items(lst):
        return [{"idx": i, "label": it.label, "betrag": it.betrag,
                 "present": it.present, "is_pkw": it.is_pkw,
                 "datum": it.datum, "ort": it.ort} for i, it in enumerate(lst)]
    return {"antrag_pdf": p.antrag_pdf, "header": asdict(p.header),
            "sender": asdict(p.sender), "booking": asdict(p.booking),
            "reisetage": items(p.reisetage), "verkehrsmittel": items(p.verkehrsmittel),
            "nebenkosten": items(p.nebenkosten),
            "zugehoerige_dateien": p.zugehoerige_dateien, "warnings": p.warnings}


def browser_parse(pdf_bytes, name: str = "") -> str:
    parsed = parse_antrag_bytes(_to_bytes(pdf_bytes), name=name)
    _SESSION["parsed"] = parsed
    return json.dumps(_parsed_to_dict(parsed))


def browser_assemble(params_json: str, files, stamp_bytes=None) -> str:
    import base64
    p: ParsedAntrag = _SESSION.get("parsed")
    if p is None:
        raise FmbError("Kein analysierter Antrag im Speicher – bitte erneut analysieren.")

    prm = json.loads(params_json)
    sel = prm.get("selections", {})
    for key in ("reisetage", "verkehrsmittel", "nebenkosten"):
        flags = sel.get(key, [])
        for i, it in enumerate(getattr(p, key)):
            if i < len(flags):
                it.present = bool(flags[i])

    percent = max(0.01, min(1.0, float(prm.get("percent", 0.8))))
    zusatz = float(prm.get("zusatz") or 0.0)
    manual = prm.get("manual")
    manual = float(manual) if manual not in (None, "") else None
    jahr = int(prm.get("jahr") or date.today().year)
    sachb = str(prm.get("sachbearbeiter") or "")
    totals = compute_totals(p, percent, zusatz, manual)

    try:
        files = files.to_py()
    except AttributeError:
        pass
    named: List[Tuple[str, bytes]] = [(str(n), _to_bytes(b)) for n, b in files]

    stamp_img = generate_stamp_image(
        p.booking, _eur_de(totals.abschlag), jahr,
        template_bytes=_to_bytes(stamp_bytes) if stamp_bytes else None)

    appended_antrag = None
    belege, appendix_names = [], []
    antrag_lower = p.antrag_pdf.lower()
    for fname, data in named:
        low = fname.lower()
        if low == antrag_lower or "abrechnungsantrag" in low:
            appended_antrag = data            # the official form: right after the letter
            continue
        if low.endswith(".pdf"):
            belege.append(data)
            appendix_names.append(fname.rsplit(".pdf", 1)[0])
        elif low.endswith(".png"):
            belege.append(png_to_pdf_bytes(data))
            appendix_names.append(fname.rsplit(".png", 1)[0])

    letter = build_letter_pdf_bytes(p, totals, percent, sachb, appendix_names, stamp_img)
    # order: cover letter -> Abrechnungsantrag -> Belege (receipts) at the very end
    appended = ([appended_antrag] if appended_antrag else []) + belege
    final = merge_pdfs_bytes(letter, appended)
    _SESSION["final_name"] = f"antrag_abschlag_{_sanitize_filename(p.header.genehmigungsnummer)}.pdf"
    return base64.b64encode(final).decode("ascii")


def browser_final_name() -> str:
    return str(_SESSION.get("final_name", "antrag_abschlag.pdf"))


# --------------------------------------------------------------------------- #
# Desktop convenience wrappers (file paths)
# --------------------------------------------------------------------------- #

def find_antrag_pdf(folder: str) -> str:
    if not os.path.isdir(folder):
        raise AntragNotFound(f"Ordner nicht gefunden: {folder}")
    matches = [f for f in os.listdir(folder)
               if f.lower().endswith(".pdf") and "abrechnungsantrag" in f.lower()]
    if not matches:
        raise AntragNotFound("Kein 'Abrechnungsantrag_*.pdf' im Ordner gefunden.")
    if len(matches) > 1:
        raise AntragNotFound("Mehrere Abrechnungsanträge: " + ", ".join(matches))
    return os.path.join(folder, matches[0])


def parse_antrag(folder: str) -> ParsedAntrag:
    path = find_antrag_pdf(folder)
    with open(path, "rb") as fh:
        return parse_antrag_bytes(fh.read(), name=os.path.basename(path))


# --------------------------------------------------------------------------- #
# Self-test (pure logic; no PDF needed)
# --------------------------------------------------------------------------- #

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    assert parse_amount("1.234,56") == 1234.56
    assert parse_amount("292,79 EUR") == 292.79
    assert parse_amount("keine Zahl") is None
    demo = ParsedAntrag(header=HeaderData(genehmigungsnummer="GN-42"))
    demo.reisetage = [LineItem("01.03.", "Übernachtung", 89.0)]
    demo.nebenkosten = [LineItem("02.03.", "Parken", 8.0, present=False)]
    tot = compute_totals(demo, 0.8, zusatz=15.0)
    assert (tot.reisetage, tot.gesamt, tot.abschlag) == (104.0, 104.0, 83.2), tot
    print("Self-test passed:", tot)
