# AI Product Enrichment Pipeline
> **Portfolio context:** Extracted from founder-led production systems — multi-marketplace inventory, orders, and warehouse execution. **[Full portfolio](https://github.com/AspiranteD/AspiranteD)** · [aspiranted.github.io](https://aspiranted.github.io)

Production-grade pipeline that transforms raw product data into marketplace-optimized listings using AI. Built to process thousands of items daily across multiple marketplace accounts.

## What It Does

Takes a product with basic Amazon data (title, features, department) and produces a complete Wallapop-ready listing:

```
INPUT:  "Sony WH-1000XM5 Wireless Noise Cancelling Headphones"
        Department: Electronics, Category: Headphones

OUTPUT: Title:       "Sony WH-1000XM5 auriculares bluetooth"
        Description: "Auriculares inalámbricos Sony con cancelación de ruido..."
        Category:    "Tecnología y electrónica > Audio > Auriculares"
        Keywords:    "auriculares,bluetooth,inalámbrico,música,sonido"
        Hashtags:    "#sony,#auriculares,#bluetooth,#musica,#telovendo"
        Brand:       "Sony"
        Model:       "WH-1000XM5"
```

## Architecture

```
+------------------------------------------------------+
¦                 EnrichmentPipeline                   ¦
¦                                                      ¦
¦  +---------+  +--------------+  +-----------------+ ¦
¦  ¦ Stage 1 ¦? ¦   Stage 2    ¦? ¦    Stage 3      ¦ ¦
¦  ¦ Scrape  ¦  ¦ Categorize   ¦  ¦ Generate Content¦ ¦
¦  ¦         ¦  ¦              ¦  ¦                 ¦ ¦
¦  ¦ External¦  ¦ 1.JSON map   ¦  ¦ OpenAI API      ¦ ¦
¦  ¦ data    ¦  ¦ 2.AI (OpenAI)¦  ¦ - Title (50ch)  ¦ ¦
¦  ¦ fetch   ¦  ¦ 3.Fallback   ¦  ¦ - Description   ¦ ¦
¦  ¦         ¦  ¦              ¦  ¦ - Keywords      ¦ ¦
¦  ¦ Retry   ¦  ¦ 600+ mapping ¦  ¦ - Brand/Model   ¦ ¦
¦  ¦ tracking¦  ¦ rules        ¦  ¦ - Hashtags      ¦ ¦
¦  +---------+  +--------------+  +-----------------+ ¦
¦                                          ¦           ¦
¦  +-----------------+  +-----------------+¦           ¦
¦  ¦    Stage 4      ¦  ¦ Policy Sanitizer ¦¦           ¦
¦  ¦ Update Listings ¦  ¦                 ¦¦           ¦
¦  ¦                 ¦  ¦ 30+ regex rules ¦¦           ¦
¦  ¦ Only empty      ¦  ¦ TV/TDT, spy cam ¦¦           ¦
¦  ¦ fields (idem-   ¦  ¦ exam earpiece   ¦¦           ¦
¦  ¦ potent writes)  ¦  ¦ GPS trackers    ¦¦           ¦
¦  +-----------------+  +-----------------+¦           ¦
+------------------------------------------------------+
```

## Key Design Decisions

### Three-Tier Categorization
Not every item needs an AI call. The system checks a 600+ rule JSON mapping first (Amazon department/category ? Wallapop category, covers ~80% of items at zero cost), falls back to AI classification, and guarantees a category via department-level fallback. This reduced our OpenAI spend by ~80%.

### Title Deduplication
When multiple items share the same ASIN (e.g., same product in different conditions), the pipeline queries existing titles and instructs the AI to differentiate — by including model numbers, capacities, voltages, or other unique attributes. This prevents duplicate listings that confuse buyers.

### Idempotent Writes
Every stage only writes to empty fields and never overwrites existing data. This makes the pipeline safe to re-run on partially enriched items, and ensures manual edits are preserved.

### Policy Compliance Sanitizer
Marketplaces auto-reject listings with certain terms. The sanitizer uses 30+ regex rules (ordered by phrase length to avoid partial matches) to replace flagged terms:
- "receptor satélite" ? "sintonizador TDT" (not just "satélite" ? "TDT")
- "pinganillo invisible para examen" ? "auricular bluetooth mini"
- "cámara espía" ? "cámara mini"
- "desbloqueado" ? "libre"

### Pluggable Architecture
The pipeline accepts functions for data access (scraping, title lookup, listing update) so the core logic is database-agnostic. This makes it testable without a database and reusable across different storage backends.

## Project Structure

```
+-- src/
¦   +-- enrichment/
¦   ¦   +-- pipeline.py              # 4-stage orchestrator (250+ lines)
¦   ¦   +-- category_mapper.py       # 3-tier classification (170+ lines)
¦   ¦   +-- description_generator.py # AI content generation (140+ lines)
¦   ¦   +-- policy_sanitizer.py      # Regex compliance engine (90+ lines)
¦   ¦   +-- listing_builder.py       # Field mapping + idempotent writes
¦   ¦   +-- openai_client.py         # JSON/text API wrapper
¦   +-- cli/
¦       +-- generate_descriptions.py # Batch description CLI
¦       +-- categorize_items.py      # Batch categorization CLI
+-- data/
¦   +-- category_mapping.json        # 600+ Amazon?Wallapop mapping rules
¦   +-- category_taxonomy.json       # Full Wallapop category tree
+-- tests/
¦   +-- test_pipeline.py             # 20+ pipeline stage tests
¦   +-- test_category_mapper.py      # 3-tier hierarchy tests
¦   +-- test_description_generator.py# AI generation + truncation tests
¦   +-- test_policy_sanitizer.py     # 30+ sanitization rule tests
¦   +-- test_listing_builder.py      # Field mapping + idempotency tests
+-- examples/
    +-- enrich_single_item.py        # Full pipeline demo
    +-- batch_categorize.py          # Batch categorization with stats
```

## Usage

### Quick Start

```bash
pip install -r requirements.txt
cp .env.example .env  # Add your OpenAI API key
```

### Run Tests

```bash
python -m pytest tests/ -v
```

### Single Item Enrichment

```python
from src.enrichment.pipeline import EnrichmentPipeline, PipelineConfig

config = PipelineConfig(
    scrape_fn=your_scraper,
    get_existing_titles_fn=your_title_lookup,
    update_listing_fn=your_listing_updater,
)

pipeline = EnrichmentPipeline(config)
result = pipeline.enrich(item, item_id="LPN-001")
# result.scraping ? "ok" | "skipped" | "failed" | "max_attempts"
# result.categorization ? "ok" | "skipped" | "no_data" | "failed"
# result.description ? "ok" | "skipped" | "no_data" | "failed"
```

### Batch Processing

```python
from src.cli.generate_descriptions import run_batch, BatchConfig

stats = run_batch(
    items=pending_items,
    config=BatchConfig(delay=1.5, commit_batch_size=10),
    get_existing_titles_fn=title_lookup,
    commit_fn=lambda n: session.commit(),
)
print(stats.summary())  # "45 OK / 2 FAIL / 3 SKIP / 50 total"
```

### Policy Check

```python
from src.enrichment.policy_sanitizer import sanitize_text, has_risk_word

if has_risk_word(title, description):
    title = sanitize_text(title, for_title=True)  # Truncates to 50 chars
    description = sanitize_text(description)
```

## Tech Stack

- **Python 3.11+**
- **OpenAI API** (gpt-4o-mini) — JSON structured output for content generation, text mode for classification
- **Regex engine** — 30+ compiled patterns for policy compliance
- **pytest** — 110+ unit tests with mocked API calls
