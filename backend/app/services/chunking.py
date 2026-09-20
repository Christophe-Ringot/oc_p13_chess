import re

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def _split_long_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Decoupe un texte trop long en respectant les frontieres de phrases,
    pour eviter de couper un mot en deux (ce qui degraderait l'embedding)."""
    sentences = [s.strip() for s in _SENTENCE_SPLIT_RE.split(text) if s.strip()] or [text]

    chunks: list[str] = []
    current = ""

    for sentence in sentences:
        candidate = f"{current} {sentence}".strip() if current else sentence

        if len(candidate) <= chunk_size:
            current = candidate
            continue

        if current:
            chunks.append(current)
            tail = current[-overlap:] if overlap else ""
            current = f"{tail} {sentence}".strip()
        else:
            current = sentence

        while len(current) > chunk_size:
            chunks.append(current[:chunk_size])
            current = current[chunk_size - overlap :]

    if current:
        chunks.append(current)

    return chunks


def split_into_chunks(text: str, chunk_size: int = 800, overlap: int = 150) -> list[str]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]

    chunks: list[str] = []
    current = ""

    for paragraph in paragraphs:
        candidate = f"{current}\n\n{paragraph}" if current else paragraph

        if len(candidate) <= chunk_size:
            current = candidate
            continue

        if current:
            chunks.append(current)
            tail = current[-overlap:] if overlap else ""
            current = f"{tail}\n\n{paragraph}".strip()
        else:
            current = paragraph

        if len(current) > chunk_size:
            split = _split_long_text(current, chunk_size, overlap)
            chunks.extend(split[:-1])
            current = split[-1] if split else ""

    if current:
        chunks.append(current)

    return chunks
