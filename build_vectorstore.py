"""Ingestion pipeline: documents -> loaders -> pii -> chunking -> embeddings -> chroma_store.
Run once: python build_vectorstore.py
"""
from pathlib import Path

import chromadb
from vectorstore import build_or_load_collection, _chunk_document, STORE_DIR, COLLECTION_NAME

DOCS_DIR = Path(__file__).parent / "documents"


def main():
    client = chromadb.PersistentClient(path=STORE_DIR)
    collection = build_or_load_collection(client)

    total_redactions = 0
    ids, docs, metas = [], [], []

    for path in sorted(DOCS_DIR.iterdir()):
        if path.suffix.lower() not in {".pdf", ".docx", ".html", ".csv", ".json"}:
            continue
        chunks, redactions = _chunk_document(path)
        total_redactions += redactions
        print(f"{path.name}: {len(chunks)} chunks, {redactions} redactions")
        for c in chunks:
            ids.append(c.chunk_id)
            docs.append(c.text)
            metas.append({"source": c.source})

    if ids:
        collection.upsert(ids=ids, documents=docs, metadatas=metas)

    print(f"\nTotal chunks ingested: {len(ids)}")
    print(f"Total PII redactions across all documents: {total_redactions}")
    print(f"Collection '{COLLECTION_NAME}' ready at {STORE_DIR}")


if __name__ == "__main__":
    main()
