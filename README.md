# 📄 Inverted Index Past Paper Worksheet Generator

> **CS201: Data Structures II — Spring 2026**  
> A Python tool that parses Cambridge O/A-Level past paper PDFs, indexes questions by topic using a custom inverted index, and generates clean, print-ready A4 PDF worksheets with questions selected via a Fisher-Yates shuffle and greedy fill.

---

## 🧠 Motivation

Preparing for Cambridge exams means manually hunting through years of past papers to find questions on specific topics — a slow and tedious process. This project automates that entirely: point it at a folder of past paper PDFs and it builds a searchable index, lets you pick a topic and a mark target, and outputs a clean, watermark-free worksheet ready to print.

---

## ✨ Features

| Feature | Description |
|---|---|
| **PDF Parser** | Extracts questions from raw Cambridge PDFs using bounding-box geometry and a 5-point vertical bucket-sort algorithm to reliably isolate questions from headers, footers, and margin text |
| **Custom Inverted Index** | Maps composite keys (`subject_topic_paperType`) to postings lists of question IDs — O(1) insert and lookup, with union/intersection set operations |
| **Fisher-Yates Question Selector** | Shuffles the candidate pool using an in-place Fisher-Yates algorithm (O(n)), then greedily fills the worksheet to reach a user-specified mark target — ensuring every run produces a different worksheet |
| **Worksheet Generator** | Compiles selected questions into a clean A4 PDF using PyMuPDF's vector-preserving renderer — no rasterisation, full diagram quality, source watermarks removed |
| **Topic Mapper** | Keyword frequency scoring (bag-of-words) against Cambridge syllabus keyword maps to tag each question with its topic, with AS/A2 tier awareness |
| **Interactive Demo CLI** | Two-mode terminal interface: full worksheet generation pipeline and an isolated data structure operations walkthrough |
| **Test Suite** | Unit tests covering all core modules: index operations, PDF parsing, worksheet generation, topic mapping, and the demo runner |

---

## 🏗️ Project Structure

```
DS2-Project/
├── inverted_index.py        # Core data structure — custom InvertedIndex
├── pdf_parser.py            # BBox-based question extraction from PDFs
├── topic_mapper.py          # Keyword-scoring topic tagger (AS/A2 aware)
├── worksheet_generator.py   # A4 PDF worksheet builder
├── build_index.py           # Full ingestion pipeline: PDF → InvertedIndex
├── demo_runner.py           # Interactive CLI (worksheet gen + DS demo)
├── config.py                # Project-wide constants and paths
├── requirements.txt
├── data/
│   └── keywords/
│       └── keyword_map.json # Cambridge syllabus keyword maps
├── assets/
│   └── worksheet_preview.png
└── tests/
    ├── test_inverted_index.py
    ├── test_pdf_parser.py
    ├── test_topic_mapper.py
    ├── test_worksheet_generator.py
    └── test_demo_runner.py
```

---

## 🔧 Tech Stack

- **Python 3.x** — core language
- **PyMuPDF (fitz)** — PDF parsing and vector-quality rendering
- **Flask** — web backend routing
- **JSON** — index and keyword map persistence

---

## 🚀 Quick Start

**1. Clone the repository**
```bash
git clone https://github.com/widadfatimakhan/DS2-Project.git
cd DS2-Project
```

**2. Install dependencies**
```bash
pip install -r requirements.txt
```

**3. Add past paper PDFs**

Place Cambridge past paper PDFs in `data/papers/`. File names should follow the standard Cambridge convention (e.g. `9702_w24_qp_21.pdf`).

**4. Build the index**
```bash
python build_index.py
```

**5. Run the demo**
```bash
python demo_runner.py
```

---

## 📐 How It Works

```
Cambridge PDFs  ──►  pdf_parser.py      ──►  Structured question records
                     (BBox + bucket sort)           │
                                                    ▼
                     topic_mapper.py    ──►  Topic-tagged records
                     (bag-of-words,              │
                      AS/A2 aware)               │
                                                    ▼
                     inverted_index.py  ──►  Composite key → postings list
                                                    │
                     Fisher-Yates shuffle ◄──────────┘
                     + greedy fill
                           │
                           ▼
                     worksheet_generator.py  ──►  Clean A4 PDF output
```

