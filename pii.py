"""Regex-based PII redaction applied at ingestion time, before chunking/embedding."""
import re
from dataclasses import dataclass

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
UK_PHONE_RE = re.compile(r"\b0\d{2,4}[\s-]?\d{3,4}[\s-]?\d{3,4}\b")
UK_SORT_CODE_RE = re.compile(r"\b\d{2}-\d{2}-\d{2}\b")


@dataclass
class RedactionResult:
    text: str
    redaction_count: int


def redact(text: str) -> RedactionResult:
    count = 0

    def _sub(pattern, label, s):
        nonlocal count
        new_s, n = pattern.subn(f"[REDACTED_{label}]", s)
        count += n
        return new_s

    text = _sub(EMAIL_RE, "EMAIL", text)
    text = _sub(UK_PHONE_RE, "PHONE", text)
    text = _sub(UK_SORT_CODE_RE, "SORT_CODE", text)
    return RedactionResult(text=text, redaction_count=count)
