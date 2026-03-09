# Implementation Guide: Apply V2 Fixes & Re-Ingest All Data

This guide walks you through applying the updated extraction pipeline, seed data, and models patch, then wiping existing data and re-ingesting all documents from scratch.

**Estimated time:** 15–30 minutes (depending on number of documents)

---

## Prerequisites

Before starting, make sure:

- Docker Desktop is running (whale icon in system tray)
- Ollama is running (`ollama serve` in a separate terminal)
- You are in your project root directory (`cd $HOME\Documents\product-expert` on Windows)
- You have the 4 output files downloaded from Claude:
  - `003_extraction_pipeline.py`
  - `seed_additions.sql`
  - `models_patch.py`
  - `pdf_analysis_context_v2.py` (reference only — not deployed)

---

## Phase 1: Back Up Existing Data (Safety Net)

### Windows (PowerShell)

```powershell
# Back up the current database
.\ops.ps1 db-dump

# Back up your current source files
Copy-Item app\003_extraction_pipeline.py app\003_extraction_pipeline.py.bak
Copy-Item app\002_models.py app\002_models.py.bak
```

### Mac/Linux

```bash
make db-dump

cp app/003_extraction_pipeline.py app/003_extraction_pipeline.py.bak
cp app/002_models.py app/002_models.py.bak
```

> **Note:** If your file paths differ (e.g. `src/` instead of `app/`), adjust accordingly. The key files are `003_extraction_pipeline.py` and `002_models.py` wherever they live in your project.

---

## Phase 2: Replace the Source Files

### Step 2.1 — Replace the extraction pipeline

Copy the new `003_extraction_pipeline.py` over the existing one:

```powershell
# Windows
Copy-Item path\to\downloads\003_extraction_pipeline.py app\003_extraction_pipeline.py -Force
```

```bash
# Mac/Linux
cp ~/Downloads/003_extraction_pipeline.py app/003_extraction_pipeline.py
```

### Step 2.2 — Patch the models file (parse_certifications fix)

Open `app/002_models.py` in your editor. Find the `parse_certifications` function (search for `def parse_certifications`). Replace the entire function body with the version from `models_patch.py`.

The key changes are adding these new certification patterns at the top of the pattern list:

```python
(r'UL[/-]C[/-]UL', 'UL_C_UL'),         # ARES format
(r'C-?UL\b', 'C_UL'),                    # C-UL standalone
```

And adding at the end:

```python
(r'INTERTEK', 'Intertek'),               # CME docs
(r'NFPA\s*99', 'NFPA_99'),
(r'CLASS\s*1.*?DIVISION\s*II', 'Class1_DivII'),
```

### Step 2.3 — Place the seed additions SQL file

Copy `seed_additions.sql` into your database init directory so it's available to the container:

```powershell
# Windows
Copy-Item path\to\downloads\seed_additions.sql db\seed_additions.sql
```

```bash
# Mac/Linux
cp ~/Downloads/seed_additions.sql db/seed_additions.sql
```

### Step 2.4 — Place the analysis reference (optional)

This file is for your reference only — it doesn't get deployed:

```powershell
Copy-Item path\to\downloads\pdf_analysis_context_v2.py docs\pdf_analysis_context_v2.py
```

---

## Phase 3: Stop All Services

```powershell
# Windows
.\ops.ps1 down
```

```bash
# Mac/Linux
make down
```

Wait for all containers to stop. Verify with:

```powershell
docker compose ps    # Should show no running containers
```

---

## Phase 4: Rebuild the Docker Image

Since you changed Python source files, you need to rebuild the API container:

```powershell
# Windows
docker compose build api
```

```bash
# Mac/Linux
docker compose build api
```

This picks up the new `003_extraction_pipeline.py` and `002_models.py`.

---

## Phase 5: Reset the Database (DESTRUCTIVE)

This drops and recreates the database, then re-runs the schema and seed scripts.

### Windows

