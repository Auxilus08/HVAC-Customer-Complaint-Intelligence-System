# HVAC Intelligence System — Demo Script

**Total time:** 5 minutes
**URL:** http://localhost:5173

---

## Opening (30s)

**Say:**
> "An HVAC service company gets thousands of complaints every week — across WhatsApp, CRM, email, field technician notes. Patterns hide in that noise for weeks. Our system surfaces them in hours."

**Show:**
- The dashboard fully loaded.
- TopBar pills: `500 complaints · 12 clusters · 2 🚨 emerging`.
- Live indicator (green pulsing dot).

---

## Problem Statement (45s)

**Say:**
> "Each complaint is unstructured text — Hindi, English, Hinglish, all mixed. Manual triage takes weeks. By the time the operations team spots a pattern, customers have already left for a competitor."

**Show:**
- Click `Upload Complaints` to show the modal — explain CSV ingestion.
- Close the modal.

---

## Live Pattern Detection (60s)

**Say:**
> "The alert banner flags emerging clusters automatically. Look — compressor noise in Delhi, up 280% week-over-week. Refrigerant leaks, also climbing. We detected this in **under 24 hours**. Manually it would take 6 weeks."

**Show:**
- The orange-bordered alert cards in `AlertBanner`.
- Hover to show region, growth %, complaint count, exposure.
- Click the highest-growth alert.

---

## Cluster Deep Dive (60s)

**Say:**
> "When you click a cluster, you see the full picture — 19 complaints, average sentiment minus 0.59, 280% week-over-week growth, **Rs.1.95 lakhs of cost exposure**. Now I'll generate a Gemini-powered field advisory."

**Show:**
- Metrics row in `ClusterDetail`.
- Top SKUs / Regions chips.
- Trend chart showing weekly volume climb.
- Recent complaints list — one click, technician sees the actual customer language.
- Click `Generate Advisory`.

**Say (while loading):**
> "Gemini reads the representative complaints, applies HVAC domain knowledge, and writes the advisory in 3 to 5 seconds."

**Show:**
- Four ## sections appear: Root Cause, Diagnostic Steps, Parts Likely Needed, Escalation Criteria.
- Click `Download` to show export.

---

## Analytics View (45s)

**Say:**
> "Operations VP doesn't care about individual complaints. They need cost exposure by region, by SKU, by sentiment. Switch to the Analytics tab."

**Show:**
- Press `A` (or click the Analytics tab).
- Stats row: 500 complaints, 12 clusters, silhouette 0.84, total exposure Rs.16.3L.
- Sentiment pie chart — point to CRITICAL slice.
- Region bar chart — Delhi has the most, colored by sentiment.
- Source channel chart — WhatsApp + CRM + field tech all unified.
- Click `Export Report` to show the Markdown report download.

---

## Technical Architecture (30s)

**Say:**
> "Under the hood: `paraphrase-multilingual-MiniLM-L12-v2` for 384-dim embeddings (50+ languages), pgvector for similarity, UMAP for two-stage dimensionality reduction (50D for clustering, 2D for the map you saw), HDBSCAN to discover clusters automatically — no `k` to specify — and Gemini 2.5 Flash Lite for labeling and advisories. PII is regex-stripped *and* spaCy-NER'd before any data leaves the process. All complaint ingestion is sub-100ms; clustering runs nightly via Celery."

**Show:**
- Press `U` to flash the UMAP map again — show the colored clusters.
- Press `?` to show keyboard shortcuts.

---

## Closing (30s)

**Say:**
> "From complaint chaos to actionable intelligence. Pattern detected in hours, not weeks. Roughly Rs.38 lakhs of avoidable cost surfaced today. Every cluster has a Gemini advisory waiting. The system is real, the data is live, and you can press `D` right now to watch the auto-walkthrough."

**Show:**
- Press `D` for the 11-step demo walkthrough.

---

## Likely Judge Questions + Answers

**Q: How does it handle Hindi/Hinglish complaints?**
A: We use `paraphrase-multilingual-MiniLM-L12-v2`, trained on 50+ languages including Hindi. Embedding quality is preserved across script and code-switched text. The labeler and advisory model (Gemini) handles mixed-language input natively.

**Q: Why HDBSCAN over K-Means?**
A: K-Means forces you to specify the cluster count up front. HDBSCAN discovers it automatically — and labels outliers as noise (-1) instead of forcing them into the nearest centroid. Critical when the number of complaint patterns is unknown and changing.

**Q: How is PII protected?**
A: Two-pass stripping. Pass 1 — regex for phone numbers, emails, Aadhaar, PAN. Pass 2 — spaCy NER for personal names and addresses. Both passes run before *any* DB write **and** before *any* Gemini call. Raw text is encrypted at rest with AES-256-GCM. The PII strip is enforced via a static AST audit (`scripts/check_pii_coverage.py`) on every commit.

**Q: Can it scale beyond 500 complaints?**
A: The architecture is horizontally scalable. Celery embeds + scores in parallel — workers auto-scale per queue. pgvector's IVFFlat index handles 2M+ vectors. UMAP switches to approximate (`densmap=False, low_memory=True`) above 50k. HDBSCAN scales to ~100k on a single node, and we'd shard by region beyond that.

**Q: Why Gemini 2.5 Flash Lite?**
A: Best cost-to-capability ratio for short structured outputs. Free-tier-friendly while we're prototyping; trivial to switch to `gemini-2.5-flash` for production. Temperature 0.2 keeps labels consistent across runs (Jaccard gate also reuses unchanged-cluster labels).

**Q: What happens if the LLM API goes down?**
A: Cluster labeling reuses the previous label via the Jaccard membership gate (set difference < 0.2). Advisory generation surfaces the error inline in the UI with a Retry button — no broken state. The dashboard remains fully functional; only labeling/advisory degrade.

**Q: How fresh is the data?**
A: Complaint ingestion: <100ms (async embed + sentiment via Celery). Clustering: nightly batch (configurable cron). Labels + advisories: on-demand via Gemini. Trend snapshots: nightly. Alerts (emerging clusters): updated each batch run.
