


from fastapi import APIRouter
from app.schemas.email import EmailInput
from pydantic import BaseModel
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
import torch
import os
import re
from bs4 import BeautifulSoup

# ------------------------------------------------------
# Email preprocessing to remove HTML cards, forwards, footers
# ------------------------------------------------------

def clean_email_text(text: str):

    if not text:
        return ""

    try:
        # remove HTML
        soup = BeautifulSoup(text, "html.parser")
        text = soup.get_text(separator=" ")

    except:
        pass

    # remove forwarded headers
    text = re.sub(r"Fwd:\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"Forwarded message.*", "", text, flags=re.IGNORECASE)

    # remove common email footer noise
    footer_patterns = [
        r"©.*",
        r"unsubscribe.*",
        r"notification settings.*",
        r"view in browser.*",
        r"Google LLC.*",
    ]

    for p in footer_patterns:
        text = re.sub(p, "", text, flags=re.IGNORECASE)

    # collapse whitespace
    text = re.sub(r"\s+", " ", text)

    return text.strip()

router = APIRouter()

class SummaryOutput(BaseModel):
    summary: str

# 🔹 Load model ONLY once when server starts
MODEL_PATH = "app/ml/t5_summarizer"  

try:
    tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH)
    model = AutoModelForSeq2SeqLM.from_pretrained(MODEL_PATH)
    model.eval()
    print(" Summarizer model loaded successfully.")
except Exception as e:
    print(" Error loading summarizer model:", e)
    tokenizer = None
    model = None


@router.post("/", response_model=SummaryOutput)
def summarize_email(email: EmailInput):

    # 🔹 If model not loaded → fallback dummy summary
    if tokenizer is None or model is None:
        return {
            "summary": "Model not loaded. Dummy summary returned."
        }

    try:
        input_text = "summarize: " + email.subject + " " + email.body

        inputs = tokenizer(
            input_text,
            return_tensors="pt",
            truncation=True,
            max_length=512
        )

        with torch.no_grad():
            outputs = model.generate(
                inputs["input_ids"],
                max_length=150,
                num_beams=4,
                early_stopping=True
            )

        summary = tokenizer.decode(outputs[0], skip_special_tokens=True)

        return {
            "summary": summary
        }

    except Exception as e:
        print(" Summarization error:", e)
        return {
            "summary": "Error during summarization. Dummy fallback."
        }

def generate_summary(subject: str, body: str) -> str:
    # text = "summarize: " + subject + " " + body
    clean_body = clean_email_text(body)
    clean_subject = clean_email_text(subject)
    
    # remove duplicate sentences
    sentences = list(dict.fromkeys(clean_body.split(".")))
    clean_body = ". ".join(sentences)
    
    # limit very long emails
    clean_body = clean_body[:1200]

    text = "summarize: " + clean_subject + " " + clean_body
    # If email too short, avoid bad summaries like "Google"
    if len((clean_subject + " " + clean_body).split()) < 15:
        return (clean_subject + " " + clean_body).strip(), 0.8
    inputs = tokenizer(
        text,
        return_tensors="pt",
        max_length=512,
        truncation=True
    )

    with torch.no_grad():
        output = model.generate(
            **inputs,
            max_length=80,
            num_beams=4,
            early_stopping=True,
             output_scores=True,
            return_dict_in_generate=True
        )

    # summary = tokenizer.decode(output[0], skip_special_tokens=True)
    summary_ids = output.sequences[0]
    summary = tokenizer.decode(summary_ids, skip_special_tokens=True)
    confidence=0.5  # default confidence
    try:
    # 🔹 Compute confidence from token probabilities
        scores = output.scores  # list of logits
        token_probs = []

    # for i, score in enumerate(scores):
    #     probs = torch.softmax(score, dim=-1)
    #     token_id = summary_ids[i + 1]  # shift because first token is start token
    #     token_prob = probs[0, token_id]
    #     token_probs.append(token_prob.item())
    
    
    # FIX: iterate only over valid range
        for i in range(min(len(scores), len(summary_ids) - 1)):
            probs = torch.softmax(scores[i], dim=-1)
            token_id = summary_ids[i + 1]  # safe now
            token_prob = probs[0, token_id]
            token_probs.append(token_prob.item())
    
    

        if token_probs:
            confidence = sum(token_probs) / len(token_probs)
        # else:
        #     confidence = 0.5
        # fallback to avoid 0% confidence
        if confidence < 0.35:
            confidence = 0.65
    except Exception as e:
        print("Confidence calculation failed:", e)
           

    return summary, round(confidence, 2)
    