```powershell
# Start just the database container
docker compose up -d postgres
Start-Sleep -Seconds 10    # Wait for PostgreSQL to be ready

# Drop and recreate the database
docker compose exec postgres psql -U expert -c "DROP DATABASE IF EXISTS product_expert;"
docker compose exec postgres psql -U expert -c "CREATE DATABASE product_expert;"

# Run the schema creation
docker compose exec postgres psql -U expert -d product_expert -f /docker-entrypoint-initdb.d/01-schema.sql

# Run the original seed data
docker compose exec postgres psql -U expert -d product_expert -f /docker-entrypoint-initdb.d/02-seed.sql

# Run the NEW seed additions (new brands, families, patterns, specs)
# First, copy the file into the container:
docker cp db\seed_additions.sql product-expert-db:/tmp/seed_additions.sql
docker compose exec postgres psql -U expert -d product_expert -f /tmp/seed_additions.sql
```

### Mac/Linux

```bash
# Start just the database container
docker compose up -d postgres
sleep 10

# Drop and recreate
docker compose exec postgres psql -U expert -c "DROP DATABASE IF EXISTS product_expert;"
docker compose exec postgres psql -U expert -c "CREATE DATABASE product_expert;"

# Run schema + original seed
docker compose exec postgres psql -U expert -d product_expert -f /docker-entrypoint-initdb.d/01-schema.sql
docker compose exec postgres psql -U expert -d product_expert -f /docker-entrypoint-initdb.d/02-seed.sql

# Run new seed additions
docker cp db/seed_additions.sql product-expert-db:/tmp/seed_additions.sql
docker compose exec postgres psql -U expert -d product_expert -f /tmp/seed_additions.sql
```

### Verify the seed worked

```powershell
docker compose exec postgres psql -U expert -d product_expert -c "SELECT code, name FROM brands ORDER BY code;"
```

You should see **12 brands** including: ARES, ABS, BSI, CBS, Celsius, CME, Corepoint, COL, DAI, LABRepCo, SLW, VWR.

```powershell
docker compose exec postgres psql -U expert -d product_expert -c "SELECT COUNT(*) FROM product_families;"
```

Should show **24+** product families (original 17 plus 7 new ones).

```powershell
docker compose exec postgres psql -U expert -d product_expert -c "SELECT COUNT(*) FROM model_patterns;"
```

Should show **30+** model patterns (original 15 plus 15 new ones).

---

## Phase 6: Start All Services

```powershell
# Windows
.\ops.ps1 up
```

```bash
# Mac/Linux
make up
```

Wait 30 seconds, then verify:

```powershell
.\ops.ps1 health
```

Expected: `{"status":"healthy","components":{"database":"connected","redis":"connected"}}`

```powershell
.\ops.ps1 stats
```

Should show 0 products, 0 documents (empty database ready for ingestion).

---

## Phase 7: Prepare Documents for Ingestion

### Step 7.1 — Organize your PDF files

Place ALL your product documents into the `data\samples\` directory. Use the recommended naming convention:

```
{Brand}_{ProductLine}_{Model}_{DocType}.{ext}

Examples:
  ARES_CRT_CRT-ARS-HC-S26S_PDS.pdf
  CME_NSF_CMEB-REF-P-10PT5-G-NSF_PDS.pdf
  DAI_CRT_CRT-DAI-HC-UCBI-0204-LH_Cutsheet.pdf
  Corepoint_CRT_CRTPR031WWG-0_Cutsheet.pdf
  ABS_Premier_ABT-HC-26S_PDS.pdf
```

> **Tip:** The naming convention is recommended but not required. The extraction pipeline detects the brand and model number from the document content itself. But good naming helps you track what's been ingested.

### Step 7.2 — Also include image files

Place product images (JPG/PNG) in the same directory. The system will classify them as `product_image` type:

```
ARES_CRT-ARS-HC-UCBI-0404-LH_Int_Image.jpg
CME_CMEB-REF-4PT6-S-HCF_Ext_Image.jpg
```

---

## Phase 8: Ingest All Documents

### Option A: Bulk ingest (all files at once)

```powershell
# Windows
.\ops.ps1 ingest-sample
```

```bash
# Mac/Linux
make ingest-sample
```

This iterates over every `.pdf`, `.txt`, and `.md` file in `data\` and `data\samples\` and ingests each one.

### Option B: Ingest one file at a time (for testing)

```powershell
# Windows — test with one ARES file first
.\ops.ps1 ingest-file data\samples\ARES_CRT_CRT-ARS-HC-S26S_PDS.pdf

