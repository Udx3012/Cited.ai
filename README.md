# Cited.ai - Document-Grounded Q&A System

Cited.ai is a domain-agnostic, document-grounded Question-Answering system (Retrieval-Augmented Generation) designed to run entirely on free-tier cloud services. It processes uploaded documents (PDFs), indexes them into a vector store using hybrid dense-sparse search, and answers questions strictly based on the content of the documents with inline citations back to the source chunks.

---

## 🏗️ System Architecture

```
[ Frontend (Next.js on Vercel) ] 
       │
       ▼ (Secured via X-API-Key Header)
[ Backend (FastAPI on Render) ]
       ├─► [ In-Memory BM25 Sparse Index ]
       ├─► [ Hugging Face Serverless API ] (Embeddings & Reranking)
       ├─► [ Qdrant Cloud ] (Dense Vector Store & Payload Cache)
       ├─► [ Supabase Storage ] (Original PDF Hosting)
       └─► [ Groq API ] (Llama 3.3 70B / 3.1 8B Synthesis & LLM-as-Judge Verification)
```

---

## 🛠️ Service Setup & Credentials

Cited.ai is built to cost **$0** to run by leveraging the following free-tier APIs. Setup accounts for each service and obtain the keys:

1. **Qdrant Cloud (Vector DB)**:
   - Create a free tier cluster on [Qdrant Cloud](https://cloud.qdrant.io/).
   - Obtain your **Cluster URL** and **API Key**.
2. **Groq Cloud (LLM Engine)**:
   - Create a free account at [Groq Console](https://console.groq.com/).
   - Generate an **API Key** (e.g., `gsk_...`).
3. **Hugging Face (Embeddings & Reranker)**:
   - Sign up/log in to [Hugging Face](https://huggingface.co/).
   - Create a **Read Access Token** at Settings -> Access Tokens (e.g., `hf_...`).
4. **Supabase (Object Storage)**:
   - Create a free project at [Supabase](https://supabase.com/).
   - Go to Storage and create a public bucket named `documents` (or your custom name).
   - Retrieve your **Supabase URL** and **Anon/Service Role Key**.

---

## 🚀 Local Quickstart

### 1. Backend Setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # On Windows: .\.venv\Scripts\activate
pip install -r requirements.txt
```

Create a `.env` file in the `backend/` directory:

```env
APP_NAME=Cited.AI Backend
APP_ENV=development
DEBUG=true

# Security key required for frontend authorization
BACKEND_API_KEY=ca_live_dev_test_key

# CORS settings
ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000

# Service integrations
QDRANT_URL=https://your-qdrant-cluster-url.qdrant.io
QDRANT_API_KEY=your-qdrant-api-key
GROQ_API_KEY=your-groq-api-key
HF_API_KEY=your-hugging-face-token
SUPABASE_URL=https://your-supabase-project.supabase.co
SUPABASE_KEY=your-supabase-key
SUPABASE_BUCKET_NAME=documents
```

Run the backend server:
```bash
python -m uvicorn app.main:app --reload --port 8000
```
Open `http://localhost:8000/docs` to view the FastAPI OpenAPI interactive documentation.

### 2. Frontend Setup

```bash
cd ..
npm install
```

Create a `.env.local` file in the root directory:

```env
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000/api/v1
```

Run the development server:
```bash
npm run dev
```
Open `http://localhost:3000` to interact with the application.

---

## ☁️ Cloud Deployment Guide

### 1. Backend Deployment to Render (Docker Web Service)

Render automatically builds your backend using the provided `Dockerfile`.

1. Push your repository to GitHub.
2. Log in to [Render](https://render.com/) and click **New -> Web Service**.
3. Select your GitHub repository.
4. Configure the service settings:
   - **Name**: `cited-ai-backend`
   - **Environment**: `Docker`
   - **Branch**: `master` (or your main branch)
   - **Plan**: `Free`
5. Go to **Environment** tab and add the environment variables:
   - `QDRANT_URL`
   - `QDRANT_API_KEY`
   - `GROQ_API_KEY`
   - `HF_API_KEY`
   - `SUPABASE_URL`
   - `SUPABASE_KEY`
   - `SUPABASE_BUCKET_NAME`
   - `BACKEND_API_KEY` (Generate a secure random string)
   - `ALLOWED_ORIGINS` (Set this to your Vercel frontend URL, e.g., `https://your-app.vercel.app`)
   - `APP_ENV` = `production`
   - `DEBUG` = `false`
6. Click **Deploy Web Service**. Render will build and expose the service at `https://cited-ai-backend.onrender.com`.

*Note: Render free services spin down after 15 minutes of inactivity. The first request after sleep will take 30-60 seconds to spin back up.*

### 2. Frontend Deployment to Vercel

1. Log in to [Vercel](https://vercel.com/) and click **Add New -> Project**.
2. Select your GitHub repository.
3. Keep default build settings (Next.js project).
4. Add the following environment variable:
   - `NEXT_PUBLIC_BACKEND_URL`: Set to the Render backend URL (e.g., `https://cited-ai-backend.onrender.com/api/v1`).
5. Click **Deploy**. Vercel will build and provision your live frontend application.

---

## 🧪 Verification Checklist

Once deployed, verify the complete end-to-end flow:
1. **Security**: Try hitting the `/api/v1/...` routes without the `X-API-Key` header set to your `BACKEND_API_KEY` to confirm requests are blocked.
2. **Ingestion**: Upload a PDF in the **Documents** page. Check that it parses, uploads to Supabase, generates vector chunks, and indexes them in Qdrant Cloud.
3. **Retrieval & Ask**: Submit a query in the **Chat** interface. Verify the answer is generated with clickable bracketed citations linking back to the exact PDF page.
4. **Guardrails**: Ask an unrelated question (e.g., "Explain quantum computing") and confirm the system refuses to answer from world knowledge, displaying *"Insufficient information found in the uploaded documents."*
