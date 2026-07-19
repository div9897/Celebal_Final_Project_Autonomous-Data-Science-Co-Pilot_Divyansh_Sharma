# Autonomous Data Science Co-Pilot

An AI agent that acts like a junior data analyst: upload a CSV/Excel/JSON
file, ask a question in plain English, and the agent writes, runs, and
self-corrects Python/Pandas code until it produces a chart or insight.

## Status: Phase 1 — Foundation
- [x] Project scaffold
- [x] File upload (CSV / Excel / JSON) + schema preview
- [x] Gemini LLM connection wrapper
- [ ] Agent code-generation loop (Phase 3)
- [ ] Sandboxed execution (Phase 4)
- [ ] Self-correction loop (Phase 5)
- [ ] RAG over Python/Pandas docs (Phase 6)
- [ ] All 5 use cases demoed (Phase 7)

## Setup

1. **Clone and enter the repo**
   ```bash
   git clone <your-repo-url>
   cd ds-copilot
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate    # Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up your API key**
   ```bash
   cp .env.example .env
   ```
   Then edit `.env` and paste your Gemini API key:
   ```
   GEMINI_API_KEY=your_key_here
   ```
   Get a free key at [aistudio.google.com](https://aistudio.google.com) → "Get API key".

5. **Run the app**
   ```bash
   streamlit run app/main.py
   ```

6. **Verify setup**
   - Open the app in your browser (Streamlit will print the URL)
   - Click "Test Gemini Connection" in the sidebar — should show ✅
   - Upload a sample CSV — should show a preview + schema

## Project structure

```
ds-copilot/
├── app/
│   ├── main.py          # Streamlit UI entry point
│   ├── llm_client.py     # Gemini API wrapper (swap providers here only)
│   └── data_loader.py    # CSV/Excel/JSON loading + schema summarization
├── rag/                  # (Phase 6) doc chunking + vector store
├── sandbox/              # (Phase 4) isolated code execution
├── docs/                 # Pandas/Python doc corpus for RAG
├── data/                 # sample test files
├── requirements.txt
└── .env.example
```

## Security notes
- Never commit `.env` — it's already in `.gitignore`.
- If an API key is ever pasted somewhere outside `.env` (chat, docs, etc.),
  revoke it in Google AI Studio and generate a new one.
