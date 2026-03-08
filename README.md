# RAG System — FLOWCAL Documentation Intelligence

A production-ready **Retrieval-Augmented Generation (RAG)** system built on top of FLOWCAL documentation. It loads, embeds, and queries multi-modal documents (text, tables, images) using Azure OpenAI and Qdrant vector database.

---

## Architecture

```
data/ (source docs)
    └── Multi-format loader (HTML, PDF, DOCX, XLSX, images)
            └── Context Preserver (links text/table/image elements)
                    └── Embeddings (Azure OpenAI text-embedding-3-large, 3072 dims)
                            └── Qdrant Vector DB (124,776+ vectors)
                                    └── RAG Chain (Azure OpenAI gpt-4.1)
                                            └── Answers with citations
```

---

## Features

- **Multi-modal document loading** — HTML, PDF, DOCX, XLSX, images (PNG/JPG/GIF)
- **AI image descriptions** — GPT-4.1 vision describes all standalone images for semantic search
- **Context preservation** — Text, tables, and images are linked together by document hierarchy
- **High-performance embeddings** — `text-embedding-3-large` (3072 dimensions) with parallel processing (10 threads)
- **Qdrant vector storage** — Persistent local vector DB with filtered search support
- **Full RAG pipeline** — Retrieves top-K results + related elements, generates grounded answers
- **Source citations** — Every answer includes relevance scores and source file references

---

## Project Structure

```
RAG/
├── src/
│   ├── config.py               # Configuration (Azure OpenAI, Qdrant)
│   ├── multi_file_loader.py    # Loads HTML, PDF, DOCX, XLSX, images
│   ├── context_preserver.py    # Links related document elements
│   ├── summarizer.py           # AI summarization + image description
│   ├── vector_store.py         # Qdrant wrapper (embed, upsert, search)
│   └── rag_chain.py            # End-to-end RAG query pipeline
├── notebooks/
│   ├── 00_setup_test.ipynb     # Environment & connectivity test
│   ├── 01_file_loading.ipynb   # Document loading exploration
│   ├── 02_context_linking.ipynb
│   ├── 03_summarization.ipynb
│   ├── 04_qdrant_storage.ipynb # Full embed + upsert pipeline
│   ├── 05_rag_system.ipynb     # RAG query demonstrations
│   └── 07_optimization.ipynb
├── data/                       # Source documents (not committed)
├── requirements.txt
└── .env                        # API keys (not committed)
```

---

## Prerequisites

- Python 3.10+
- Docker Desktop (for Qdrant)
- Azure OpenAI access with:
  - Chat deployment (e.g. `gpt-4.1`)
  - Embedding deployment (e.g. `text-embedding-3-large`)

---

## Setup

### 1. Clone & create virtual environment

```powershell
git clone <repo-url>
cd RAG
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Configure environment variables

Create a `.env` file in the project root:

```env
# Azure OpenAI
AZURE_OPENAI_ENDPOINT=https://<your-resource>.openai.azure.com/
AZURE_OPENAI_API_KEY=<your-key>
AZURE_OPENAI_API_VERSION=2025-01-01-preview
AZURE_OPENAI_CHAT_DEPLOYMENT=gpt-4.1
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-3-large

# Qdrant
QDRANT_URL=http://localhost:6333
```

### 3. Start Qdrant

```powershell
docker run -d --name qdrant -p 6333:6333 -v qdrant_storage:/qdrant/storage qdrant/qdrant
```

Qdrant dashboard: **http://localhost:6333/dashboard**

### 4. Add source documents

Place your documents in the `data/` folder. Supported formats:
- **HTML** (`.htm`, `.html`)
- **PDF** (`.pdf`)
- **Word** (`.docx`)
- **Excel** (`.xlsx`, `.xls`)
- **Images** (`.png`, `.jpg`, `.jpeg`, `.gif`)

---

## Usage

### Run the full pipeline (notebooks in order)

| Notebook | Purpose |
|---|---|
| `00_setup_test.ipynb` | Verify environment & API connectivity |
| `04_qdrant_storage.ipynb` | Load docs → describe images → embed → upsert to Qdrant |
| `05_rag_system.ipynb` | Query the RAG system with natural language |

### Programmatic usage

```python
from src.vector_store import VectorStore
from src.rag_chain import RAGChain
from src.config import Config

config = Config()

vector_store = VectorStore(
    qdrant_url=config.qdrant_url,
    collection_name=config.qdrant_collection,
    openai_api_key=Config.AZURE_OPENAI_API_KEY,
    azure_endpoint=Config.AZURE_OPENAI_ENDPOINT,
    api_version=Config.AZURE_OPENAI_API_VERSION,
    embedding_deployment=Config.AZURE_OPENAI_EMBEDDING_DEPLOYMENT
)

rag_chain = RAGChain(
    vector_store=vector_store,
    openai_api_key=Config.AZURE_OPENAI_API_KEY,
    azure_endpoint=Config.AZURE_OPENAI_ENDPOINT,
    api_version=Config.AZURE_OPENAI_API_VERSION,
    azure_deployment=Config.AZURE_OPENAI_CHAT_DEPLOYMENT
)

result = rag_chain.query("What is the main purpose of these documents?", top_k=5)
print(result['answer'])
print(f"Confidence: {result['confidence']:.1%}")
```

---

## Data Persistence

Qdrant data is stored in a Docker named volume (`qdrant_storage`) and **persists across container restarts and reboots**. You do not need to re-embed documents after restarting your machine — just start the Qdrant container again.

---

## Tech Stack

| Component | Technology |
|---|---|
| Embeddings | Azure OpenAI `text-embedding-3-large` (3072 dims) |
| Chat / Vision | Azure OpenAI `gpt-4.1` |
| Vector DB | Qdrant (local Docker) |
| Document Parsing | `unstructured`, `python-docx`, `beautifulsoup4`, `pypdf` |
| Parallel Processing | `concurrent.futures.ThreadPoolExecutor` (10 workers) |
| Notebooks | JupyterLab |
