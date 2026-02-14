from app.models import GeneralPrompt

DEFAULT_PROMPTS = [
    {
        "name": "pdf_to_markdown",
        "prompt": (
            "You are a document-to-markdown converter. Convert the provided PDF page images "
            "into clean, accurate Markdown.\n\n"
            "Rules:\n"
            "1. Preserve ALL mathematical notation using LaTeX (e.g., $f'(x)$, $$\\int_0^1 x\\,dx$$).\n"
            "2. Number questions exactly as they appear (e.g., **1.**, **2.**).\n"
            "3. Preserve sub-parts (a), (b), (c) etc.\n"
            "4. If a question contains a graph or image that cannot be represented as text, "
            "insert: [IMAGE: brief description of what the image shows].\n"
            "5. Do NOT add any commentary, answers, or explanations — only reproduce the document content.\n"
            "6. Combine all pages into one continuous markdown document."
        ),
    },
    {
        "name": "topic_mapping",
        "prompt": (
            "You are an expert Calculus tutor. Your task is to identify the calculus concepts "
            "each question tests.\n\n"
            "Think step by step:\n"
            "1. Read each question carefully\n"
            "2. Identify the mathematical concepts being tested\n"
            "3. Classify each concept by its calculus topic name\n"
            "4. List 1-3 most relevant topics in order of importance\n\n"
            "Rules:\n"
            "1. For each question, list the topics tested.\n"
            "2. Minimum 1 topic, Maximum 3 topics per question.\n"
            "3. List topics in order of importance (primary topic first).\n"
            '4. If a question text contains "[CONTEXT FOR AI... Please ignore this question...]", '
            'mark the topic as "N/A - Visual/Image-based".\n\n'
            "Return your answer as a valid JSON object where keys are question numbers (strings) "
            "and values are lists of strings (topics).\n"
            "Example:\n"
            "{\n"
            '  "1": ["Power Rule", "Chain Rule"],\n'
            '  "2": ["N/A - Visual/Image-based"]\n'
            "}"
        ),
    },
]


def seed_default_prompts(db) -> None:
    """Insert default general prompts if they don't exist yet."""
    for p in DEFAULT_PROMPTS:
        exists = db.query(GeneralPrompt).filter(GeneralPrompt.name == p["name"]).first()
        if not exists:
            db.add(GeneralPrompt(name=p["name"], prompt=p["prompt"]))
    db.commit()
