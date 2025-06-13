from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from sentence_transformers import SentenceTransformer, util
import spacy
import json
import random

app = Flask(__name__)
CORS(app)

# Carica modello spaCy italiano
nlp = spacy.load("it_core_news_md")

# Carica modello multilingua SBERT
model = SentenceTransformer("distiluse-base-multilingual-cased-v1")

# Carica FAQ
with open("./faq/zalandoHtml.json", encoding="utf-8") as f:
    faq_data = json.load(f)

faq_questions = [item["question"] for item in faq_data]
faq_answers = {item["question"]: item["answer"] for item in faq_data}
faq_category = {}
for item in faq_data:
    if (item["category"] in faq_category):
        faq_category[item["category"]]=faq_category[item["category"]]+"\n"+item["question"]
    else:
        faq_category[item["category"]]=item["question"]

with open("./faq/zalandoCategory.json", encoding="utf-8") as f:
    faq_category_answers= json.load(f)

with open("./smallTalks/small_talks.json", encoding="utf-8") as f:
    SMALL_TALK= json.load(f)

with open("./smallTalks/intent_examples.json", encoding="utf-8") as f:
    INTENT_EXAMPLES= json.load(f)

faq_embeddings = model.encode([q.lower().replace("zalando","") for q in faq_questions], convert_to_tensor=True)
intent_example_embeddings = {
    intent: model.encode(examples, convert_to_tensor=True)
    for intent, examples in INTENT_EXAMPLES.items()
}

def classify_intent(user_input):
    doc_input = nlp(user_input.lower().replace('zalando',''))
    doc_no_stop_words = nlp(' '.join([t.lemma_ for t in doc_input if not t.is_punct and not t.is_stop]))
    print(doc_no_stop_words)
    keywordsQuery = nlp(' '.join(token.lemma_ for token in nlp(user_input) if token.pos_ in {"NOUN", "VERB", "PROPN"} and not token.is_stop))
    print(keywordsQuery)

    # Controllo FAQ
    best_faq = None
    best_faq_score = 0.70
    for q in faq_questions:
        q_no_stop_words = nlp(' '.join([t.lemma_ for t in nlp(q) if not t.is_punct and not t.is_stop]))
        score = doc_no_stop_words.similarity(q_no_stop_words)
        if score > best_faq_score:
            best_faq_score = score
            best_faq = q
            print(q_no_stop_words)
            print(q)
            print(score)
    if best_faq:
        return "faq", best_faq


    # Controllo small talk
    best_intent = None
    best_score = 0.65
    for intent, examples in INTENT_EXAMPLES.items():
        for ex in examples:
            score = doc_input.similarity(nlp(ex))
            if score > best_score:
                best_score = score
                best_intent = intent

    if best_intent:
        return best_intent, None

    return "default", None


def classify_intent_bert(user_input, context):
    user_input_processed = user_input.lower().replace("zalando", "")
    embedding_user = model.encode(user_input_processed, convert_to_tensor=True)
    user_input_processed_context = context+" "+user_input.lower().replace("zalando", "")
    embedding_user_context = model.encode(user_input_processed_context, convert_to_tensor=True)

    # Cerca miglior corrispondenza FAQ
    best_faq = None
    best_faq_score = 0.5
    for i, q_embedding in enumerate(faq_embeddings):
        score = util.cos_sim(embedding_user, q_embedding).item()
        if score > best_faq_score:
            best_faq_score = score
            best_faq = faq_questions[i]
    if best_faq:
        return "faq", best_faq


    # Cerca miglior small talk intent (usando SBERT)
    best_intent = None
    best_intent_score = 0.65
    for intent, embeddings in intent_example_embeddings.items():
        for i, ex_embedding in enumerate(embeddings):
            score = util.cos_sim(embedding_user, ex_embedding).item()
            if score > best_intent_score:
                best_intent_score = score
                best_intent = intent
    if best_intent:
        return best_intent, None
    

    return "default", None

def generate_response(intent, faq_question=None):
    if intent == "faq" and faq_question:
        return faq_answers.get(faq_question, "Mi dispiace, non ho trovato una risposta a questa domanda.")
    elif intent == "category" and faq_question:
        return random.choice(SMALL_TALK["category"])+faq_category_answers.get(faq_question, "Mi dispiace, non ho trovato una risposta a questa domanda.")
    elif intent in SMALL_TALK:
        return random.choice(SMALL_TALK[intent])
    else:
        return random.choice(SMALL_TALK["default"])

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/ask", methods=["POST"])
def ask():
    conversation_history = request.json.get("history", [])  # lista di messaggi precedenti
    user_message = request.json.get("message", "")

    context=""

    #if (len(conversation_history)>0):
        # puoi concatenare la storia per il contesto o usarla per modificare classificazione
    #    context = " ".join([msg for msg in conversation_history[-1:]])


    intent, faq_question = classify_intent_bert(user_message,context)
    bot_response = generate_response(intent, faq_question)
    return jsonify({"response": bot_response})


if __name__ == "__main__":
    app.run(debug=True)
