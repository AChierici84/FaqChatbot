# FAQ Zalando → Embeddings → ChromaDB

Pipeline minimale per:

1. scaricare le FAQ da Zalando,
2. generare embeddings,
3. salvarli in un database vettoriale ChromaDB,
4. generare risposte finali con un LLM usando il contesto FAQ recuperato.

## Requisiti

- Python 3.10+

Installa pacchetti:

```bash
pip install -r requirements.txt
```

## Struttura

- `scrape_zalando_faq.py` → scraping FAQ (Selenium headless) in `data/zalando_faq.json`
- `build_chroma.py` → crea `data/chroma_db` con embeddings
- `query_chroma.py` → query manuale sul DB
- `rag_service.py` → logica RAG condivisa (retrieval + risposta LLM)
- `fastapi_app.py` → API HTTP (`/health`, `/ask`)
- `gradio_app.py` → interfaccia chat di test in Gradio

## Esecuzione

### 1) Estrai FAQ

```bash
python scrape_zalando_faq.py
```

Output: `data/zalando_faq.json`

### 2) Crea embeddings e indicizza in ChromaDB

```bash
python build_chroma.py
```

Output: `data/chroma_db`

### 3) Query FAQ con RAG + LLM

```bash
python query_chroma.py
```

Inserisci una domanda in italiano.

Il flusso è:

1. recupero top-k FAQ da Chroma,
2. passaggio del contesto al LLM,
3. risposta finale grounded sulle FAQ.

### Variabili ambiente opzionali

- `OPENAI_API_KEY`: chiave API per usare il LLM
- `FAQ_LLM_MODEL`: modello chat (default: `gpt-4o-mini`)
- `FAQ_TOP_K`: numero FAQ recuperate da Chroma (default: `3`)

Se `OPENAI_API_KEY` non è impostata, lo script usa un fallback e mostra la FAQ più vicina.

### 4) Avvio API FastAPI

```bash
uvicorn fastapi_app:app --host 0.0.0.0 --port 8000 --reload
```

Endpoint principali:

- `GET /health`
- `POST /ask`

Payload esempio:

```json
{
	"question": "Come posso fare un reso?",
	"top_k": 3
}
```

### 5) Avvio interfaccia Gradio (chat test)

Prima avvia FastAPI su porta 8000, poi in un secondo terminale:

```bash
python gradio_app.py
```

Apri: `http://127.0.0.1:7860`

Variabile opzionale:

- `RAG_API_URL` (default: `http://127.0.0.1:8000/ask`)

## Note tecniche

- Modello embeddings: `distiluse-base-multilingual-cased-v1`
- Collection Chroma: `zalando_faq`
- Le FAQ dipendono dalla struttura HTML corrente di Zalando: in caso di cambi layout, aggiorna i selettori nello script di scraping.
