from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import gradio as gr
import requests
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

API_ASK_URL = os.getenv("RAG_API_URL", "http://127.0.0.1:8000/ask")
DEFAULT_TOP_K = int(os.getenv("FAQ_TOP_K", "3"))

SUGGESTIONS = [
    "Come posso fare un reso?",
    "Dov'è il mio pacco?",
    "Quali sono i metodi di pagamento?",
    "Come posso annullare un ordine?",
]

WELCOME_TEXT = (
    "Ciao! Posso aiutarti sulle FAQ Zalando. "
    "Chiedimi ad esempio resi, spedizioni, pagamenti o ordini."
)

CSS = """
body { background: #f5f5f5; font-family: Arial, sans-serif; }
#app-wrap { max-width: 980px; margin: 0 auto; }
#hero h1 { font-size: 48px; line-height: 1.1; margin: 0; }
#hero p { font-size: 16px; color: #222; }
#intro-bubble {
  background: #ececec;
  border-radius: 18px;
  padding: 16px 18px;
  margin: 10px 0 8px 0;
}
#chatbot { min-height: 420px; border-radius: 16px; border: 1px solid #e3e3e3; }
#input-row { position: sticky; bottom: 8px; background: transparent; }
#message-box textarea { font-size: 18px !important; }
.suggestion button {
  border-radius: 999px !important;
  border: 1px solid #222 !important;
}
"""


def ask_rag_api(question: str, top_k: int) -> tuple[str, list[dict[str, Any]]]:
    response = requests.post(
        API_ASK_URL,
        json={"question": question, "top_k": top_k},
        timeout=120,
    )
    response.raise_for_status()
    payload = response.json()

    answer = payload.get("answer", "Nessuna risposta disponibile.")
    sources = payload.get("sources", [])
    return answer, sources


def format_sources(sources: list[dict[str, Any]]) -> str:
    if not sources:
        return ""

    links = []
    for src in sources[:3]:
        url = src.get("url", "")
        category = src.get("category", "FAQ")
        if url:
            links.append(f"- [{category}]({url})")

    if not links:
        return ""

    return "\n\nFonti FAQ:\n" + "\n".join(links)


def send_message(message: str, chat_history: list[dict[str, str]], top_k: int):
    text = (message or "").strip()
    if not text:
        return "", chat_history

    if chat_history is None:
        chat_history = []

    try:
        answer, sources = ask_rag_api(text, top_k)
        final_answer = answer 
        #+ format_sources(sources)
    except Exception as ex:
        final_answer = f"Errore nel contattare la RAG API: {ex}"

    updated = chat_history + [
        {"role": "user", "content": text},
        {"role": "assistant", "content": final_answer},
    ]
    return "", updated


def send_suggestion(suggestion: str, chat_history: list[dict[str, str]], top_k: int):
    return send_message(suggestion, chat_history, top_k)


def make_suggestion_handler(suggestion: str):
    def handler(chat_history: list[dict[str, str]], top_k: int):
        _, updated_chat = send_message(suggestion, chat_history, top_k)
        return updated_chat

    return handler


with gr.Blocks() as demo:
    with gr.Column(elem_id="app-wrap"):
        with gr.Row(equal_height=True):
            with gr.Column(scale=10, elem_id="hero"):
                gr.Markdown("# Ciao!")
            with gr.Column(scale=2, min_width=90):
                reset_btn = gr.Button("Reset", variant="secondary")

        gr.Markdown(f"<div id='intro-bubble'>{WELCOME_TEXT}</div>")

        chatbot = gr.Chatbot(
            value=[],
            elem_id="chatbot",
            show_label=False,
            height=430,
        )

        with gr.Row():
            top_k = gr.Slider(minimum=1, maximum=10, value=DEFAULT_TOP_K, step=1, label="Top K FAQ")

        with gr.Row():
            for suggestion in SUGGESTIONS:
                gr.Button(suggestion, elem_classes=["suggestion"]).click(
                    fn=make_suggestion_handler(suggestion),
                    inputs=[chatbot, top_k],
                    outputs=[chatbot],
                )

        with gr.Row(elem_id="input-row"):
            msg = gr.Textbox(
                placeholder="Inserisci il tuo messaggio",
                lines=1,
                show_label=False,
                container=True,
                elem_id="message-box",
                scale=10,
            )
            send_btn = gr.Button("Invia", variant="primary", scale=1)

        send_btn.click(send_message, inputs=[msg, chatbot, top_k], outputs=[msg, chatbot])
        msg.submit(send_message, inputs=[msg, chatbot, top_k], outputs=[msg, chatbot])
        reset_btn.click(lambda: ("", []), outputs=[msg, chatbot])


if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860, theme=gr.themes.Soft(), css=CSS)
