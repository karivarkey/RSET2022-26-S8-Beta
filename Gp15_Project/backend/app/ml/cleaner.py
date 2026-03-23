import re
import nltk
from nltk.corpus import stopwords


import nltk

try:
    nltk.data.find("corpora/stopwords")
except:
    nltk.download("stopwords")


# Make sure stopwords are downloaded at startup
nltk.download('stopwords', quiet=True)
STOP_WORDS = set(stopwords.words("english"))

def clean_email_text(text: str) -> str:
    text = str(text).lower()
    text = re.sub(r'\S+@\S+', ' ', text)       # remove emails
    text = re.sub(r'http\S+', ' ', text)       # remove URLs
    text = re.sub(r'\d+', ' ', text)           # remove numbers
    text = re.sub(r'[^a-z\s]', ' ', text)      # remove punctuation
    text = re.sub(r'\s+', ' ', text).strip()

    tokens = [w for w in text.split() if w not in STOP_WORDS]
    return " ".join(tokens)
