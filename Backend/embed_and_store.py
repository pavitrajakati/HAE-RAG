# ================================================================
# embed_and_store.py
# Embeds all 517 chunks and stores them in ChromaDB
#
# Run once to build the vector DB. After this, retriever.py
# queries it every time a student asks a question.
#
# Install first:
#   pip install chromadb sentence-transformers
# ================================================================

import json
import os
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

# -------------------------------------------------------
# CONFIG
# -------------------------------------------------------
CHUNK_FILES = [
    "data/chunks_courses.json",
    "data/chunks_faculty.json",
    "data/chunks_calendar.json",
]

# Where ChromaDB stores its files on disk
CHROMA_DIR = "data/chromadb"

# Collection name — one collection for everything
COLLECTION_NAME = "pesu_cse"

# Embedding model — free, local, no API key needed
# all-MiniLM-L6-v2: fast, 384 dimensions, good for short academic text
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# How many chunks to embed at once (reduce if RAM is low)
BATCH_SIZE = 64


# -------------------------------------------------------
# LOAD ALL CHUNKS
# -------------------------------------------------------
def load_all_chunks():
    all_chunks = []
    for filepath in CHUNK_FILES:
        with open(filepath, encoding="utf-8") as f:
            chunks = json.load(f)
        all_chunks.extend(chunks)
        print(f"  Loaded {len(chunks):>4} chunks from {filepath}")
    return all_chunks


# -------------------------------------------------------
# FLATTEN METADATA
# ChromaDB only accepts str/int/float/bool in metadata —
# no lists or dicts. Convert any lists to comma-separated strings.
# -------------------------------------------------------
def flatten_metadata(meta):
    flat = {}
    for k, v in meta.items():
        if isinstance(v, list):
            flat[k] = ", ".join(str(x) for x in v)
        elif isinstance(v, dict):
            flat[k] = json.dumps(v)
        elif v is None:
            flat[k] = ""
        else:
            flat[k] = v
    return flat


# -------------------------------------------------------
# EMBED AND STORE
# -------------------------------------------------------
def embed_and_store(chunks, collection, model):
    total = len(chunks)
    stored = 0

    for i in range(0, total, BATCH_SIZE):
        batch = chunks[i : i + BATCH_SIZE]

        ids       = [c["chunk_id"] for c in batch]
        texts     = [c["text"] for c in batch]
        metadatas = [flatten_metadata(c["metadata"]) for c in batch]

        # Generate embeddings
        embeddings = model.encode(texts, show_progress_bar=False).tolist()

        # Store in ChromaDB
        collection.add(
            ids        = ids,
            documents  = texts,
            embeddings = embeddings,
            metadatas  = metadatas,
        )

        stored += len(batch)
        print(f"  Stored {stored}/{total} chunks...", end="\r")

    print(f"  Stored {stored}/{total} chunks. Done!     ")


# -------------------------------------------------------
# VERIFY STORAGE
# -------------------------------------------------------
def verify(collection):
    count = collection.count()
    print(f"\n✅ ChromaDB collection '{COLLECTION_NAME}' has {count} chunks")

    # Test query
    test_queries = [
        "What is Python course about?",
        "Who teaches machine learning?",
        "When is ISA 1?",
    ]

    print("\n--- Quick retrieval test ---")
    for query in test_queries:
        results = collection.query(
            query_texts = [query],
            n_results   = 2,
        )
        top = results["documents"][0][0]
        meta = results["metadatas"][0][0]
        print(f"\nQ: {query}")
        print(f"  → [{meta.get('chunk_type')}] {top[:120]}...")


# -------------------------------------------------------
# MAIN
# -------------------------------------------------------
def main():
    print("=== PESU CSE RAG — Embed & Store ===\n")

    # 1. Load chunks
    print("Loading chunks...")
    chunks = load_all_chunks()
    print(f"  Total: {len(chunks)} chunks\n")

    # 2. Load embedding model
    print(f"Loading embedding model: {EMBEDDING_MODEL}")
    print("  (First run downloads ~90MB — cached after that)")
    model = SentenceTransformer(EMBEDDING_MODEL)
    print("  Model ready\n")

    # 3. Set up ChromaDB
    os.makedirs(CHROMA_DIR, exist_ok=True)
    client = chromadb.PersistentClient(path=CHROMA_DIR)

    # Delete existing collection if re-running (clean rebuild)
    try:
        client.delete_collection(COLLECTION_NAME)
        print(f"Deleted existing collection '{COLLECTION_NAME}' for clean rebuild")
    except Exception:
        pass

    collection = client.create_collection(
        name     = COLLECTION_NAME,
        metadata = {"hnsw:space": "cosine"},  # cosine similarity for text
    )
    print(f"Created collection: {COLLECTION_NAME}\n")

    # 4. Embed and store
    print("Embedding and storing chunks...")
    embed_and_store(chunks, collection, model)

    # 5. Verify
    verify(collection)

    print("\n✅ Done! Vector DB saved at:", CHROMA_DIR)
    print("Next step: run retriever.py")


if __name__ == "__main__":
    main()