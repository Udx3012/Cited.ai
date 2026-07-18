# Cited.AI — Technical Grounded Q&A Platform (RAG)

Cited.AI is a secure, high-performance Retrieval-Augmented Generation (RAG) system engineered for zero-hallucination document search and grounded question-answering. The system processes uploaded PDF and DOCX files, performs hybrid retrieval, and yields conversational responses with verifiable page-level citation boundaries.

---

## 🏗️ Technical Architecture & Stack

```
[ Client: Next.js + Lenis Smooth Scroll + GSAP Animations ]
                       │
                       ▼ (HTTP POST /completions - API Key Auth)
[ Server: FastAPI Web Service ]
  ├── [ Storage ] ──► Supabase Object Storage (Persistent PDFs/DOCXs)
  ├── [ BM25 Engine ] ──► In-Memory Sparse Indexing
  ├── [ Vector Search ] ──► Qdrant Cloud (1024-Dim Cosine Distance Vectors)
  │
  ▼ [ Grounding & Synthesis Pipeline ]
  ├── Tier 1 (Primary): Voyage AI (voyage-3 embeddings) & Gemini API (gemini-2.5-flash LLM)
  └── Tier 2 (Failover): Hugging Face (BAAI/bge-large-en-v1.5 embeddings) & Groq Cloud (llama-3.3-70b-versatile LLM)
```

### 1. Hybrid Search & Rank Fusion
- **Dense Retrieval**: Context chunks are embedded into a 1024-dimensional vector space. Queries are matched using Cosine Similarity in Qdrant Cloud.
- **Sparse Retrieval**: Uses an Okapi BM25 keyword matching engine.
- **Reciprocal Rank Fusion (RRF)**: Merges dense and sparse candidates into a single ranked list using the standard formula:
  $$RRF\_Score(d) = \sum_{m \in M} \frac{1}{k + r_m(d)}$$
  (where $k = 60$).

### 2. Neural Reranking
- The top fused candidates are scored using a Cross-Encoder Reranking model (`BAAI/bge-reranker-base`) via Hugging Face inference. The top 5 highest-relevance context chunks are selected to build the generation prompt.

### 3. Failover Generation Logic
- **Primary Generator**: Generates answers via **Gemini 2.5 Flash** using a custom prompt instructing the model to output answers along with structured citation indices (e.g. `[1]`, `[2]`) and structured JSON metadata.
- **Failover Dispatcher**: If the primary Voyage AI or Gemini APIs fail (due to rate-limiting, quota exhaustion, or networking issues), the dispatcher automatically routes requests to **Groq (Llama-3.3-70b-versatile)** and **Hugging Face (`bge-large-en-v1.5`)** without interrupting the user session.

### 4. Authentication & Security
- **Supabase Auth**: Implements JWT-based user authentication (standard logins and Google OAuth) with session persistence.
- **API Guardrails**: Frontend-backend communication is protected via `X-API-Key` headers. Input guardrails detect and neutralize prompt injection attempts.

---

## 🛠️ Environment Variables Configuration

### 1. Backend (FastAPI on Render / Server)
Configure these variables in your backend environment:

```env
APP_NAME=Cited.AI Backend
APP_ENV=production
DEBUG=false
BACKEND_API_KEY=your_secure_backend_api_key
ALLOWED_ORIGINS=https://your-frontend.vercel.app

# Qdrant Vector DB
QDRANT_URL=https://your-qdrant-cluster.qdrant.io
QDRANT_API_KEY=your_qdrant_api_key

# Supabase Storage (Bypasses RLS using Service Role Key)
SUPABASE_URL=https://your-supabase-project.supabase.co
SUPABASE_KEY=your_supabase_service_role_key
SUPABASE_BUCKET_NAME=documents

# Primary Tier Models (Voyage & Gemini)
GEMINI_API_KEY=your_gemini_api_key
VOYAGE_API_KEY=your_voyage_api_key

# Backup Tier Models (Groq & Hugging Face)
GROQ_API_KEY=your_groq_api_key
HF_API_KEY=your_hugging_face_read_token
```

### 2. Frontend (Next.js on Vercel / Client)
Configure these variables in your frontend environment:

```env
NEXT_PUBLIC_BACKEND_URL=https://your-backend.onrender.com/api/v1
NEXT_PUBLIC_SUPABASE_URL=https://your-supabase-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your_supabase_public_anon_key
```

---

## 🚀 Local Quickstart

### Backend Setup
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .\.venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```
Interactive docs are served at `http://localhost:8000/docs`.

### Frontend Setup
```bash
cd ..
npm install
npm run dev
```
Open `http://localhost:3000` to interact with the application.
