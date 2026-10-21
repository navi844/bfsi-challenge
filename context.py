"""Context packing: dedupe retrieved hits and respect a character budget."""


def dedupe(hits: list[dict]) -> list[dict]:
    seen = set()
    out = []
    for h in hits:
        key = h["text"].strip()
        if key in seen:
            continue
        seen.add(key)
        out.append(h)
    return out


def pack_context(hits: list[dict], max_total_chars: int = 2800) -> str:
    hits = dedupe(hits)
    out_parts = []
    budget = max_total_chars
    for h in hits:
        t = h["text"]
        if len(t) > budget:
            if budget <= 0:
                break
            t = t[:budget]
        out_parts.append(t)
        budget -= len(t)
        if budget <= 0:
            break
    return "\n---\n".join(out_parts)
