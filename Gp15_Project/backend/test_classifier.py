from app.ml.classifier import classify_text, classify_proba

text = """
Internal Project Update – Action Required.
Please submit the weekly progress report by tomorrow morning.
"""

label = classify_text(text)
proba_label, confidence = classify_proba(text)

print("LABEL:", label)
print("PROBA LABEL:", proba_label)
print("CONFIDENCE:", confidence)