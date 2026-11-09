# Parsing Scripts

Scripts for parsing BSI IT-Grundschutz documents into structured JSON format.

## Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Scripts](#scripts)
  - [parse_glossar.py](#parse_glossarpy)
  - [parse_grundschutz.py](#parse_grundschutzpy)
- [parse_standards_pdf.py](#parse_standards_pdfpy)
- [gski_pipeline.py](#gski_pipelinepy)
- [run_praktiker_exam.py](#run_praktiker_exampy)
- [Output Structure](#output-structure)
- [JSON Schemas](#json-schemas)

---

## Overview

These scripts extract structured data from BSI IT-Grundschutz source documents:

| Script | Input | Output |
|--------|-------|--------|
| `parse_glossar.py` | XML Kompendium | `glossar.json` |
| `parse_grundschutz.py` | XML Kompendium | `grundschutz.json` |
| `parse_standards_pdf.py` | BSI Standard 200-* PDFs | Individual chunk files |
| `run_praktiker_exam.py` | Preprocessed corpus and `08_IT-GS-Praktiker-Pruefungsfragen.json` | Exam scores with and without retrieval, see `data/results/praktiker-exam-2026-11-09.md` |

---

## Prerequisites

All dependencies are managed via `uv`. From the project root:

```bash
# Dependencies are already in pyproject.toml
uv sync
```

Required packages:
- `lxml` - XML parsing with namespace support
- `pymupdf` - PDF text extraction

---

## Scripts

### parse_glossar.py

Extracts glossary terms from the IT-Grundschutz-Kompendium XML for use in RAG query expansion.

**Usage:**
```bash
uv run python scripts/parse_glossar.py
```

**Input:** `data/data_raw/XML_Kompendium_2023.xml`

**Output:** `data/data_preprocessed/glossar.json`

**Features:**
- Extracts term definitions from `<emphasis role="strong">` elements
- Detects cross-references ("Siehe auch [Term]")
- Outputs structured JSON with term count statistics

---

### parse_grundschutz.py

Parses the complete IT-Grundschutz-Kompendium XML into a deeply nested JSON structure.

**Usage:**
```bash
uv run python scripts/parse_grundschutz.py
```

**Input:** `data/data_raw/XML_Kompendium_2023.xml`

**Output:** `data/data_preprocessed/grundschutz.json`

**Extracts:**
- **Rollen** (29 role definitions)
- **Elementare Gefährdungen** (47 threats: G 0.1 – G 0.47)
- **Schichten** (10 layers: ISMS, ORP, CON, OPS, DER, APP, SYS, IND, NET, INF)
- **Bausteine** (111 modules with nested structure)
- **Anforderungen** (1978 requirements: Basis, Standard, Erhöht)

**Features:**
- Deep hierarchy preserving Schicht → Baustein → Anforderung relationships
- Extracts Zuständigkeiten (responsibilities) from tables
- Detects modal verbs (MUSS, SOLLTE, DARF NICHT, etc.)
- Extracts cross-references between Bausteine

---

### parse_standards_pdf.py

Parses BSI Standard 200-* PDF documents into individual chunk files.

**Usage:**
```bash
uv run python scripts/parse_standards_pdf.py
```

**Input:** `data/data_raw/standard_200_*.pdf`

**Output:** `data/data_preprocessed/standards/`

**Features:**
- Detects headers by numbering pattern (1, 1.1, 1.1.1, etc.) and font formatting
- Filters out page headers/footers
- Preserves full header hierarchy for each chunk
- Extracts modal verbs from content
- Creates index files for navigation

**Output structure:**
```
data/data_preprocessed/standards/
├── _index.json                    # Overall index
├── standard_200_1/
│   ├── _index.json               # Document index
│   ├── 1.json                    # "1 Einleitung"
│   ├── 1_1.json                  # "1.1 ..."
│   └── ...
├── standard_200_2/
├── standard_200_3/
└── standard_200_4/
```

---

## Output Structure

### Directory Layout

```
data/
├── data_raw/                          # Source documents
│   ├── XML_Kompendium_2023.xml
│   ├── standard_200_1.pdf
│   ├── standard_200_2.pdf
│   ├── standard_200_3.pdf
│   └── standard_200_4.pdf
│
└── data_preprocessed/                 # Parsed output
    ├── glossar.json                   # Glossary terms
    ├── grundschutz.json               # Full Kompendium structure
    └── standards/                     # PDF chunks
        ├── _index.json
        ├── standard_200_1/
        ├── standard_200_2/
        ├── standard_200_3/
        └── standard_200_4/
```

---

## JSON Schemas

### Glossar Term

```json
{
  "term": "Informationssicherheitsbeauftragte (ISB)",
  "definition": "Der oder die ISB ist zuständig für...",
  "see_also": ["ISMS", "Sicherheitskonzept"]
}
```

### Anforderung (Requirement)

```json
{
  "id": "SYS.1.9.A11",
  "xml_id": "scroll-bookmark-2493",
  "typ": "anforderung",
  "schicht": {
    "id": "SYS",
    "name": "IT-Systeme",
    "typ": "system"
  },
  "baustein": {
    "id": "SYS.1.9",
    "titel": "Terminalserver",
    "xml_id": "scroll-bookmark-2466"
  },
  "anforderung": {
    "titel": "Sichere Konfiguration von Profilen",
    "typ": "S",
    "typ_lang": "Standard-Anforderung",
    "verantwortliche": null
  },
  "zustaendigkeiten": {
    "grundsaetzlich": ["IT-Betrieb"],
    "weitere": ["Planende"]
  },
  "inhalt": "Benutzende SOLLTEN ihre spezifischen Einstellungen...",
  "modal_verben": ["SOLLTEN", "SOLLTE"],
  "cross_references": []
}
```

### PDF Chunk

```json
{
  "id": "3_2_1",
  "header": "3.2.1 Festlegung des Geltungsbereichs",
  "header_hierarchy": [
    {"level": 1, "number": "3", "title": "IT-Grundschutz-Methodik"},
    {"level": 2, "number": "3.2", "title": "Strukturanalyse"},
    {"level": 3, "number": "3.2.1", "title": "Festlegung des Geltungsbereichs"}
  ],
  "content": "Der Geltungsbereich (Scope) legt fest...",
  "pages": {"start": 15, "end": 16},
  "modal_verben": ["MUSS", "SOLLTE"],
  "source": {
    "document": "standard_200_2",
    "file": "standard_200_2.pdf"
  }
}
```

---

### gski_pipeline.py

Notebook-friendly helpers for embedding preprocessed docs and upserting into Qdrant. The module does **not** do any preprocessing; you pass in docs from your notebook.

**Usage (from Jupyter):**
```python
from scripts.gski_pipeline import ingest_docs

docs = [
    {"id": "REQ-1", "text": "Beispieltext ...", "meta": {"source": "grundschutz.json"}}
]

ingest_docs(docs, collection_name="grundschutz_json", recreate=True)
```

---

## Modal Verbs Reference

| Verb | Obligation Level | German |
|------|------------------|--------|
| `MUSS` / `MÜSSEN` | Mandatory | Verpflichtend |
| `DARF NUR` | Restriction | Einschränkung |
| `DARF NICHT` / `DÜRFEN NICHT` | Prohibition | Verboten |
| `SOLLTE` / `SOLLTEN` | Recommended | Empfohlen |
| `SOLLTE NICHT` / `SOLLTEN NICHT` | Not recommended | Nicht empfohlen |

---

## Anforderungstypen (Requirement Types)

| Type | Code | Description |
|------|------|-------------|
| Basis-Anforderung | `B` | Mandatory for all protection levels |
| Standard-Anforderung | `S` | Recommended for standard protection |
| Erhöhter Schutzbedarf | `H` | For enhanced protection requirements |

---

## run_praktiker_exam.py

Answers the 71 multiple-choice questions of the IT-Grundschutz-Praktiker exam (`data/data_evaluation/08_IT-GS-Praktiker-Pruefungsfragen.json`) with and without retrieval and scores them against the key (issue #15). The corpus is built from `grundschutz.json` (requirements, Baustein descriptions, threats), the standards chunks and `glossar.json`; embeddings are cached in the output folder, retrieval uses an in-memory Qdrant with top-k 5.

```bash
set -a; . notebooks/.env; set +a
uv run python scripts/run_praktiker_exam.py . data/results/praktiker-exam-$(date +%F) gpt-oss-120b gemma-4-31b
```

Reads `LITELLM_API_BASE`, `LITELLM_API_KEY` and `EMBEDDING_MODEL`; falls back to the AI Hub with `AISC_API_KEY`. Writes `summary.json` and one `results_<model>_<rag|no_rag>.json` per condition. The run of 2026-11-09 is documented in `data/results/praktiker-exam-2026-11-09.md`.
