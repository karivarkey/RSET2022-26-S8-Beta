def build_abstractive_input(summary: str, entities: dict) -> str:
    """
    Combine extractive summary + key entities
    into structured prompt for abstractive model.
    Rewrite the summary professionally while preserving ALL key details.

STRICT RULES:
- Do NOT remove agenda items
- Do NOT remove dates, time, or location
- Do NOT remove participants or roles
- Keep logistics information
- If the extractive summary contains lists, keep them as lists
- Do NOT shorten aggressively
    """

    # ---------- Convert entities to readable lines ----------
    entity_lines = []

    if entities.get("DATE"):
        entity_lines.append("Date: " + ", ".join(entities["DATE"]))

    if entities.get("TIME"):
        entity_lines.append("Time: " + ", ".join(entities["TIME"]))

    if entities.get("MONEY"):
        entity_lines.append("Budget: " + ", ".join(entities["MONEY"]))

    if entities.get("GPE"):
        entity_lines.append("Location: " + ", ".join(entities["GPE"]))

    if entities.get("ORG"):
        entity_lines.append("Organization: " + ", ".join(entities["ORG"]))

    # Join entity section
    entity_text = "\n".join(entity_lines)

    # ---------- Final structured prompt ----------
    prompt = f"""

Summary:
{summary}

Key Details:
{entity_text}

"""

    return prompt.strip()
