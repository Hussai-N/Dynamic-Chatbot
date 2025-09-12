from config import CHUNK_SIZE

def chunk_text(text, chunk_size=CHUNK_SIZE):
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size):
        chunks.append(" ".join(words[i:i+chunk_size]))
    return chunks

def chunk_text_smart(text: str, chunk_size_words: int = CHUNK_SIZE, overlap_words: int = 100):
    """
    Sentence-aware chunking with overlap to preserve context across chunk boundaries.
    - Splits text into sentences.
    - Packs sentences into chunks up to chunk_size_words.
    - Adds overlap_words from the end of the previous chunk to the start of the next.
    """
    import re

    # Split into sentences (simple heuristic)
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    chunks = []
    current = []
    current_len = 0

    for s in sentences:
        if not s:
            continue
        words = s.split()
        wlen = len(words)
        if wlen == 0:
            continue

        # If adding this sentence exceeds the limit, finalize current chunk
        if current and (current_len + wlen > chunk_size_words):
            chunk_text_ = " ".join(current).strip()
            if chunk_text_:
                chunks.append(chunk_text_)

            # Prepare overlap for next chunk
            if overlap_words > 0:
                prev_words = chunk_text_.split()
                overlap = " ".join(prev_words[-overlap_words:]) if prev_words else ""
                current = [overlap] if overlap else []
                current_len = len(overlap.split()) if overlap else 0
            else:
                current = []
                current_len = 0

        # Add sentence to current chunk
        current.append(s)
        current_len += wlen

    # Flush remaining
    if current:
        chunk_text_ = " ".join(current).strip()
        if chunk_text_:
            chunks.append(chunk_text_)

    # Ensure at least one chunk
    if not chunks:
        chunks = [text.strip()]

    return chunks

# --- Retrieval helpers for better grounding ---
import re
import math
from typing import List, Dict, Tuple

STOPWORDS = {
    "the","a","an","and","or","if","to","in","on","for","of","is","are","was","were","be",
    "with","as","by","at","it","that","this","from","but","not","can","will","your","you",
    "we","our","their","they","he","she","them","his","her","i","me","my","mine","yours",
    "about","into","out","up","down","over","under","again","further","then","once","here",
    "there","when","where","why","how","all","any","both","each","few","more","most","other",
    "some","such","no","nor","only","own","same","so","than","too","very"
}

def tokenize(text: str) -> List[str]:
    tokens = re.findall(r"[a-zA-Z0-9]+", text.lower())
    return [t for t in tokens if t not in STOPWORDS and len(t) > 2]

def build_idf(chunks: List[str]) -> Dict[str, float]:
    """Compute a simple IDF for tokens across chunks."""
    N = len(chunks) or 1
    df: Dict[str, int] = {}
    for ch in chunks:
        seen = set(tokenize(ch))
        for t in seen:
            df[t] = df.get(t, 0) + 1
    idf: Dict[str, float] = {}
    for t, d in df.items():
        idf[t] = math.log(1.0 + (N / (1.0 + d)))
    return idf

def score_chunks(query: str, chunks: List[str], idf: Dict[str, float]) -> List[Tuple[int, float]]:
    """Score chunks using a simple TF-IDF overlap with the query."""
    q_tokens = tokenize(query)
    if not q_tokens:
        return [(i, 0.0) for i in range(len(chunks))]
    q_set = set(q_tokens)
    scores: List[Tuple[int, float]] = []
    for i, ch in enumerate(chunks):
        ch_tokens = tokenize(ch)
        tf: Dict[str, int] = {}
        for t in ch_tokens:
            tf[t] = tf.get(t, 0) + 1
        score = 0.0
        for t in q_set:
            if t in tf:
                score += tf[t] * idf.get(t, 0.0)
        scores.append((i, score))
    return sorted(scores, key=lambda x: x[1], reverse=True)

def select_top_chunks(question: str, chunks: List[str], idf: Dict[str, float], k: int = 7, max_chars: int = 4000) -> str:
    """Select top-k chunks by score, respecting a character budget. Falls back to sequential if scores are zero."""
    ranked = score_chunks(question, chunks, idf)
    selected: List[str] = []
    total = 0
    count = 0

    # If no chunks or all scores are zero, fall back to sequential selection with higher k
    all_zero = not ranked or (ranked and ranked[0][1] <= 0.0)

    if all_zero:
        k = min(10, len(chunks))  # Select up to 10 chunks if no matches
        for i in range(len(chunks)):
            piece = f"Chunk {i+1}:\n{chunks[i].strip()}\n"
            if total + len(piece) > max_chars:
                continue
            selected.append(piece)
            total += len(piece)
            count += 1
            if count >= k:
                break
    else:
        for idx, _ in ranked:
            piece = f"Chunk {idx+1}:\n{chunks[idx].strip()}\n"
            if total + len(piece) > max_chars:
                continue
            selected.append(piece)
            total += len(piece)
            count += 1
            if count >= k:
                break

    # Always include the first chunk if not already selected
    if chunks and not any("Chunk 1:" in s for s in selected):
        first_piece = f"Chunk 1:\n{chunks[0].strip()}\n"
        if total + len(first_piece) <= max_chars:
            selected.insert(0, first_piece)

    # Fallback: if nothing selected, include the first chunk
    if not selected and chunks:
        selected.append(f"Chunk 1:\n{chunks[0].strip()}\n")
    return "\n".join(selected)
