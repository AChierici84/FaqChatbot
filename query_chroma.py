from __future__ import annotations

from rag_service import answer_question, retrieve_faq_context


def main() -> None:
    query = input("Domanda: ").strip()
    if not query:
        print("Nessuna domanda inserita")
        return

    result = answer_question(query)

    print("\n" + "=" * 60)
    print("Risposta (RAG + LLM)")
    print("=" * 60)
    print(result["answer"])

    if result.get("is_small_talk"):
        print("\n(Intent small-talk rilevato, nessun retrieval FAQ necessario)")
        return

    documents, metadatas, distances = retrieve_faq_context(query, result["top_k"])
    for idx, (doc, meta, score) in enumerate(zip(documents, metadatas, distances), start=1):
        print("\n" + "=" * 60)
        print(f"Risultato #{idx} | distanza: {score:.4f}")
        print(f"Categoria: {meta['category_label']}")
        print(f"Fonte: {meta['source_url']}")
        print(doc[:1200])


if __name__ == "__main__":
    main()
