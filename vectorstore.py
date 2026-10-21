"""OpenAI embeddings + ChromaDB wrapper. OpenAI-only, per course convention."""
import os
from pathlib import Path
from dotenv import load_dotenv

import chromadb
from chromadb.utils import embedding_functions

from loaders import load_document
from pii import redact
from chunking import chunk_units, Chunk

STORE_DIR = str(Path(__file__).parent / "chroma_store")
COLLECTION_NAME = "lloyds_bfsi_starter"


def get_embedding_function():
    load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env", override=False)

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Check the .env file in the project root."
        )

    return embedding_functions.OpenAIEmbeddingFunction(
        api_key=api_key, model_name="text-embedding-3-small"
    )


def _chunk_document(path) -> tuple[list[Chunk], int]:
    units = load_document(path)
    redaction_count = 0
    redacted_units = []
    for u in units:
        r = redact(u.text)
        redaction_count += r.redaction_count
        redacted_units.append(type(u)(source=u.source, unit_id=u.unit_id, text=r.text))
    chunks = chunk_units(redacted_units)
    return chunks, redaction_count


def build_or_load_collection(client=None):
    client = client or chromadb.PersistentClient(path=STORE_DIR)
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME, embedding_function=get_embedding_function()
    )
    return collection


def query(collection, text: str, n_results: int = 6) -> list[dict]:
    """n_results defaults generously - a small top_k is the classic way to
    silently lose true matches in a similarity search (see README)."""
    res = collection.query(query_texts=[text], n_results=n_results)
    hits = []
    docs = res.get("documents", [[]])[0]
    metas = res.get("metadatas", [[]])[0]
    dists = res.get("distances", [[]])[0] if res.get("distances") else [None] * len(docs)
    for doc, meta, dist in zip(docs, metas, dists):
        hits.append({"text": doc, "source": (meta or {}).get("source"), "distance": dist})
    return hits


def format_hits(hits: list[dict]) -> str:
    return "\n---\n".join(h["text"] for h in hits)
