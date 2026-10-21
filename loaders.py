"""Per-format document loaders, all normalized to the same RawUnit shape."""
from dataclasses import dataclass
import csv
import json

import fitz  # PyMuPDF
from docx import Document as DocxDocument
from bs4 import BeautifulSoup


@dataclass
class RawUnit:
    source: str      # file name the text came from
    unit_id: str      # a stable id within that source (page #, row #, etc.)
    text: str


def load_pdf(path) -> list[RawUnit]:
    units = []
    doc = fitz.open(path)
    for i, page in enumerate(doc):
        text = page.get_text().strip()
        if text:
            units.append(RawUnit(source=str(path), unit_id=f"page-{i+1}", text=text))
    return units


def load_docx(path) -> list[RawUnit]:
    doc = DocxDocument(path)
    units = []
    for i, para in enumerate(doc.paragraphs):
        if para.text.strip():
            units.append(RawUnit(source=str(path), unit_id=f"para-{i+1}", text=para.text.strip()))
    return units


def load_html(path) -> list[RawUnit]:
    soup = BeautifulSoup(open(path, encoding="utf-8").read(), "html.parser")
    units = []
    i = 0
    for h2 in soup.find_all("h2"):
        q = h2.get_text(strip=True)
        p = h2.find_next_sibling("p")
        a = p.get_text(strip=True) if p else ""
        i += 1
        units.append(RawUnit(source=str(path), unit_id=f"qa-{i}", text=f"{q} {a}"))
    return units


def load_csv(path) -> list[RawUnit]:
    units = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            text = "; ".join(f"{k}: {v}" for k, v in row.items())
            units.append(RawUnit(source=str(path), unit_id=f"row-{i+1}", text=text))
    return units


def load_json(path) -> list[RawUnit]:
    data = json.loads(open(path, encoding="utf-8").read())
    units = []
    for i, item in enumerate(data.get("products", [])):
        text = ", ".join(f"{k}: {v}" for k, v in item.items())
        units.append(RawUnit(source=str(path), unit_id=f"item-{i+1}", text=text))
    return units


LOADERS = {
    ".pdf": load_pdf,
    ".docx": load_docx,
    ".html": load_html,
    ".csv": load_csv,
    ".json": load_json,
}


def load_document(path) -> list[RawUnit]:
    from pathlib import Path
    ext = Path(path).suffix.lower()
    if ext not in LOADERS:
        raise ValueError(f"no loader registered for {ext}")
    return LOADERS[ext](path)
