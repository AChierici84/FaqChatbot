import json
from datasets import Dataset
from transformers import AutoTokenizer,pipeline
from transformers import AutoModelForSequenceClassification, TrainingArguments, Trainer


with open("smallTalks/intent_examples.json", encoding="utf-8") as f:
    intent_examples = json.load(f)

texts = []
labels = []
for label, examples in intent_examples.items():
    for ex in examples:
        texts.append(ex)
        labels.append(label)

data = Dataset.from_dict({"text": texts, "label": labels})
label_list = sorted(set(labels))
label2id = {label: i for i, label in enumerate(label_list)}
id2label = {i: label for label, i in label2id.items()}

# Converti etichette testuali in ID numerici
data = data.map(lambda x: {"label": label2id[x["label"]]})

tokenizer = AutoTokenizer.from_pretrained("distilbert-base-multilingual-cased")

def tokenize(example):
    return tokenizer(example["text"], padding="max_length", truncation=True)

data_tokenized = data.map(tokenize, batched=True)

model = AutoModelForSequenceClassification.from_pretrained(
    "distilbert-base-multilingual-cased",
    num_labels=len(label_list),
    id2label=id2label,
    label2id=label2id
)

training_args = TrainingArguments(
    output_dir="./results",
    evaluation_strategy="no",
    num_train_epochs=4,
    per_device_train_batch_size=8,
    logging_steps=10,
    save_strategy="epoch",
    save_total_limit=1,
)

trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=data_tokenized,
    tokenizer=tokenizer,
)

trainer.train()

trainer.save_model("./smalltalk_model")
tokenizer.save_pretrained("./smalltalk_model")

classifier = pipeline("text-classification", model="./smalltalk_model", tokenizer="./smalltalk_model")

text="sei stato utilissimo come sempre, grazie e arrivederci"
result = classifier(text)[0]
label = result["label"]
score = result["score"]
print(label+"("+score+")")