import joblib
import os
from .cleaner import clean_email_text

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

VECTORIZER_PATH = os.path.join(BASE_DIR, "tfidf_final.joblib")
MODEL_PATH = os.path.join(BASE_DIR, "logistic_final.joblib")

# Load model and vectorizer once at startup
vectorizer = joblib.load(VECTORIZER_PATH)
model = joblib.load(MODEL_PATH)

def classify_text(text: str) -> str:
    cleaned = clean_email_text(text)
    vectorized = vectorizer.transform([cleaned])
    prediction = model.predict(vectorized)[0]

    return "Corporate" if prediction == 1 else "Non-Corporate"



def classify_proba(text: str):
    cleaned = clean_email_text(text)
    vectorized = vectorizer.transform([cleaned])

    probability = model.predict_proba(vectorized)[0]

    # probability for corporate (label=1)
    corp_conf = float(probability[1])

    label = "Corporate" if corp_conf >= 0.5 else "Non-Corporate"

    # choose correct confidence
    confidence = corp_conf if label == "Corporate" else (1 - corp_conf)

    return label, confidence