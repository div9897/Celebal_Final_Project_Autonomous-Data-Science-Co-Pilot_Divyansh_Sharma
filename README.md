# 📊 Autonomous Data Science Co-Pilot

**An AI agent that acts like a junior data analyst.** Upload a CSV, Excel, or JSON file, ask a question in plain English, and the agent writes Python/Pandas code, runs it inside an isolated sandbox, checks its own work, and — if it fails — fixes itself using retrieved documentation, until it hands you back a working chart and a set of insights. No code required from the user, ever.

**🔗 Live app:** https://celebalfinalprojectautonomous-data-science-co-pilotdivyanshsha.streamlit.app/

> Built as a Summer Internship 2025 final project (Agentic AI / Data Engineering / Full-Stack Python).

---

## Table of Contents
1. [The Problem This Solves](#the-problem-this-solves)
2. [What Makes This "Agentic" (Not Just a Chatbot)](#what-makes-this-agentic-not-just-a-chatbot)
3. [System Architecture](#system-architecture)
4. [The Full Request Lifecycle, Step by Step](#the-full-request-lifecycle-step-by-step)
5. [Project Structure](#project-structure)
6. [Component Deep-Dive](#component-deep-dive)
7. [Design Decisions & Trade-offs (and why)](#design-decisions--trade-offs-and-why)
8. [Security Model — What's Actually Sandboxed](#security-model--whats-actually-sandboxed)
9. [The 5 Use Cases](#the-5-use-cases)
10. [Setup & Local Installation](#setup--local-installation)
11. [Deployment](#deployment)
12. [Known Limitations & Honest Caveats](#known-limitations--honest-caveats)
13. [What I'd Build Next](#what-id-build-next)
14. [Tech Stack Summary](#tech-stack-summary)

---

## The Problem This Solves

Most business teams sit on mountains of raw data — CSVs from a POS system, an Excel export from finance, a JSON dump from an internal tool — but don't have anyone on hand who can write a `groupby()` or knows what a `pivot_table` is. Traditionally, this means either:
- Waiting on a data analyst who has a backlog, or
- Asking ChatGPT for code, then manually copy-pasting it into a notebook, fixing the inevitable errors yourself, and running it

This project removes both bottlenecks. A non-technical person uploads a file, types a question the way they'd ask a colleague ("is our revenue growing?", "which customers are we losing?"), and gets back a finished chart and a written takeaway — not a code snippet they have to run themselves.

## What Makes This "Agentic" (Not Just a Chatbot)

The key differentiator, straight from the project brief, is **"Text-Out" → "Action-Out."** A chatbot gives you an answer in words. An agent *does something* and hands you the finished result. Concretely, this system:

1. **Writes its own code** — it isn't following a hardcoded template per question; Gemini genuinely generates novel pandas/matplotlib code based on the specific question and the specific dataset's schema.
2. **Executes that code itself**, in an isolated environment, rather than just showing it to the user.
3. **Observes its own failures** — when the sandbox reports an error, the agent doesn't just surface the error to the user and stop. It reads the error, retrieves relevant documentation, and tries again — autonomously, with no human in the loop.
4. **Grounds its self-correction in real references** (RAG), rather than purely guessing from its own training memory, which can be stale or simply wrong about a specific error's fix.

This loop — **generate → execute → observe → retrieve → retry** — is what separates an "agent" from a single LLM API call, and it's the core engineering challenge this project set out to solve.

## System Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                     Streamlit UI (app/main.py)                │
│   File upload · Chat interface · Developer mode toggle        │
└───────────────────────────┬────────────────────────────────────┘
                            │
            ┌───────────────┴────────────────┐
            │                                 │
┌───────────▼────────────┐        ┌──────────▼─────────────┐
│   data_loader.py         │        │      agent.py            │
│  Reads CSV/Excel/JSON    │        │  Builds prompts, calls   │
│  into a DataFrame; builds│        │  Gemini, extracts code   │
│  a compact schema summary│        │  from the response       │
└───────────────────────────┘       └──────────┬─────────────┘
                                                │
                          ┌─────────────────────┼─────────────────────┐
                          │                     │                     │
                ┌─────────▼──────────┐  ┌───────▼────────┐  ┌────────▼─────────┐
                │   llm_client.py     │  │  rag/retriever  │  │ sandbox/executor  │
                │  Gemini API wrapper │  │  TF-IDF search  │  │  Isolated         │
                │  (google-genai SDK) │  │  over docs/*.md │  │  subprocess       │
                │                     │  │  for error fixes │  │  execution        │
                └─────────────────────┘  └─────────────────┘  └───────────────────┘
```

Every arrow above is a genuine module boundary — not just a conceptual split. This matters because it means, for example, swapping Gemini for a different LLM provider only touches `llm_client.py`; nothing else in the codebase needs to know or care.

## The Full Request Lifecycle, Step by Step

Here's exactly what happens between a user typing a question and seeing a chart, tracing through the actual code:

1. **File upload** (`data_loader.py`) — the file is read into a pandas DataFrame. Critically, **the full dataset is never sent to the LLM** — only a compact schema summary (column names, dtypes, non-null counts, and 3 sample rows) is built and used in prompts. This keeps prompts small, keeps API costs down, and avoids unnecessarily exposing potentially sensitive data to a third-party API.

2. **Prompt construction** (`agent.py::_build_prompt`) — the schema summary and the user's plain-English question are combined into a prompt, along with a system instruction that constrains Gemini to specific output conventions: assume `df` already exists, store any chart in a variable called `fig`, store 2-4 observations in a variable called `insights`, output nothing but a single Python code block.

3. **Code generation** (`agent.py::generate_code` → `llm_client.py::ask_llm`) — the prompt is sent to Gemini (currently `gemini-flash-lite-latest`, chosen for its more generous free-tier rate limit compared to other Flash variants). The response is parsed to pull out just the code, stripping any markdown fencing or commentary Gemini might add despite instructions not to.

4. **Sandboxed execution** (`sandbox/executor.py::run_in_sandbox`) — this is the security-critical step, covered in detail below. The generated code is written into a temporary runner script and executed as a **separate OS subprocess** (not in the same process as the Streamlit app), with a 15-second timeout and a restricted set of allowed imports/builtins. The DataFrame is passed across the process boundary via a temporary CSV file (simpler and safer than pickling arbitrary Python objects). The chart (if any) is captured by having the child process save it to a PNG file; insights are returned via a JSON file. The parent process reads both back.

5. **Success or failure branch:**
   - **On success:** the PNG bytes and insights list are returned up to the UI, which renders the image and bullet points in the chat.
   - **On failure:** the exact error message (e.g. `KeyError: 'regionn'`) is captured and fed into the next loop iteration.

6. **RAG-grounded retry** (`rag/retriever.py::retrieve`) — if step 5 failed, the error message itself becomes a search query against a small, hand-curated corpus of Pandas/Python/Matplotlib documentation (`docs/*.md`), using TF-IDF + cosine similarity. The top 2 most relevant documentation chunks are pulled back and inserted into the *next* prompt to Gemini, alongside the original error — so the correction is grounded in an actual reference, not just Gemini's unaided guess.

7. **Repeat up to 3 attempts total.** If all 3 fail, the user sees a clear final error message rather than a silent hang or a stack trace. If any attempt succeeds, the loop stops immediately.

8. **Conversation history** — each question/answer pair (including the full attempt log, for transparency) is appended to `st.session_state["conversation"]`, so multiple questions in a session stack up like a real chat rather than overwriting each other.

## Project Structure

```
ds-copilot/
├── app/
│   ├── main.py            # Streamlit UI: chat interface, file upload, orchestration
│   ├── agent.py            # Prompt construction, code generation, RAG-aware retry logic
│   ├── llm_client.py        # Thin wrapper around the Gemini API (google-genai SDK)
│   └── data_loader.py       # CSV/Excel/JSON loading + schema summarization
├── sandbox/
│   └── executor.py         # Isolated subprocess execution: restricted imports, timeout
├── rag/
│   ├── build_index.py       # Chunks docs/*.md and builds the TF-IDF search index
│   ├── retriever.py         # Given an error message, returns the most relevant doc chunks
│   └── index.pkl            # Pre-built index (regenerate via build_index.py after editing docs/)
├── docs/                    # Curated Pandas/Python/Matplotlib documentation corpus
│   ├── pandas_keyerror_indexing.md
│   ├── pandas_groupby_aggregation.md
│   ├── pandas_datetime_handling.md
│   ├── pandas_dtype_errors.md
│   └── matplotlib_plotting.md
├── data/                    # Sample datasets covering all 5 use cases
│   ├── sample_sales.csv      # Sales Dashboard (revenue by region)
│   ├── sample_customers.csv  # Data Quality Audit + Cohort Analysis (has planted issues)
│   └── sample_traffic.csv    # Trend Analysis (90 days, real upward trend + seasonality)
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md                # You are here
```

~1,100 lines of application code across 7 Python modules, plus ~300 lines of curated documentation and 3 purpose-built sample datasets.

## Component Deep-Dive

### `llm_client.py` — the only file that knows about Gemini
Every other module calls `ask_llm(prompt, system_instruction, temperature)` and gets a plain string back. It has no idea the underlying model is Gemini specifically. This is a deliberate abstraction boundary: if this project needed to switch to OpenAI, Claude, or a local model tomorrow, this is the *only* file that would change.

### `data_loader.py` — schema-first, not data-first
`build_schema_summary()` produces something like:
```
Shape: 15 rows x 5 columns
Columns (name : dtype : non-null count):
  - date : object : 15 non-null
  - region : object : 15 non-null
  - revenue : int64 : 15 non-null
Sample rows (first 3):
   date       region  revenue
0  2025-01-05  North   12500
```
This is what gets sent to the LLM — never `df.to_csv()` in full. For a 32,000-row dataset (like the UCI Census Income dataset used during testing), this keeps every single prompt small and cheap regardless of the underlying file's size.

### `agent.py` — the orchestration brain
Contains the system instruction that constrains Gemini's output format, the prompt-building logic (including the RAG hook on retries), and the regex-based code extraction that pulls a clean Python snippet out of Gemini's response even if it wraps it in explanatory text despite being told not to.

### `sandbox/executor.py` — the security boundary
The most engineering-intensive file in the project. Full breakdown in the [Security Model](#security-model--whats-actually-sandboxed) section below, including two real bugs discovered and fixed during development.

### `rag/build_index.py` and `rag/retriever.py` — retrieval-augmented self-correction
`build_index.py` splits each markdown file in `docs/` along its `## ` headers (so each chunk stays topically coherent — e.g., one chunk is entirely about the `.dt` accessor `AttributeError`), then builds a TF-IDF matrix over all chunks using scikit-learn. `retriever.py` loads that index once and, given a query (an error message), returns the top-k chunks ranked by cosine similarity, with a minimum relevance threshold so irrelevant docs aren't injected into prompts when nothing matches well.

## Design Decisions & Trade-offs (and why)

This section exists because **understanding why a choice was made is more valuable, and more defensible in a demo/interview, than just listing what was built.**

### TF-IDF instead of dense embeddings for RAG
The "obvious" RAG stack is sentence-transformers embeddings + FAISS. That path was tried first, and hit a real, concrete constraint: sentence-transformers depends on PyTorch, which is a 1-2GB install — heavy for a project whose actual documentation corpus is a handful of small markdown files. More importantly, for **this specific retrieval task** — matching an error message like `KeyError: 'regionn'` or `AttributeError: Can only use .dt accessor...` against documentation — exact keyword/phrase overlap is arguably *better* than semantic embeddings, since you specifically want an exact match on a function name or exception type, not a fuzzy semantic neighbor. TF-IDF + cosine similarity, using nothing heavier than scikit-learn (already a near-universal dependency), does this well and was verified empirically: four different realistic error messages were tested against the corpus, and each correctly retrieved its matching documentation chunk with a clear score gap over irrelevant chunks.

### Subprocess isolation instead of in-process `exec()`
An earlier version of this project (still visible in `agent.py::run_generated_code`, kept for reference/comparison) ran LLM-generated code via `exec()` directly inside the Streamlit app's own process. This is fine for a quick demo but is a real security gap: if Gemini ever generated something like `import os; os.system(...)`, it would execute with the app's own permissions. `sandbox/executor.py` replaces this with genuine OS-level process isolation.

### Gemini model selection: `gemini-flash-lite-latest`
The project initially used `gemini-2.5-flash`, which was retired for new users mid-project (a real, live example of how fast this space moves). It was then switched to `gemini-flash-latest` (a Google-maintained alias that always points at the current best Flash model, chosen specifically so this doesn't break again on the next model retirement). During testing, `gemini-3.5-flash` (what the alias resolved to at the time) hit its free-tier daily cap of just 20 requests — much stricter than expected. The model was switched again to `gemini-flash-lite-latest`, which carries a materially higher free-tier daily quota, making it the more practical choice for a project involving repeated self-correction loops during both development and demoing.

### Schema-only prompts, never full datasets
Already covered above, but worth restating as a deliberate design principle: this keeps the system viable on real-world datasets of any size (tested successfully against the 32,561-row UCI Census Income dataset) without ballooning prompt costs or token limits.

## Security Model — What's Actually Sandboxed

Since the entire premise of this project is "let an LLM write and run code autonomously," the security boundary deserves an honest, detailed accounting rather than a hand-wave.

### What the sandbox does
- Runs generated code in a **separate OS subprocess**, not the Streamlit app's own process
- Enforces a **15-second timeout**, so an infinite loop or runaway computation can't hang the app
- Blocks the LLM's code from importing `os`, `subprocess`, `socket`, `requests`, `shutil`, `multiprocessing`, and similar modules
- Removes the `open()` builtin entirely from the generated code's execution scope, since legitimate generated code never needs raw file access (data comes in via `df`, output goes out via `fig`/`insights`)
- Confines the subprocess's working directory to a temporary folder that's deleted immediately after execution

### Two real bugs found and fixed during development (worth knowing about)
Building this sandbox surfaced two non-obvious failure modes that are genuinely instructive:

1. **Blocking `os`/`sys` imports by name doesn't work, because they're already loaded.** Pandas and Matplotlib import `os` and `sys` internally before any user code ever runs, so a naive "block the string `os`" check either does nothing (if already-cached modules are allowed) or breaks legitimate plotting code (if they aren't). The fix: the import hook inspects **which code frame is making the import call** — using a sentinel key injected into the exec'd code's globals — so it only blocks imports that originate from the *LLM's own generated code*, not from library internals doing their normal job.

2. **A builtins snapshot taken before installing the restricted import hook silently captured the unrestricted version.** This was caught by literally trying to break the sandbox on purpose (`import os; os.system("echo PWNED")`) — and it printed `PWNED`, confirming the block wasn't actually working despite looking correct in code review. The fix was ordering: build the "safe builtins" dictionary *after* installing the hook, not before.

Both bugs were caught by writing deliberate attack tests (`os.system`, `subprocess.run`, an infinite loop, a direct `open()` call) rather than just testing the happy path — a practice worth highlighting in any discussion of this project's engineering rigor.

### Honest limitation
This is a defense-in-depth sandbox appropriate for a student/demo project, not a substitute for production-grade isolation (gVisor, Docker/Firecracker microVMs, or a fully separate untrusted-execution service) that a real enterprise deployment would need. The current model assumes the LLM is not adversarial, just fallible — it protects against buggy generated code and prevents the most obvious escape vectors, but a sufficiently determined and specifically-crafted payload could likely still find gaps (e.g., certain forms of resource exhaustion, or exploiting an unblocked but still-dangerous stdlib module not on the current blocklist). This trade-off — real protection against realistic failure modes, explicitly not claimed as bulletproof — is a deliberate and defensible scoping decision for a project of this size.

## The 5 Use Cases

All five use cases from the original project brief were implemented and validated:

| # | Use Case | Sample Data | Example Question |
|---|----------|-------------|-------------------|
| 1 | **Sales Dashboard** | `sample_sales.csv` | "Show me revenue by region as a bar chart" |
| 2 | **Data Quality Audit** | `sample_customers.csv` (contains a planted duplicate row, several missing values, and one deliberate decimal-point outlier) | "Check this data for missing values, duplicate rows, and outliers" |
| 3 | **Trend Analysis** | `sample_traffic.csv` (90 days of synthetic data with a genuine upward trend + weekly seasonality) | "Is traffic growing over time? Show a trend line" |
| 4 | **Cohort Analysis** | `sample_customers.csv` | "Segment customers by plan and show average monthly spend per segment" |
| 5 | **Ad-hoc Query** | any file | "Which region has the most customers on the Enterprise plan?" |

The system was also validated against a real-world, messy, third-party dataset — the classic **UCI Census Income (Adult) dataset** (32,561 rows, 15 columns), which uses `"?"` string placeholders instead of true `NaN` for missing values and contains real duplicate rows — a genuinely good stress test for whether the agent's data-quality reasoning goes beyond a naive `.isnull()` check.

## Setup & Local Installation

```bash
git clone <your-repo-url>
cd ds-copilot

python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\Activate.ps1

pip install -r requirements.txt

cp .env.example .env
# Edit .env and add: GEMINI_API_KEY=your_key_here
# Get a free key at https://aistudio.google.com

streamlit run app/main.py
```

If you edit anything in `docs/`, rebuild the RAG index:
```bash
python rag/build_index.py
```

**Windows note:** if `venv\Scripts\Activate.ps1` is blocked by PowerShell's execution policy, run once:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

## Deployment

This project is deployed on **Streamlit Community Cloud**:

**🔗 https://celebalfinalprojectautonomous-data-science-co-pilotdivyanshsha.streamlit.app/**

Deployment specifics:
- **Main file path:** `app/main.py`
- **Secrets:** `GEMINI_API_KEY` is configured via Streamlit Cloud's encrypted Secrets manager (App Settings → Secrets), in TOML format (`GEMINI_API_KEY = "..."`) — never committed to the repository
- **`.gitignore`** excludes `.env`, `venv/`, `__pycache__/`, and other local-only artifacts

## Known Limitations & Honest Caveats

Being upfront about these matters more than pretending they don't exist:

- **Free-tier API rate limits.** Gemini's free tier caps requests per day (as low as 20/day for some model variants encountered during development). Each self-correction attempt costs one request, so heavy testing/demoing can exhaust the daily quota. A paid tier or more conservative usage avoids this in a production setting.
- **The sandbox is defense-in-depth, not airtight** (see the Security Model section above for the full honest breakdown).
- **RAG corpus is small and hand-curated**, not a full scrape of official Pandas/Python documentation. It covers the error categories actually encountered during this project's own testing (KeyErrors, groupby quirks, datetime parsing, dtype conversion, matplotlib plotting), not the entire pandas API surface.
- **Insights are LLM-generated text, not independently verified numbers.** During testing, one case surfaced where the chart and the accompanying insight text appeared to describe different underlying computations — a reminder that "the code ran without error" is not the same guarantee as "the answer is correct," and a good discussion point on the limits of autonomous agents.
- **No persistent storage.** Conversation history lives only in the current browser session's `st.session_state` and is lost on refresh; there's no database backing user history across sessions.

## What I'd Build Next

Given more time, the natural next steps would be:
- Expand the RAG corpus to a genuine scrape of official Pandas/NumPy/Matplotlib docs, chunked more systematically
- Add a lightweight "verification" pass — have a second LLM call check whether the generated insights text actually matches the computed numbers, rather than trusting them blindly
- Move sandboxing from subprocess-level isolation to container-level (Docker) for a meaningfully stronger security boundary
- Add persistent storage (even just SQLite) so conversation history survives a page refresh
- Support chained/follow-up questions that reference the previous answer's result directly, rather than treating each question independently

## Tech Stack Summary

| Layer | Technology | Why |
|---|---|---|
| Frontend / UI | Streamlit | Fast to build a real chat interface; native support for file upload, chat components, and inline images |
| LLM | Google Gemini (`gemini-flash-lite-latest`) via `google-genai` SDK | Most workable free-tier quota among available options for a project requiring repeated self-correction calls |
| Code Execution | Python `subprocess` with a restricted import hook and blocked builtins | Real process isolation without the overhead of a full container runtime |
| RAG / Retrieval | scikit-learn `TfidfVectorizer` + cosine similarity | Lightweight, no large model download, and well-suited to exact error/API-name matching |
| Data Processing | pandas, NumPy, openpyxl | Industry-standard; supports CSV, Excel, and JSON uniformly |
| Visualization | Matplotlib (headless `Agg` backend in the sandbox) | Reliable, well-documented, works without a display in a subprocess |
| Deployment | Streamlit Community Cloud | Free, GitHub-integrated, native secrets management |

---

*Built as a Summer Internship 2025 final project — Autonomous Data Science Co-Pilot.*
