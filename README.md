# ESG Assistant

A local RAG pipeline that discovers, indexes, and answers questions about corporate sustainability reports. Built with Albert (French government LLM API), Qdrant, and Streamlit.

## What it does

- **Indexes** ESG, sustainability, CSRD, and annual reports from company websites
- **Retrieves** relevant evidence using hybrid dense + BM25 search with cross-encoder reranking
- **Answers** analyst questions with grounded, cited responses
- **Compares** metrics across companies side-by-side
- **Auto-fills** CSRD ESRS E1 compliance forms from indexed reports
- **Evaluates** every pipeline change against a 30-question golden set before keeping it

## Architecture

```
PDFs → pdfplumber → chunks → quality score → Albert embeddings → Qdrant
                                                                      ↓
User question → router → dense search + BM25 → RRF fusion → reranker → top-8 chunks
                                                                              ↓
                                              Albert synthesize → cited answer + verifier
```

**Tech stack:**
- **LLM + Embeddings**: [Albert API](https://albert.api.etalab.gouv.fr) (French government, OpenAI-compatible)
- **Vector DB**: Qdrant embedded (local, no server needed)
- **BM25**: FastEmbed sparse vectors
- **UI**: Streamlit
- **Eval**: RAGAS metrics (faithfulness, answer relevancy, context precision, context recall)

## Corpus

- **51 reports** across **47 companies** (S&P 500 subset)
- **Years**: 2022, 2023, 2024
- **17,774 chunks** indexed
- Companies include: Apple, Microsoft, Amazon, Google, Meta, Tesla, Nike, JPMorgan, Walmart, and more

## Quick start

### 1. Clone and install

```bash
git clone <repo>
cd esg_assistant
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.template .env
# Edit .env with your Albert API key
```

`.env` contents:
```
ALBERT_BASE_URL=https://albert.api.etalab.gouv.fr
ALBERT_API_KEY=your_key_here
ALBERT_CHAT_MODEL=mistralai/Ministral-3-8B-Instruct-2512
ALBERT_STRONG_MODEL=mistralai/Mistral-Small-3.2-24B-Instruct-2506
ALBERT_EMBED_MODEL=BAAI/bge-m3
ALBERT_RERANK_MODEL=BAAI/bge-reranker-v2-m3
```

### 3. Test Albert connection

```bash
python -m scripts.probe_albert
```

### 4. Add PDF reports

Place PDFs in `data/pdfs/` and edit `ingest_manifest.yaml`:

```yaml
pdfs:
  - path: data/pdfs/apple_2024.pdf
    company: Apple
    year: "2024"
    report_type: sustainability
```

### 5. Run ingest

```bash
python -m esg_rag.ingest --manifest ingest_manifest.yaml
```

### 6. Launch the UI

```bash
streamlit run app.py
```

Open `http://localhost:8501`

## Project structure

```
esg_assistant/
├── app.py                          # Streamlit main app
├── pipeline_config.yaml            # Feature flags (toggle BM25, reranker, etc.)
├── ingest_manifest.yaml            # List of PDFs to index
├── requirements.txt
├── check_project.py                # Health check script
│
├── esg_rag/
│   ├── schemas.py                  # Shared dataclasses (Chunk, SearchHit, etc.)
│   ├── albert.py                   # Albert API client (all LLM calls go here)
│   ├── parsing.py                  # PDF → elements (Docling + pdfplumber fallback)
│   ├── chunking.py                 # Elements → sized chunks
│   ├── chunk_quality.py            # Score chunks 0–1
│   ├── contextual.py               # Anthropic-style contextual prefixes
│   ├── store.py                    # Qdrant wrapper (one collection per doc)
│   ├── ingest.py                   # Full ingest pipeline
│   ├── bm25_search.py              # BM25 keyword search
│   ├── dense_search.py             # Semantic search
│   ├── fusion.py                   # RRF fusion with adaptive weights
│   ├── rerank.py                   # Albert cross-encoder reranking
│   ├── router.py                   # Query classifier (5 types)
│   ├── self_correct.py             # Auto-retry with relaxed filters
│   ├── retrieve.py                 # Single retrieval entry point
│   ├── synthesize.py               # answer_question() — routes simple/orchestrated
│   ├── verifier.py                 # Regex claim verification (<100ms)
│   ├── csrd_autofill.py            # CSRD ESRS E1 auto-fill pipeline
│   ├── mcp_server.py               # MCP server (stdio)
│   │
│   ├── agents/
│   │   ├── __init__.py             # run_agent() loop + ReAct fallback
│   │   ├── retriever_agent.py
│   │   ├── analyst_agent.py
│   │   ├── fact_checker_agent.py
│   │   ├── csrd_compliance_agent.py
│   │   └── lead_orchestrator.py
│   │
│   ├── tools/
│   │   ├── __init__.py             # Tool registry
│   │   ├── retrieve_tool.py
│   │   ├── list_documents.py
│   │   ├── read_table.py
│   │   ├── compute.py              # Safe arithmetic (asteval)
│   │   ├── compare_documents.py
│   │   ├── fetch_regulation.py
│   │   ├── web_search.py           # Tavily (needs API key)
│   │   └── spawn_subagent.py
│   │
│   └── eval/
│       ├── golden_set.csv          # 30 hand-written Q&A pairs
│       ├── harness.py              # evaluate() with RAGAS metrics
│       └── plot_ablation.py        # Ablation chart generator
│
├── components/
│   ├── chat.py                     # Chat interface
│   ├── doc_library.py              # Sidebar document browser
│   ├── tool_trace.py               # Tool call visualizer
│   ├── citations.py                # Citation badges
│   ├── compare_view.py             # Cross-document comparison table
│   ├── csrd_view.py                # CSRD auto-fill UI
│   └── cost_panel.py               # Albert token usage tracker
│
├── data/
│   ├── pdfs/                       # Source PDF reports
│   ├── parsed_cache/               # Cached parse results (skip re-parsing)
│   ├── figures/                    # Extracted figure images
│   ├── .qdrant/                    # Qdrant embedded index
│   ├── albert_costs.jsonl          # Per-call token log
│   └── csrd_templates/
│       └── esrs_e1_minimal.json    # ESRS E1 template (12 datapoints)
│
└── docs/
    ├── albert_capabilities.md      # Albert API probe results
    ├── health_check.md             # Latest health check report
    └── ablation.png                # Pipeline ablation chart
```

## Running the eval harness

```bash
# Baseline (dense only)
python -m esg_rag.eval.harness --label v01_dense_only

# After enabling BM25 in pipeline_config.yaml
python -m esg_rag.eval.harness --label v02_hybrid

# After enabling reranker
python -m esg_rag.eval.harness --label v03_rerank

# Plot ablation chart
python -m esg_rag.eval.plot_ablation
```

**Rule:** only keep a change if its scoreboard row beats the previous one.

## Eval results

| Config | Faithfulness | Answer Relevancy | Context Precision | Context Recall |
|--------|-------------|-----------------|-------------------|----------------|
| v01_dense_only | 0.867 | 0.720 | 0.867 | 0.627 |
| v02_hybrid | 0.833 | 0.697 | 0.833 | 0.623 |
| v03_rerank | **0.867** | **0.726** | **0.867** | 0.613 |

**Kept:** dense + reranker (`v03_rerank`). BM25 reverted — no improvement on this corpus.

## CSRD auto-fill

```bash
# List indexed documents
python -c "from esg_rag.store import get_store; [print(d) for d in get_store().list_docs()]"

# Auto-fill ESRS E1 for a specific document
python -m esg_rag.csrd_autofill --doc-id <doc_id> --out output.json
```

## Pipeline configuration

Edit `pipeline_config.yaml` to toggle features:

```yaml
retrieval:
  use_dense: true       # always on
  use_bm25: false       # hybrid search
  use_reranker: true    # Albert cross-encoder
  use_router: false     # query classifier

agent:
  mode: simple          # "simple" | "orchestrated"
```

## MCP server

```bash
python -m esg_rag.mcp_server
```

Exposes: `mcp_fetch_regulation`, `mcp_web_search`, `mcp_get_carbon_price`

## Health check

```bash
python check_project.py
```

Runs 23 checks across file structure, Albert API, Qdrant index, retrieval pipeline, tools, synthesis, eval harness, and Streamlit components.

## Constraints

- Albert API only (no OpenAI) — all embeddings, chat, and reranking go through Albert
- Qdrant embedded — no Docker, no server, everything local
- GPU features (VLM figures, reranker fine-tuning) are batch-only, never at query time
- Every pipeline change requires a RAGAS scoreboard row before merging
