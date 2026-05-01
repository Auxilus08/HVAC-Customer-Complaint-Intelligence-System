"""Programmatically build notebooks/01_pipeline_validation.ipynb.

Run from the hvac-ml repo root:
    python notebooks/_build_notebook.py
"""

from __future__ import annotations

import nbformat as nbf
from pathlib import Path


def md(src: str) -> nbf.notebooknode.NotebookNode:
    return nbf.v4.new_markdown_cell(src)


def code(src: str) -> nbf.notebooknode.NotebookNode:
    return nbf.v4.new_code_cell(src)


def main() -> None:
    nb = nbf.v4.new_notebook()
    cells: list[nbf.notebooknode.NotebookNode] = []

    cells.append(md(
        "# HVAC Complaint Intelligence — Sprint 1 End-to-End Validation\n\n"
        "Runs the complete pipeline on 500 synthetic complaints:\n"
        "1. Generate data\n2. Embed\n3. Cluster\n4. Visualise\n5. Sentiment\n"
        "6. Cluster labelling (Claude API)\n7. Trend detection\n8. Summary\n\n"
        "All pipeline classes come from `hvac-ml/pipeline/*` — the single source "
        "of truth for the backend workers."
    ))

    # Cell 1 — setup
    cells.append(code(
        "import os\n"
        "import random\n"
        "import sys\n"
        "from pathlib import Path\n"
        "\n"
        "import numpy as np\n"
        "import pandas as pd\n"
        "\n"
        "REPO = Path.cwd()\n"
        "if REPO.name == 'notebooks':\n"
        "    REPO = REPO.parent\n"
        "sys.path.insert(0, str(REPO))\n"
        "\n"
        "from data.generators.synthetic_complaints import generate_complaints\n"
        "from pipeline.embedder import Embedder\n"
        "from pipeline.clusterer import Clusterer\n"
        "from pipeline.sentiment import SentimentAnalyzer\n"
        "from pipeline.labeler import ClusterLabeler\n"
        "from pipeline.trend_detector import TrendDetector\n"
        "\n"
        "SEED = 42\n"
        "random.seed(SEED)\n"
        "np.random.seed(SEED)\n"
        "print(f'Working dir: {REPO}')"
    ))

    # Cell 2 — generate data
    cells.append(md("## 2. Generate 500 synthetic complaints"))
    cells.append(code(
        "df = generate_complaints(n=500, seed=SEED)\n"
        "print(f'Generated {len(df)} complaints')\n"
        "print()\n"
        "print('Distribution per category:')\n"
        "print(df['category'].value_counts().sort_index().to_string())\n"
        "print()\n"
        "print('Sample complaints:')\n"
        "for i, row in df.sample(5, random_state=SEED).iterrows():\n"
        "    print(f\"  [{row['category']:<22}] {row['complaint_text'][:90]}\")"
    ))

    # Cell 3 — embed
    cells.append(md(
        "## 3. Embed all complaints\n\n"
        "Wraps `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` "
        "with a SHA-256 hash cache."
    ))
    cells.append(code(
        "# When PyTorch wheels aren't available (e.g. Python 3.14), fall back\n"
        "# to a deterministic token-bag stub encoder. The stub preserves the\n"
        "# Embedder contract — the model itself is what changes.\n"
        "try:\n"
        "    from sentence_transformers import SentenceTransformer  # noqa: F401\n"
        "    print('Using real sentence-transformers model')\n"
        "except Exception:\n"
        "    print('sentence-transformers unavailable — using deterministic stub encoder')\n"
        "    import hashlib\n"
        "    from unittest.mock import MagicMock\n"
        "    import pipeline.embedder as _embedder_mod\n"
        "    \n"
        "    def _stub_encode(texts, **kwargs):\n"
        "        out = np.zeros((len(texts), 384), dtype=np.float32)\n"
        "        for i, text in enumerate(texts):\n"
        "            tok = np.zeros(384, dtype=np.float32)\n"
        "            for token in text.lower().split():\n"
        "                d = hashlib.sha256(token.encode()).digest()\n"
        "                seed = int.from_bytes(d[:8], 'little', signed=False)\n"
        "                tok += np.random.default_rng(seed).standard_normal(384).astype(np.float32)\n"
        "            full = hashlib.sha256(text.lower().encode()).digest()\n"
        "            full_seed = int.from_bytes(full[:8], 'little', signed=False)\n"
        "            noise = np.random.default_rng(full_seed).standard_normal(384).astype(np.float32)\n"
        "            v = tok + 0.05 * noise\n"
        "            n = np.linalg.norm(v)\n"
        "            if n > 0:\n"
        "                v = v / n\n"
        "            out[i] = v\n"
        "        return out\n"
        "    \n"
        "    class _StubST:\n"
        "        def __init__(self, *a, **k):\n"
        "            pass\n"
        "        def encode(self, texts, **kwargs):\n"
        "            if isinstance(texts, str):\n"
        "                texts = [texts]\n"
        "            return _stub_encode(list(texts))\n"
        "    \n"
        "    _embedder_mod.SentenceTransformer = _StubST\n"
        "\n"
        "embedder = Embedder()\n"
        "texts = df['complaint_text'].tolist()\n"
        "embeddings = embedder.encode_batch(texts)\n"
        "print(f'Embedding shape: {embeddings.shape}')\n"
        "assert embeddings.shape == (500, 384)\n"
        "\n"
        "# Cache hit verification: re-encode the same list and confirm zero new model calls.\n"
        "stats_before = dict(embedder.cache_stats)\n"
        "embedder.encode_batch(texts[:50])\n"
        "stats_after = dict(embedder.cache_stats)\n"
        "print(f'Cache hits: {stats_after[\"hits\"] - stats_before[\"hits\"]} '\n"
        "      f'(expected 50 — pure cache hits, no recomputation)')\n"
        "\n"
        "# Semantic-similarity sanity check.\n"
        "from sklearn.metrics.pairwise import cosine_similarity\n"
        "cooling_idx = df[df.category == 'cooling_inefficiency'].index[:2]\n"
        "noise_idx = df[df.category == 'compressor_noise'].index[:1]\n"
        "if len(cooling_idx) >= 2:\n"
        "    sim = cosine_similarity(\n"
        "        embeddings[cooling_idx[0]:cooling_idx[0]+1],\n"
        "        embeddings[cooling_idx[1]:cooling_idx[1]+1],\n"
        "    )[0, 0]\n"
        "    print(f'Cooling vs Cooling cosine: {sim:.3f}  (should be > 0.6)')\n"
        "if len(cooling_idx) >= 1 and len(noise_idx) >= 1:\n"
        "    sim = cosine_similarity(\n"
        "        embeddings[cooling_idx[0]:cooling_idx[0]+1],\n"
        "        embeddings[noise_idx[0]:noise_idx[0]+1],\n"
        "    )[0, 0]\n"
        "    print(f'Cooling vs Noise   cosine: {sim:.3f}  (should be < 0.4)')"
    ))

    # Cell 4 — cluster
    cells.append(md(
        "## 4. Cluster the embeddings\n\n"
        "UMAP 384→50 (clustering) and 384→2 (visualisation), then HDBSCAN."
    ))
    cells.append(code(
        "clusterer = Clusterer(\n"
        "    umap_n_components_cluster=50,\n"
        "    umap_n_components_viz=2,\n"
        "    hdbscan_min_cluster_size=15,\n"
        "    random_state=SEED,\n"
        ")\n"
        "result = clusterer.fit(embeddings)\n"
        "print(f'Found {result.n_clusters} clusters')\n"
        "print(f'Noise:      {result.noise_count} points ({result.noise_pct:.1f}%)')\n"
        "print(f'Silhouette: {result.silhouette_score:.3f}')\n"
        "print()\n"
        "print('Cluster sizes:')\n"
        "for cid, size in sorted(result.cluster_sizes.items()):\n"
        "    print(f'  cluster {cid}: {size} members')\n"
        "\n"
        "df['cluster_id'] = result.labels"
    ))

    # Cell 5 — visualise
    cells.append(md("## 5. Visualise (Plotly UMAP scatter)"))
    cells.append(code(
        "import plotly.express as px\n"
        "\n"
        "viz_df = pd.DataFrame({\n"
        "    'x': result.coords_2d[:, 0],\n"
        "    'y': result.coords_2d[:, 1],\n"
        "    'cluster': result.labels.astype(str),\n"
        "    'text': [t[:80] for t in df['complaint_text']],\n"
        "    'category': df['category'].values,\n"
        "    'region': df['region'].values,\n"
        "})\n"
        "fig = px.scatter(\n"
        "    viz_df, x='x', y='y', color='cluster',\n"
        "    hover_data=['text', 'category', 'region'],\n"
        "    title='HVAC Complaint Clusters — UMAP 2D Projection',\n"
        "    width=1000, height=700,\n"
        ")\n"
        "fig.update_traces(marker=dict(size=7, opacity=0.75))\n"
        "out_html = REPO / 'notebooks' / 'cluster_scatter.html'\n"
        "fig.write_html(str(out_html))\n"
        "print(f'Scatter saved to: {out_html}')\n"
        "fig.show()"
    ))

    # Cell 6 — sentiment
    cells.append(md("## 6. Sentiment scoring (VADER)"))
    cells.append(code(
        "analyzer = SentimentAnalyzer()\n"
        "sentiments = analyzer.score_batch(df['complaint_text'].tolist())\n"
        "df['sentiment_score'] = [s.compound for s in sentiments]\n"
        "df['sentiment_label'] = [s.label for s in sentiments]\n"
        "\n"
        "print('Sentiment label counts:')\n"
        "print(df['sentiment_label'].value_counts().to_string())\n"
        "print()\n"
        "print('Top 5 most-angry complaints:')\n"
        "for _, row in df.nsmallest(5, 'sentiment_score').iterrows():\n"
        "    print(f'  [{row.sentiment_label:<8}] '\n"
        "          f'{row.sentiment_score:+.2f} | {row.complaint_text[:90]}')\n"
        "\n"
        "critical_count = int((df.sentiment_label == 'CRITICAL').sum())\n"
        "print(f'\\nTotal CRITICAL complaints: {critical_count}')\n"
        "assert critical_count >= 2, 'Sprint exit criterion: at least 2 CRITICAL complaints'"
    ))

    # Cell 7 — label clusters
    cells.append(md(
        "## 7. Auto-label clusters via Claude API\n\n"
        "Uses `ClusterLabeler` with the default Jaccard threshold (0.2). "
        "On the first run all clusters are relabeled; the second call with "
        "identical fingerprints exercises the gate and skips every cluster."
    ))
    cells.append(code(
        "labeler = ClusterLabeler()\n"
        "\n"
        "cluster_complaints: dict[int, list[str]] = {}\n"
        "fingerprints: dict[int, set[int]] = {}\n"
        "for cid in sorted(result.cluster_sizes.keys()):\n"
        "    mask = result.labels == cid\n"
        "    cluster_complaints[cid] = df.loc[mask, 'complaint_text'].tolist()[:10]\n"
        "    fingerprints[cid] = set(np.where(mask)[0].tolist())\n"
        "\n"
        "if not os.environ.get('ANTHROPIC_API_KEY'):\n"
        "    print('ANTHROPIC_API_KEY not set — using deterministic stub labels')\n"
        "    cluster_labels = {cid: f'Cluster {cid} Pattern Label' for cid in cluster_complaints}\n"
        "else:\n"
        "    cluster_labels = labeler.label_all_clusters(cluster_complaints)\n"
        "\n"
        "for cid, lbl in cluster_labels.items():\n"
        "    size = result.cluster_sizes[cid]\n"
        "    avg_sent = float(df.loc[result.labels == cid, 'sentiment_score'].mean())\n"
        "    print(f'Cluster {cid} (n={size:3d}): {lbl}  | avg sentiment: {avg_sent:+.2f}')\n"
        "\n"
        "# Jaccard gate verification: identical fingerprints → all clusters skipped.\n"
        "if os.environ.get('ANTHROPIC_API_KEY'):\n"
        "    second = labeler.label_all_clusters(\n"
        "        cluster_complaints,\n"
        "        old_fingerprints=fingerprints,\n"
        "        new_fingerprints=fingerprints,\n"
        "        previous_labels=cluster_labels,\n"
        "    )\n"
        "    assert second == cluster_labels, 'Jaccard gate must skip relabeling unchanged clusters'\n"
        "    print('\\nJaccard gate verified: re-running with identical fingerprints reused all labels.')"
    ))

    # Cell 8 — trend detection
    cells.append(md("## 8. Week-over-week trend detection"))
    cells.append(code(
        "detector = TrendDetector()\n"
        "trends = detector.compute_trends(df[df.cluster_id != -1])\n"
        "trends_sorted = sorted(trends, key=lambda t: t.growth_pct, reverse=True)\n"
        "\n"
        "for t in trends_sorted:\n"
        "    flag = ' [EMERGING]' if t.is_emerging else ''\n"
        "    print(f'Cluster {t.cluster_id:>2}: '\n"
        "          f'curr={t.current_week_count:>3} prev={t.previous_week_count:>3} | '\n"
        "          f'{t.growth_pct:+6.0f}% WoW | '\n"
        "          f'Rs.{t.window_cost_exposure:>10,.0f}{flag}')\n"
        "\n"
        "# Sprint exit criterion: Delhi compressor_noise should fire as emerging.\n"
        "delhi_comp_clusters = df[\n"
        "    (df.category == 'compressor_noise') & (df.region == 'Delhi') & (df.cluster_id != -1)\n"
        "].cluster_id.value_counts()\n"
        "if not delhi_comp_clusters.empty:\n"
        "    primary = int(delhi_comp_clusters.idxmax())\n"
        "    primary_trend = next((t for t in trends if t.cluster_id == primary), None)\n"
        "    if primary_trend is not None:\n"
        "        print(f'\\nDelhi compressor_noise primary cluster: {primary}')\n"
        "        print(f'  WoW growth: {primary_trend.growth_pct:+.0f}%')\n"
        "        print(f'  Emerging:   {primary_trend.is_emerging}')"
    ))

    # Cell 9 — summary
    cells.append(md("## 9. Sprint 1 summary table"))
    cells.append(code(
        "header = '| Cluster | Label                          | Count | Sent.  | Growth  | Exposure  |'\n"
        "sep    = '|---------|--------------------------------|-------|--------|---------|-----------|'\n"
        "lines = [header, sep]\n"
        "for t in trends_sorted:\n"
        "    cid = t.cluster_id\n"
        "    lbl = cluster_labels.get(cid, f'Cluster {cid}')[:30]\n"
        "    avg_sent = float(df.loc[result.labels == cid, 'sentiment_score'].mean())\n"
        "    flag = ' EMERGING' if t.is_emerging else ''\n"
        "    lines.append(\n"
        "        f'| {cid:>7} | {lbl:<30} | {result.cluster_sizes[cid]:>5} | '\n"
        "        f'{avg_sent:+.2f} | {t.growth_pct:+6.0f}% | Rs.{t.window_cost_exposure:>7,.0f}{flag} |'\n"
        "    )\n"
        "for line in lines:\n"
        "    print(line)\n"
        "\n"
        "# ── Sprint 1 exit criteria assertions ─────────────────────────────────────\n"
        "assert result.n_clusters >= 5, f'Expected 5+ clusters, got {result.n_clusters}'\n"
        "assert result.silhouette_score > 0.2, f'Silhouette {result.silhouette_score:.3f} < 0.2'\n"
        "assert int((df.sentiment_label == 'CRITICAL').sum()) >= 2, 'Need 2+ CRITICAL complaints'\n"
        "assert any(t.is_emerging and t.growth_pct >= 100.0 for t in trends), (\n"
        "    'Need at least one emerging cluster with 100%+ WoW growth'\n"
        ")\n"
        "print('\\nAll Sprint 1 exit criteria met.')"
    ))

    nb["cells"] = cells
    nb["metadata"]["kernelspec"] = {
        "display_name": "Python 3 (hvac-ml)",
        "language": "python",
        "name": "python3",
    }
    nb["metadata"]["language_info"] = {"name": "python", "version": "3.11"}

    out = Path(__file__).resolve().parent / "01_pipeline_validation.ipynb"
    with out.open("w", encoding="utf-8") as fh:
        nbf.write(nb, fh)
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
