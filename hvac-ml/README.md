# hvac-ml

NLP pipeline, model code, and notebooks for the HVAC Complaint Intelligence System.

## Purpose

Standalone ML library that provides:
- `Embedder` — SentenceTransformer wrapper with text-hash cache
- `Clusterer` — UMAP (50D + 2D) + HDBSCAN pipeline
- `SentimentAnalyzer` — VADER wrapper with severity labels
- `ClusterLabeler` — Claude API labeling with Jaccard-distance gate
- `TrendDetector` — Pandas WoW growth and cost exposure calculation
- Synthetic data generator — 500 HVAC complaints across 8 types via Claude API

## Quick Start

```bash
cp .env.example .env
# Fill in ANTHROPIC_API_KEY

pip install -e ".[dev]"
pytest
```

## Generate Synthetic Data

```bash
python -m data.generators.synthetic_complaints
# Writes to data/synthetic_complaints.csv
```

## Run Pipeline Validation Notebook

```bash
jupyter lab notebooks/01_pipeline_validation.ipynb
```

## Environment Variables

| Variable | Description | Default |
|---|---|---|
| `ANTHROPIC_API_KEY` | Anthropic API key | _(required for labeling + data gen)_ |
| `CLAUDE_MODEL` | Claude model ID | `claude-sonnet-4-20250514` |
| `EMBEDDING_MODEL` | SentenceTransformer model | `paraphrase-multilingual-MiniLM-L12-v2` |
| `UMAP_RANDOM_STATE` | Random state for all UMAP fits | `42` |
| `HDBSCAN_MIN_CLUSTER_SIZE` | Min cluster size | `15` |
| `JACCARD_RELABEL_THRESHOLD` | Min Jaccard distance to trigger relabeling | `0.2` |

## Architecture Notes

- **Two UMAP fits**: 50D for HDBSCAN, 2D for visualisation — never mixed
- **random_state=42** on all UMAP fits for reproducibility
- **PII stripping** applied before any Claude API call in `labeler.py`
- **Jaccard gate** in `labeler.py` reduces LLM calls to 1–3 per nightly run
