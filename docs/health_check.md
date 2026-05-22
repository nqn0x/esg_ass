# ESG Assistant — Health Check Report
Generated: 2026-05-22 11:53:22 UTC

**23/23 checks passed**

| Check | Status | Detail |
|-------|--------|--------|
| File structure | ✅ | 47 files |
| .env loaded | ✅ | True |
| Environment variables | ✅ | base_url=https://albert.api.etalab.gouv.fr |
| Albert list_models | ✅ | 7 models available |
| Albert embeddings | ✅ | dim=1024 |
| Albert chat | ✅ | reply='Got it. **Got it.**' |
| Albert rerank | ✅ | top_score=1.000 top_idx=0 |
| Qdrant index | ✅ | 51 docs, 17,774 chunks, 47 companies, years=['2022', '2023', '2024'] |
| Dense retrieval | ✅ | 8 hits, top=[Apple p.104] score=1.000 |
| Router classification | ✅ | all 4 queries classified correctly |
| Retrieval + reranker | ✅ | 8 hits after reranking, top score=1.000 |
| Tools registry | ✅ | 6 tools: retrieve, list_documents, read_table, compute, compare_documents, fetch |
| compute tool | ✅ | result=16.38% |
| list_documents tool | ✅ | 51 docs, 17,774 chunks |
| fetch_regulation tool | ✅ | content=568 chars |
| retrieve tool | ✅ | 8 hits, class=factual_lookup |
| answer_question (simple) | ✅ | answer=Apple's Scope 1 emissions are 55,200 metric tons of carbon dioxide equiva |
| Verifier | ✅ | verdict=pass, claims=1 |
| Golden set | ✅ | 30 questions, types=['cross_doc_compare', 'factual_lookup', 'numeric_computation |
| Scoreboard | ✅ | 3 runs: ['v01_dense_only', 'v02_hybrid', 'v03_rerank'] | best=v01_dense_only fai |
| Ablation chart | ✅ | exists (52KB) |
| Streamlit components | ✅ | all 6 components importable |
| app.py syntax | ✅ | app.py syntax OK |
