# Qual

Finance Analysis system for global and national market trends and report.

## Target Audience
Analysts who need repeatable workflows for ingesting market data and producing global/macroeconomic analysis.

## Key Features
- **Global analysis with a multi-agent system** to synthesize insights across sources.
- **Market data ingestion** from live and RSS sources.
- **Quality gates and audits** for data readiness.
- **RAG evaluation and indexing** to support retrieval-augmented workflows.

## Quick Start

```bash
./run.sh
```

The script installs dependencies and starts the API server.

## Setup

1. Create a virtual environment (recommended).
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Copy environment template and set your keys:
   ```bash
   cp .env.example .env
   ```
4. Start the server:
   ```bash
   ./run.sh
   ```

## Configuration
Environment variables are defined in `.env.example`. Required keys include:
- `FRED_API_KEY`
- `ALPHA_VANTAGE_API_KEY`
- `OLLAMA_URL`

## Project Structure (high level)
- `api/` – API server and routes
- `ingestion/` – data ingestion pipelines
- `intelligence/` – analysis and multi-agent logic
- `rag/` – retrieval and evaluation workflows
- `data/` – datasets and artifacts
- `tests/` – test suite

## Common Tasks
- Run RSS ingestion: `python run_rss_ingest.py`
- Refresh data & index: `python refresh_data_and_index.py`
- Run RAG evaluation: `python run_rag_eval.py`

## License
Add your license here (e.g., MIT).