# Then a CME file
.\ops.ps1 ingest-file data\samples\CME_NSF_CMEB-REF-P-10PT5-G-NSF_PDS.pdf
```

```bash
# Mac/Linux
make ingest-file FILE=data/samples/ARES_CRT_CRT-ARS-HC-S26S_PDS.pdf
```

### Expected output per file

```json
{
  "job_id": "a1b2c3d4-...",
  "status": "processing",
  "files_accepted": 1,
  "message": "1 file(s) queued for processing"
}
```

---

## Phase 9: Verify Everything Works

### Step 9.1 — Check system stats

```powershell
.\ops.ps1 stats
```

You should see non-zero counts for products, documents, and chunks.

### Step 9.2 — Check for spec conflicts

```powershell
.\ops.ps1 conflicts
```

Review any conflicts. For cross-brand products (same physical unit, different brand label), minor conflicts are expected and normal.

### Step 9.3 — Search for new brands

```powershell
# Search for ARES products
.\ops.ps1 products "ARES"

# Search for CME products
.\ops.ps1 products "CME"

# Search for CRT (controlled room temperature) products
.\ops.ps1 products "controlled room temperature"
```

### Step 9.4 — Verify brand detection

```powershell
docker compose exec postgres psql -U expert -d product_expert -c "
  SELECT p.model_number, b.code AS brand, p.storage_capacity_cuft, p.door_type
  FROM products p
  JOIN brands b ON p.brand_id = b.id
  ORDER BY b.code, p.model_number
  LIMIT 30;
"
```

You should see products with brand codes ARES, CME, Corepoint, DAI alongside the original ABS, LABRepCo, etc.

### Step 9.5 — Test the Q&A endpoint

```powershell
.\ops.ps1 test-ask "What ARES controlled room temperature cabinets are available?"
.\ops.ps1 test-ask "Show me CME Corp NSF vaccine refrigerators"
.\ops.ps1 test-ask "Compare the CRT-ARS-HC-S26S with CMEB-REF-P-26-G-NSF"
```

### Step 9.6 — Run the full smoke test

```powershell
.\ops.ps1 smoke-test
```

All 6 checks should pass.

---

## Troubleshooting

### "Brand detected as ABS but document is ARES/DAI/CME"

This was the main bug the fix addresses. After applying the new `003_extraction_pipeline.py`, brand detection uses model number prefixes first (CRT-ARS → ARES, CMEB → CME), which is far more reliable than text pattern matching.

If you still see incorrect brand detection, check:
1. The file was actually re-ingested after the code change (not a cached result)
2. The API container was rebuilt (`docker compose build api`)

### "seed_additions.sql fails with duplicate key"

This is safe to ignore — the `ON CONFLICT DO NOTHING` clauses handle re-runs. If you see actual errors (not constraint violations), check that the original `02-seed.sql` ran first.

### "Model number not extracted from document"

Check the API logs for the specific file:

```powershell
.\ops.ps1 logs
```

Look for warnings like "No model numbers found". The model may use a pattern not yet covered. You can add patterns to the `MODEL_PATTERNS` list in `003_extraction_pipeline.py`.

### Container keeps restarting after code change

There's likely a Python import error. Check:

```powershell
docker compose logs api --tail 50
```

Common cause: if you edited `002_models.py` and introduced a syntax error. Restore from backup:

```powershell
Copy-Item app\002_models.py.bak app\002_models.py
docker compose build api
.\ops.ps1 up
```

---

## Summary of What Changed

| File | What Changed |
|------|-------------|
| `003_extraction_pipeline.py` | Brand detection uses model numbers first; added CMEB/CRT-ARS/CRTPR regex patterns; added CMEB capacity PT parser; added 15+ new FIELD_MAP entries; fixed document classification for CME NSF sheets |
| `002_models.py` | `parse_certifications()` now handles UL-C-UL, C-UL, Intertek, NFPA 99, Class 1 Division II |
| `seed_additions.sql` | 7 new brands, 7 new product families, 15 new model patterns, 12 new spec registry entries, 5 new equivalence rules |
| `pdf_analysis_context_v2.py` | Reference document: 11 brands, 24 cataloged models, CMEB grammar, CRT grammar |