1. **Parse** — `pdf_parser.py` walks each PDF line by line, uses bounding-box coordinates to skip headers/footers, and groups text into 5-point vertical buckets to correct for scan misalignments. Questions are identified by an `x < 85` left-margin fence.

2. **Tag** — `topic_mapper.py` scores each question's text against keyword maps loaded from `keyword_map.json` using bag-of-words scoring, with separate keyword sets for AS and A2 tiers.

3. **Index** — `build_index.py` inserts tagged questions into the `InvertedIndex` under composite keys like `9702_Kinematics_p21`. Year is stored in the record and applied as a post-lookup filter, not encoded in the key.

4. **Select** — The candidate pool is randomised with an in-place Fisher-Yates shuffle, then a greedy pass picks questions until the mark target is reached. Every run with the same query produces a different worksheet.

5. **Generate** — `worksheet_generator.py` opens each source PDF, crops out Cambridge's margin chrome (sidebars, barcodes, footers), and stamps each question region into a blank A4 document using `show_pdf_page()` — preserving full vector quality.

---

## 🗂️ Inverted Index Design

The custom `InvertedIndex` maps composite keys → postings lists, with a separate `question_store` keyed by ID so records are never duplicated across multiple topic tags.

```
Key format:   "{subject}_{topic}_{paper_type}"
Example:      "9702_Kinematics_p21"

              ┌─────────────────────────────┐
  Key ───────►│ Postings List               │
              │  [qid_1, qid_4, qid_9, ...] │
              └─────────────────────────────┘
                         │
                         ▼  fetch_documents()
              ┌─────────────────────────────┐
              │ Question Store              │
              │  { qid: full record, ... }  │
              └─────────────────────────────┘
```

**Public API:**

| Method | Complexity | Description |
|---|---|---|
| `insert(key, record)` | O(1) | Add a question under a composite key |
| `query(key)` | O(1) | Get postings list for a key |
| `union(keys)` | O(n) | IDs in ANY of the given keys |
| `intersect(keys)` | O(n) | IDs in ALL of the given keys |
| `fetch_documents(ids)` | O(k) | Resolve IDs to full records with optional year filter |
| `delete(key, qid)` | O(n) | Remove one ID or the entire key |
| `remove_question(qid)` | O(k) | Purge an ID from every postings list |

---

## 🎲 Fisher-Yates Shuffle

The question selector uses a custom in-place implementation of the Fisher-Yates algorithm rather than the standard library's `random.shuffle`. For each position `i` from `0` to `n-1`, a random index `j` in `[0, i]` is picked and `lst[i]` and `lst[j]` are swapped — guaranteeing a uniformly random permutation in O(n) time. After shuffling, a greedy pass fills the worksheet up to the mark target.

```python
def fisher_yates_shuffle(lst):
    for i in range(len(lst)):
        j = random.randint(0, i)
        lst[i], lst[j] = lst[j], lst[i]
    return lst
```

---

## 🖥️ Demo CLI Modes

Running `python demo_runner.py` gives two modes:

**Mode 1 — Generate a Worksheet** walks the full 8-stage pipeline interactively: pick curriculum level → subject → tier (AS/A2) → paper style (MCQ/Theory) → topics → year range → mark target → worksheet PDF.

**Mode 2 — Data Structure Operations** demonstrates each `InvertedIndex` method in isolation: INSERT, SEARCH (O(1) hash lookup), UNION, INTERSECT, DELETE, VIEW TREE, and a BENCHMARK comparing index lookup against a naive O(n) linear scan.

---

## 🧪 Running Tests

```bash
python -m pytest tests/ -v
```

---

## 👥 Team

Built as a team of 4 for CS201: Data Structures II, Spring 2026.

---

## 📜 License

This project is for academic purposes.