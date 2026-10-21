"""Character-based chunking with overlap."""
from dataclasses import dataclass
from loaders import RawUnit


@dataclass
class Chunk:
    chunk_id: str
    source: str
    text: str


def chunk_units(units: list[RawUnit], max_chars: int = 800, overlap_chars: int = 120) -> list[Chunk]:
    chunks = []
    for unit in units:
        text = unit.text
        if len(text) <= max_chars:
            chunks.append(Chunk(chunk_id=f"{unit.source}:{unit.unit_id}:0", source=unit.source, text=text))
            continue
        start = 0
        idx = 0
        while start < len(text):
            end = min(start + max_chars, len(text))
            chunks.append(Chunk(
                chunk_id=f"{unit.source}:{unit.unit_id}:{idx}",
                source=unit.source,
                text=text[start:end],
            ))
            idx += 1
            if end == len(text):
                break
            start = end - overlap_chars
    return chunks
