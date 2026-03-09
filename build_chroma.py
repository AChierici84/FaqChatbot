from __future__ import annotations

import json
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer

DATA_PATH = Path("data/zalando_faq.json")
CHROMA_PATH = Path("data/chroma_db")
COLLECTION_NAME = "zalando_faq"
EMBEDDING_MODEL = "distiluse-base-multilingual-cased-v1"


def main() -> None:
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"File non trovato: {DATA_PATH}. Esegui prima scrape_zalando_faq.py")

    records = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    if not records:
        raise RuntimeError("Il file FAQ è vuoto")

    model = SentenceTransformer(EMBEDDING_MODEL)

    texts = [f"Q: {r['question']}\nA: {r['answer']}" for r in records]
    embeddings = model.encode(texts, normalize_embeddings=True).tolist()

    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    collection = client.get_or_create_collection(name=COLLECTION_NAME)

    ids = [r["id"] for r in records]
    metadatas = [
        {
            "question": r["question"],
            "category_slug": r["category_slug"],
            "category_label": r["category_label"],
            "source_url": r["source_url"],
        }
        for r in records
    ]

    collection.upsert(
        ids=ids,
        documents=texts,
        embeddings=embeddings,
        metadatas=metadatas,
    )

    print(f"Indicizzazione completata: {len(ids)} documenti in '{COLLECTION_NAME}'")
    print(f"Path db: {CHROMA_PATH}")


if __name__ == "__main__":
    main()
