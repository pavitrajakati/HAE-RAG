# HAE-RAG: Hallucination-Aware Explainable Retrieval-Augmented Generation

## Overview

HAE-RAG is a Retrieval-Augmented Generation (RAG) framework designed for university academic query resolution with an emphasis on factual reliability and explainability. The system integrates structured institutional data sources with large language models and a post-generation verification layer to ensure that responses are grounded in evidence.

The primary objective is to mitigate hallucinations in large language model outputs while providing transparent, sentence-level validation of generated answers.

## Key Features

- Retrieval-Augmented Generation (RAG) for improved factual grounding  
- Intent-aware retrieval using lightweight pattern-based classification  
- Sentence-level hallucination verification using NLI  
- Explainable outputs with confidence scores and supporting evidence  
- Modular architecture for extensibility  

## System Architecture

The system follows a four-stage pipeline:

1. Query Interface: Accepts user queries through a FastAPI endpoint  
2. Retriever: Performs semantic search over ChromaDB using embeddings  
3. Generator: Produces responses using Llama-3 via Groq  
4. Verifier: Applies NLI model to validate each sentence  

Each component is implemented as an independent module :contentReference[oaicite:0]{index=0}.

## Knowledge Base Construction

The knowledge base is built from:

- Curriculum documents (PDF)  
- Faculty profiles (JSON)  
- Academic calendar documents (PDF)  

Each source is parsed, chunked, and embedded using all-MiniLM-L6-v2. The embeddings are stored in ChromaDB with cosine similarity indexing.

## Retrieval Strategy

Queries are classified into:

- Course-related  
- Faculty-related  
- Calendar-related  

Each type uses customized retrieval parameters (top-k and filters) to improve precision.

## Answer Generation

Retrieved context is passed to the LLM with controlled prompting to:

- Restrict answers to available evidence  
- Avoid speculation  
- Maintain concise outputs  

Low temperature is used for better factual consistency.

## Hallucination Verification

Each generated sentence is evaluated using an NLI model (DeBERTa-v3):

- VERIFIED (≥ 0.7)  
- PARTIAL (0.4 – 0.7)  
- HALLUCINATED (< 0.4)  

An overall trust score is computed from sentence-level results.

## Project Structure

├── Backend/
│ ├── extract_.py
│ ├── chunk_.py
│ ├── embed_and_store.py
│ ├── retriever.py
│ ├── groq_generator.py
│ ├── sentence_verifier.py
│ ├── response_builder.py
│ └── main.py
│
├── frontend/
│ ├── index.html
│ ├── package.json
│ ├── vite.config.js
│ └── tailwind.config.js
│
└── data/
├── JSON files
├── PDFs
└── ChromaDB storage



## Technology Stack

- Backend: Python, FastAPI  
- Frontend: React (Vite), Tailwind CSS  
- Vector DB: ChromaDB  
- Embeddings: all-MiniLM-L6-v2  
- LLM: Llama-3 (Groq API)  
- Verification: DeBERTa-v3 (NLI)  

## API Endpoints

- GET /health — Health check  
- POST /ask — Query endpoint  
- GET /stats — Knowledge base statistics  

## Performance

- Factual Accuracy: 91.7%  
- Hallucination Rate: 8.3%  
- Average Latency: ~2.4 seconds  

