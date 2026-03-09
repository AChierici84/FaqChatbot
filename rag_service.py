from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import chromadb
from dotenv import load_dotenv
from openai import OpenAI
from sentence_transformers import SentenceTransformer

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")



CHROMA_PATH = "data/chroma_db"
COLLECTION_NAME = "zalando_faq"
EMBEDDING_MODEL = "distiluse-base-multilingual-cased-v1"
DEFAULT_LLM_MODEL = "gpt-4o-mini"



def classify_and_answer_small_talk_with_llm(question: str, llm_model: str) -> dict[str, Any]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return {
            "is_small_talk": False,
            "intent": "faq",
            "response": "",
            "used_fallback": True,
        }

    client = OpenAI(api_key=api_key)
    system_prompt = (
        "Sei un classificatore conversazionale per un assistente FAQ e devi restituire SOLO JSON valido. "
        "Classifica il messaggio utente come small_talk o faq. "
        "Se è small_talk, genera anche una risposta breve, naturale e cordiale in italiano. "
        "Intent small_talk ammessi: greeting, thanks, how_are_you, goodbye, bot_identity, small_talk_other. "
        "Se non è small_talk, usa intent='faq' e response=''."
    )

    user_prompt = (
        f"Messaggio utente: {question}\n\n"
        "Rispondi in JSON con questo schema esatto:\n"
        "{\n"
        '  "is_small_talk": true/false,\n'
        '  "intent": "greeting|thanks|how_are_you|goodbye|bot_identity|small_talk_other|faq",\n'
        '  "response": "string"\n'
        "}"
    )

    try:
        completion = client.chat.completions.create(
            model=llm_model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        content = completion.choices[0].message.content or "{}"
        parsed = json.loads(content)

        is_small_talk = bool(parsed.get("is_small_talk", False))
        intent = str(parsed.get("intent", "faq"))
        response = str(parsed.get("response", "")).strip()

        if is_small_talk and not response:
            response = "Certo 🙂 Dimmi pure come posso aiutarti."

        return {
            "is_small_talk": is_small_talk,
            "intent": intent,
            "response": response,
            "used_fallback": False,
        }
    except Exception:
        return {
            "is_small_talk": False,
            "intent": "faq",
            "response": "",
            "used_fallback": True,
        }


@lru_cache(maxsize=1)
def get_embedding_model() -> SentenceTransformer:
    return SentenceTransformer(EMBEDDING_MODEL)


@lru_cache(maxsize=1)
def get_collection() -> Any:
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    return client.get_collection(COLLECTION_NAME)


def retrieve_faq_context(query: str, top_k: int) -> tuple[list[str], list[dict], list[float]]:
    model = get_embedding_model()
    query_embedding = model.encode(query, normalize_embeddings=True).tolist()

    collection = get_collection()
    result = collection.query(query_embeddings=[query_embedding], n_results=top_k)

    documents = result["documents"][0]
    metadatas = result["metadatas"][0]
    distances = result["distances"][0]
    return documents, metadatas, distances


def build_context_block(documents: list[str], metadatas: list[dict], distances: list[float]) -> str:
    blocks = []
    for idx, (doc, meta, score) in enumerate(zip(documents, metadatas, distances), start=1):
        blocks.append(
            "\n".join(
                [
                    f"[FAQ {idx}]",
                    f"Categoria: {meta.get('category_label', 'N/A')}",
                    f"Fonte: {meta.get('source_url', 'N/A')}",
                    f"Distanza: {score:.4f}",
                    f"Contenuto: {doc}",
                ]
            )
        )
    return "\n\n".join(blocks)


def answer_with_llm(user_question: str, context_block: str, llm_model: str) -> tuple[str, bool]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        fallback = "[FALLBACK] OPENAI_API_KEY non impostata. Uso la FAQ più vicina come risposta:\n\n"
        return fallback + context_block.split("\n\n")[0], True

    client = OpenAI(api_key=api_key)
    system_prompt = (
        "Sei un assistente FAQ Zalando. "
        "Rispondi in italiano in modo chiaro e sintetico. "
        "Usa esclusivamente le informazioni nel contesto FAQ fornito. "
        "Se il contesto non basta, dichiara esplicitamente che non hai abbastanza informazioni "
        "e suggerisci di contattare l'assistenza Zalando."
    )

    user_prompt = (
        f"Domanda utente:\n{user_question}\n\n"
        f"Contesto FAQ recuperato:\n{context_block}\n\n"
        "Fornisci:\n"
        "risposta finale breve\n"
        "una sezione con i link usati."
    )

    completion = client.chat.completions.create(
        model=llm_model,
        temperature=0.1,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    content = completion.choices[0].message.content or "Nessuna risposta generata dal modello."
    return content, False


def answer_question(question: str, top_k: int | None = None, llm_model: str | None = None) -> dict[str, Any]:
    llm_model_value = llm_model or os.getenv("FAQ_LLM_MODEL", DEFAULT_LLM_MODEL)

    small_talk_llm = classify_and_answer_small_talk_with_llm(question, llm_model_value)
    if small_talk_llm["is_small_talk"]:
        return {
            "answer": small_talk_llm["response"],
            "used_fallback": small_talk_llm["used_fallback"],
            "model": llm_model_value,
            "top_k": 0,
            "sources": [],
            "intent": small_talk_llm["intent"],
            "is_small_talk": True,
        }

    top_k_value = top_k if top_k is not None else int(os.getenv("FAQ_TOP_K", "3"))

    documents, metadatas, distances = retrieve_faq_context(question, top_k_value)
    context_block = build_context_block(documents, metadatas, distances)
    answer, used_fallback = answer_with_llm(question, context_block, llm_model_value)

    sources = []
    for meta, distance in zip(metadatas, distances):
        sources.append(
            {
                "category": meta.get("category_label", "N/A"),
                "url": meta.get("source_url", "N/A"),
                "distance": distance,
            }
        )

    return {
        "answer": answer,
        "used_fallback": used_fallback,
        "model": llm_model_value,
        "top_k": top_k_value,
        "sources": sources,
        "intent": "faq",
        "is_small_talk": False,
    }
