from pydantic import BaseModel

class ClassificationOutput(BaseModel):
    is_corporate: bool
    confidence: float
    category: str
