import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import asyncio
from app.retrieval.bm25 import bm25_service
from app.retrieval.fusion import ReciprocalRankFusion
from app.reranker.rerank import hf_reranker
from rank_bm25 import BM25Okapi


def run_verification():
    # 1. Setup sample document chunks
    chunks = [
        {
            "id": "chunk-1",
            "document_id": "doc-1",
            "chunk_index": 0,
            "page_number": 1,
            "text": "The company achieved total quarterly revenues of $45.2 million in Q3 2023, representing a 14% year-over-year increase.",
            "metadata": {"document_name": "Financial_Report_Q3.pdf", "page": 1, "heading": "Executive Summary", "is_ocr": False}
        },
        {
            "id": "chunk-2",
            "document_id": "doc-1",
            "chunk_index": 1,
            "page_number": 2,
            "text": "Operating expenses were $28.5 million, primarily driven by R&D investments in artificial intelligence and infrastructure.",
            "metadata": {"document_name": "Financial_Report_Q3.pdf", "page": 2, "heading": "Financial Review", "is_ocr": False}
        },
        {
            "id": "chunk-3",
            "document_id": "doc-2",
            "chunk_index": 0,
            "page_number": 1,
            "text": "Risk factors include supply chain disruptions, foreign currency volatility, and macroeconomic uncertainty.",
            "metadata": {"document_name": "Risk_Disclosures.pdf", "page": 1, "heading": "Risk Factors", "is_ocr": False}
        }
    ]

    # 2. Build in-memory BM25 index
    bm25_service.chunks = chunks
    bm25_service.index = BM25Okapi([bm25_service._tokenize(c["text"]) for c in chunks])

    # 3. Test BM25 sparse search
    query = "What were the total quarterly revenues in Q3?"
    sparse_hits = bm25_service.retrieve_sparse(query, top_n=3)
    print("\n--- BM25 SPARSE HITS ---")
    for h in sparse_hits:
        print(f"ID: {h['id']} | BM25 Score: {h['bm25_score']:.4f} | Text: {h['text'][:70]}...")

    assert len(sparse_hits) > 0
    assert sparse_hits[0]["id"] == "chunk-1", "BM25 should rank revenue chunk first!"

    # 4. Simulate dense search hits
    dense_hits = [
        {
            "id": "chunk-1",
            "document_name": "Financial_Report_Q3.pdf",
            "page_number": 1,
            "chunk_index": 0,
            "text": chunks[0]["text"],
            "vector_score": 0.88,
            "bm25_score": 0.0,
            "metadata": chunks[0]["metadata"]
        },
        {
            "id": "chunk-2",
            "document_name": "Financial_Report_Q3.pdf",
            "page_number": 2,
            "chunk_index": 1,
            "text": chunks[1]["text"],
            "vector_score": 0.65,
            "bm25_score": 0.0,
            "metadata": chunks[1]["metadata"]
        }
    ]

    # 5. Test Reciprocal Rank Fusion (RRF)
    fused = ReciprocalRankFusion.fuse_results(dense_results=dense_hits, sparse_results=sparse_hits, limit=3)
    print("\n--- FUSED CANDIDATES (RRF) ---")
    for f in fused:
        print(f"ID: {f['id']} | RRF Score: {f['rerank_score']:.5f} | Vector: {f['vector_score']} | BM25: {f['bm25_score']:.2f}")

    assert fused[0]["id"] == "chunk-1"
    assert fused[0]["page"] == 1
    assert fused[0]["document_name"] == "Financial_Report_Q3.pdf"

    # 6. Test Reranking
    async def test_rerank():
        reranked = await hf_reranker.rerank_chunks(query, fused)
        print("\n--- RERANKED RESULTS ---")
        for r in reranked:
            print(f"ID: {r['id']} | Final Rerank Score: {r.get('rerank_score'):.4f} | Doc: {r['document_name']} (Page {r['page']})")
        assert len(reranked) == len(fused)
        assert reranked[0]["id"] == "chunk-1"


    asyncio.run(test_rerank())
    print("\nALL PIPELINE STAGES (BM25 -> RRF FUSION -> RERANKING) SUCCEEDED 100%!")

if __name__ == "__main__":
    run_verification()
