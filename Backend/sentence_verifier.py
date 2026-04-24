# ================================================================
# backend/sentence_verifier.py  (v2)
# ================================================================

import re
import nltk
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification

nltk.download("punkt",     quiet=True)
nltk.download("punkt_tab", quiet=True)

NLI_MODEL          = "cross-encoder/nli-deberta-v3-small"
VERIFIED_THRESHOLD = 0.7
PARTIAL_THRESHOLD  = 0.4
VERIFIED           = "VERIFIED"
PARTIAL            = "PARTIAL"
HALLUCINATED       = "HALLUCINATED"

# ── List detection ────────────────────────────────────────────────
# Answers that are numbered lists should be verified as ONE unit
LIST_PATTERNS = [
    r"^\s*\d+\.\s+\S",           # starts with "1. something"
    r":\s*\n?\s*\d+\.\s+\S",     # "... are: 1. something"
    r"\s+\d+\.\s+[A-Z]",         # inline "... 1. Name 2. Name"
    r":\s*[-•]\s+\S",            # bullet list
]

def is_list_answer(text: str) -> bool:
    """Detect if the answer is a numbered/bulleted list."""
    for p in LIST_PATTERNS:
        if re.search(p, text):
            return True
    return False


def collapse_list_answer(text: str) -> list[str]:
    """
    For list answers, return as a SINGLE verification unit
    instead of splitting into fragments.
    This prevents name fragments like 'Dr. Vaishali Shinde 2.'
    from being verified in isolation.
    """
    return [text.strip()]


class SentenceVerifier:

    def __init__(self):
        print("Loading NLI model (first run downloads ~180MB)...")
        self.tokenizer = AutoTokenizer.from_pretrained(NLI_MODEL)
        self.model     = AutoModelForSequenceClassification.from_pretrained(NLI_MODEL)
        self.model.eval()
        self.label_map = {0: "contradiction", 1: "entailment", 2: "neutral"}
        print("  NLI model ready\n")

    def split_sentences(self, text: str) -> list[str]:
        """
        Smart sentence splitting:
        - List answers → kept as ONE unit (prevents fragment verification)
        - Normal prose → split by sentence
        """
        if is_list_answer(text):
            return collapse_list_answer(text)

        sentences = nltk.sent_tokenize(text)
        return [s.strip() for s in sentences if len(s.strip()) > 10]

    def nli_score(self, premise: str, hypothesis: str) -> dict:
        # Truncate very long premises to fit model context
        inputs = self.tokenizer(
            premise[:1000],      # cap premise length
            hypothesis,
            return_tensors = "pt",
            truncation     = True,
            max_length     = 512,
            padding        = True,
        )
        with torch.no_grad():
            logits = self.model(**inputs).logits
        probs = torch.softmax(logits, dim=-1)[0].tolist()
        return {
            "contradiction": round(probs[0], 4),
            "entailment":    round(probs[1], 4),
            "neutral":       round(probs[2], 4),
        }

    def verify_sentence(self, sentence: str, chunks: list) -> dict:
        best_entailment = 0.0
        best_chunk      = None
        best_scores     = None

        for chunk in chunks:
            scores = self.nli_score(chunk["text"], sentence)
            if scores["entailment"] > best_entailment:
                best_entailment = scores["entailment"]
                best_chunk      = chunk
                best_scores     = scores

        if best_entailment >= VERIFIED_THRESHOLD:
            label      = VERIFIED
            confidence = best_entailment
        elif best_entailment >= PARTIAL_THRESHOLD:
            label      = PARTIAL
            confidence = best_entailment
        else:
            label      = HALLUCINATED
            confidence = 1.0 - best_entailment

        return {
            "sentence":   sentence,
            "label":      label,
            "confidence": round(confidence, 4),
            "evidence":   best_chunk["text"][:300] if best_chunk else "",
            "source":     best_chunk["metadata"]   if best_chunk else {},
            "nli_scores": best_scores,
        }

    def verify_answer(self, answer: str, chunks: list) -> dict:
        sentences = self.split_sentences(answer)
        results   = []

        is_list = is_list_answer(answer)
        print(f"  Answer type: {'LIST (single unit)' if is_list else 'PROSE'}")
        print(f"  Verifying {len(sentences)} unit(s)...")

        for i, sentence in enumerate(sentences):
            result = self.verify_sentence(sentence, chunks)
            results.append(result)
            print(f"    [{i+1}] {result['label']} ({result['confidence']:.2f})")

        verified     = sum(1 for r in results if r["label"] == VERIFIED)
        partial      = sum(1 for r in results if r["label"] == PARTIAL)
        hallucinated = sum(1 for r in results if r["label"] == HALLUCINATED)
        total        = len(results)

        overall_score = (verified * 1.0 + partial * 0.5) / total if total > 0 else 0

        if overall_score >= 0.8:
            verdict = "TRUSTWORTHY"
        elif overall_score >= 0.5:
            verdict = "MIXED"
        else:
            verdict = "UNRELIABLE"

        return {
            "sentences":            results,
            "overall_score":        round(overall_score, 4),
            "verified_count":       verified,
            "partial_count":        partial,
            "hallucinated_count":   hallucinated,
            "total_sentences":      total,
            "verdict":              verdict,
            "answer_type":          "list" if is_list else "prose",
        }