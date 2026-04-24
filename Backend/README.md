# Backend (HAE-RAG)

This is the backend for the HAE-RAG system.  
It handles everything from data processing to answering queries and checking if the answers are actually correct.

---

## What this backend does

- Takes a user question
- Figures out what the question is about (courses / faculty / calendar)
- Pulls relevant data from the database
- Generates an answer using an LLM
- Verifies each sentence to check if it’s factual or hallucinated
- Sends back a structured response with confidence and evidence

---

## Main Flow

1. Query comes in  
2. Retriever finds relevant chunks  
3. LLM generates answer based on those chunks  
4. Verifier checks each sentence  
5. Response builder formats everything into output  

---

## Important Files

- `main.py`  
  Entry point. Handles API requests and routes everything.

- `retriever.py`  
  Finds relevant data using embeddings and filters.

- `groq_generator.py`  
  Talks to the LLM and generates answers.

- `sentence_verifier.py`  
  Checks each sentence using NLI and labels it.

- `response_builder.py`  
  Builds the final response with labels, confidence, and sources.

- `embed_and_store.py`  
  Converts data into embeddings and stores it in the database.

---

## Data Processing

These files prepare the data before it goes into the system:

- `extract_*` → pulls data from PDFs / JSON  
- `chunk_*` → splits data into smaller pieces  

---

## Data Storage

- Uses ChromaDB for storing embeddings  
- Data is split into chunks and stored with metadata  
- Retrieval is based on semantic similarity  

---

## What makes this different

- Doesn’t blindly trust the LLM  
- Every answer is checked after generation  
- Shows which parts are reliable and which are not  
- Uses simple intent detection to improve accuracy  

---

## Output

The backend doesn’t just return an answer.  
It returns:

- the generated answer  
- sentence-level labels (verified / partial / hallucinated)  
- confidence scores  
- supporting evidence  

---

## Notes

- Models are loaded once and reused  
- No training is happening here, everything is inference-based  
- Designed to be modular, so each part can be replaced easily  

---

That’s it. Backend is basically the brain of the system.
