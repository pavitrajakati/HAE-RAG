# ================================================================
# backend/retriever.py  (v3)
# ================================================================

import re
import chromadb
from sentence_transformers import SentenceTransformer

CHROMA_DIR      = "data/chromadb"
COLLECTION_NAME = "pesu_cse"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
DEFAULT_TOP_K   = 5

# Course list queries
LIST_PATTERNS = [
    r"\b(list|show|give|what are|all|every)\b.*\b(course|elective|subject)\b",
    r"\b(elective|subject|course)s?\b.*\b(sem|semester)\b",
    r"\b(sem|semester)\b.*\b(elective|course|subject)s?\b",
]

# Faculty domain queries — route to domain_summary chunks
WHO_TEACHES_PATTERNS = [
    r"\bwho teaches\b",
    r"\bwho work[s]? on\b",
    r"\bwho (?:are|is) (?:the )?(?:expert|specialist)\b",
    r"\bteach(?:es|ing)?\b.*\b(ml|dl|nlp|ai|cv)\b",
    r"\bfaculty\b.*\b(machine learning|deep learning|computer vision|nlp|natural language|cyber|cloud|iot|blockchain|image processing|generative ai)\b",
    r"\b(machine learning|deep learning|computer vision|nlp|natural language|cyber security|cloud computing|iot|blockchain|image processing|generative ai)\b.*\bfaculty\b",
    r"\b(machine learning|deep learning|computer vision|nlp|natural language|cyber security|cloud computing|iot|blockchain|image processing|generative ai)\b.*\b(teacher|professor|instructor|staff|teach|expert)\b",
    r"\bwho.*\b(machine learning|deep learning|computer vision|nlp|cyber|cloud|iot)\b",
]

# Email/contact queries
EMAIL_PATTERNS = [
    r"\bemail\b", r"\bcontact\b", r"\bmail\b",
]


class Retriever:

    def __init__(self):
        print("Loading retriever...")
        self.model      = SentenceTransformer(EMBEDDING_MODEL)
        client          = chromadb.PersistentClient(path=CHROMA_DIR)
        self.collection = client.get_collection(COLLECTION_NAME)
        total           = self.collection.count()
        print(f"  Connected to ChromaDB — {total} chunks available\n")

    def _detect_top_k(self, query: str) -> int:
        q = query.lower()
        for p in LIST_PATTERNS:
            if re.search(p, q):
                return 15           # need many chunks for course lists
        for p in WHO_TEACHES_PATTERNS:
            if re.search(p, q):
                return 5            # domain_summary is one chunk — 5 is enough
        for p in EMAIL_PATTERNS:
            if re.search(p, q):
                return 8            # need profile chunks which have emails
        return DEFAULT_TOP_K

    def _detect_filters(self, query: str) -> dict | None:
        q = query.lower()

        # Email → faculty source only
        for p in EMAIL_PATTERNS:
            if re.search(p, q):
                return {"source": "faculty"}

        # Who teaches / domain query → domain_summary chunks only
        # These have ALL faculty per domain in one chunk with emails
        for p in WHO_TEACHES_PATTERNS:
            if re.search(p, q):
                return {"$and": [
                {"source":     {"$eq": "faculty"}},
                {"chunk_type": {"$eq": "domain_summary"}},
            ]}

        # Calendar queries
        if re.search(
            r"\b(holiday|isa|ptm|ccm|fam|schedule|exam|semester start|result|lwd|last working)\b",
            q
        ):
            return {"source": "calendar"}

        return None

    def retrieve(self, query: str, top_k: int = None, filters: dict = None) -> list:
        if top_k is None:
            top_k = self._detect_top_k(query)
        if filters is None:
            filters = self._detect_filters(query)

        where = filters if filters else None

        results = self.collection.query(
            query_texts = [query],
            n_results   = top_k,
            where       = where,
            include     = ["documents", "metadatas", "distances"],
        )

        chunks = []
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            score = round(1 - dist, 4)
            chunks.append({"text": doc, "metadata": meta, "score": score})

        return chunks

    def retrieve_for_verification(self, sentence: str, top_k: int = 3) -> list:
        return self.retrieve(sentence, top_k=top_k, filters=None)

    def format_context(self, chunks: list) -> str:
        lines = []
        for i, chunk in enumerate(chunks, 1):
            source = chunk["metadata"].get("source", "")
            ctype  = chunk["metadata"].get("chunk_type", "")
            lines.append(f"[{i}] ({source}/{ctype}) {chunk['text']}")
        return "\n\n".join(lines)


# ── Test ────────────────────────────────────────────────────────
if __name__ == "__main__":
    r = Retriever()

    tests = [
        "Who teaches machine learning?",
        "Who teaches machine learning and what is their email?",
        "Which faculty work on deep learning?",
        "List the electives of 6th semester",
        "When is ISA 1 for odd semester 2025?",
        "What is the Python course about?",
        "What is the email of Ankita Singhai?",
    ]

    for q in tests:
        top_k   = r._detect_top_k(q)
        filters = r._detect_filters(q)
        chunks  = r.retrieve(q)
        print(f"\nQ: {q}")
        print(f"   top_k={top_k} | filters={filters}")
        for c in chunks[:2]:
            print(f"   [{c['score']:.2f}] {c['metadata'].get('chunk_type'):20s} | {c['text'][:80]}...")