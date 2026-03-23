from app.ml.classifier import vectorizer

vocab = vectorizer.get_feature_names_out()
print("Vocabulary size:", len(vocab))
print("First 50 words:", vocab[:50])