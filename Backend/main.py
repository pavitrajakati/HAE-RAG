# ================================================================
# backend/main.py
# FastAPI backend — production-ready
#
# Install:
#   pip install fastapi uvicorn groq chromadb sentence-transformers
#              nltk torch transformers python-dotenv
#
# Run:
#   uvicorn main:app --reload --port 8000
# ================================================================

import os
import time
import uuid
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from retriever          import Retriever
from groq_generator     import GroqGenerator
from sentence_verifier  import SentenceVerifier
from response_builder   import ResponseBuilder

load_dotenv()

# ── App ──────────────────────────────────────────────────────────
app = FastAPI(
    title       = "PESU CSE RAG API",
    description = "Hallucination-Aware Explainable RAG for PES University CSE",
    version     = "1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins     = ["http://localhost:5173", "http://localhost:3000"],
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)

# ── Load components once at startup ──────────────────────────────
print("\n🚀 Initialising PESU CSE RAG system...")

retriever = Retriever()
generator = GroqGenerator()
verifier  = SentenceVerifier()
builder   = ResponseBuilder()

print("✅ All components ready\n")


# ── Request / Response models ─────────────────────────────────────
class AskRequest(BaseModel):
    query:   str
    top_k:   Optional[int] = 5
    filters: Optional[dict] = None


class HealthResponse(BaseModel):
    status:        str
    chunks_indexed: int
    version:       str


# ── Routes ───────────────────────────────────────────────────────
@app.get("/", tags=["health"])
def root():
    return {"message": "PESU CSE RAG API is running"}


@app.get("/health", response_model=HealthResponse, tags=["health"])
def health():
    return {
        "status":         "ok",
        "chunks_indexed": retriever.collection.count(),
        "version":        "1.0.0",
    }


@app.post("/ask", tags=["rag"])
def ask(req: AskRequest):
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    request_id = str(uuid.uuid4())[:8]
    start      = time.time()

    print(f"\n[{request_id}] Query: {req.query[:80]}")

    try:
        # Step 1 — Retrieve
        t1     = time.time()
        chunks = retriever.retrieve(req.query, top_k=req.top_k, filters=req.filters)
        print(f"[{request_id}] Retrieved {len(chunks)} chunks in {time.time()-t1:.2f}s")

        # Step 2 — Generate
        t2         = time.time()
        gen_result = generator.generate(req.query, chunks)
        print(f"[{request_id}] Generated answer in {time.time()-t2:.2f}s")

        # Step 3 — Verify
        t3         = time.time()
        ver_result = verifier.verify_answer(gen_result["answer"], chunks)
        print(f"[{request_id}] Verified {ver_result['total_sentences']} sentences in {time.time()-t3:.2f}s")

        # Step 4 — Build response
        response = builder.build(req.query, gen_result, ver_result)

        elapsed = round(time.time() - start, 2)
        response["meta"] = {
            "request_id":   request_id,
            "elapsed_s":    elapsed,
            "model":        gen_result.get("model", ""),
            "chunks_used":  len(chunks),
        }

        print(f"[{request_id}] Done in {elapsed}s | verdict={ver_result['verdict']}")
        return response

    except Exception as e:
        print(f"[{request_id}] ERROR: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stats", tags=["rag"])
def stats():
    count = retriever.collection.count()
    sample = retriever.collection.get(limit=5)
    sources = {}
    for meta in sample.get("metadatas", []):
        s = meta.get("source", "unknown")
        sources[s] = sources.get(s, 0) + 1
    return {
        "total_chunks": count,
        "sample_sources": sources,
    }