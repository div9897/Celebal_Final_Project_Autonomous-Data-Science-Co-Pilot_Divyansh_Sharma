"""
main.py
-------
Autonomous Data Science Co-Pilot — Streamlit entry point.

Upload a CSV / Excel / JSON file, ask a question in plain English, and an
LLM-powered agent writes pandas/matplotlib code, runs it in an isolated
sandbox, and self-corrects (grounded in retrieved documentation) if it
fails — until it produces a working chart and insights.
"""

import streamlit as st
import matplotlib.pyplot as plt
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "sandbox"))

from data_loader import load_file, build_schema_summary
from llm_client import test_connection
from agent import generate_code
from executor import run_in_sandbox

MAX_ATTEMPTS = 3

st.set_page_config(page_title="Data Science Co-Pilot", page_icon="📊", layout="wide")

st.title("📊 Autonomous Data Science Co-Pilot")
st.caption("Upload a file, ask a question in plain English — the agent does the rest.")

if "conversation" not in st.session_state:
    st.session_state["conversation"] = []  # list of {question, result, attempt_log}

# SIDEBAR
with st.sidebar:
    st.header("⚙️ System Check")
    if st.button("Test Gemini Connection"):
        with st.spinner("Pinging Gemini..."):
            try:
                result = test_connection()
                st.success(f"✅ {result}")
            except Exception as e:
                st.error(f"❌ Connection failed: {e}")

    st.divider()
    st.header("📋 Example Questions")
    with st.expander("1️⃣ Sales Dashboard"):
        st.caption("File: `data/sample_sales.csv`")
        st.code("Show me revenue by region as a bar chart", language=None)
    with st.expander("2️⃣ Data Quality Audit"):
        st.caption("File: `data/sample_customers.csv`")
        st.code(
            "Check this data for missing values, duplicate rows, "
            "and any outliers, and summarize what you find",
            language=None,
        )
    with st.expander("3️⃣ Trend Analysis"):
        st.caption("File: `data/sample_traffic.csv`")
        st.code("Is traffic growing over time? Show a trend line", language=None)
    with st.expander("4️⃣ Cohort Analysis"):
        st.caption("File: `data/sample_customers.csv`")
        st.code(
            "Segment customers by plan and show average monthly "
            "spend per segment as a chart",
            language=None,
        )
    with st.expander("5️⃣ Ad-hoc Query"):
        st.caption("File: any of the above")
        st.code("Which region has the most customers on the Enterprise plan?", language=None)

    st.divider()
    dev_mode = st.checkbox("🛠️ Developer mode", value=False,
                            help="Shows internal details: generated code, retry attempts, RAG sources.")

# FILE UPLOAD 
uploaded_file = st.file_uploader(
    "Upload your data file",
    type=["csv", "xlsx", "xls", "json"],
    help="Supported formats: CSV, Excel, JSON",
)

if uploaded_file is not None:
    try:
        df = load_file(uploaded_file)

        # Reset conversation history when a new file is uploaded
        if st.session_state.get("current_file") != uploaded_file.name:
            st.session_state["conversation"] = []
            st.session_state["current_file"] = uploaded_file.name

        st.session_state["df"] = df

        st.success(f"Loaded **{uploaded_file.name}** — {df.shape[0]} rows × {df.shape[1]} columns")

        with st.expander("Preview & schema", expanded=False):
            col1, col2 = st.columns([2, 1])
            with col1:
                st.subheader("Preview")
                st.dataframe(df.head(10), use_container_width=True)
            with col2:
                st.subheader("Schema")
                st.text(build_schema_summary(df))

    except Exception as e:
        st.error(f"Could not load file: {e}")
else:
    st.info("👆 Upload a CSV, Excel, or JSON file to get started.")

st.divider()

# CONVERSATION HISTORY
for turn in st.session_state["conversation"]:
    with st.chat_message("user"):
        st.markdown(turn["question"])
    with st.chat_message("assistant"):
        result = turn["result"]
        attempt_log = turn["attempt_log"]

        if result["success"]:
            if len(attempt_log) > 1:
                st.caption(f"✅ Succeeded after self-correcting {len(attempt_log) - 1} time(s)")
            if result["image_bytes"]:
                st.image(result["image_bytes"])
            if result["insights"]:
                for point in result["insights"]:
                    st.markdown(f"- {point}")
            if result["stdout"]:
                st.text(result["stdout"])
        else:
            st.error(f"Couldn't complete this after {len(attempt_log)} attempts: {result['error']}")

        if dev_mode:
            with st.expander(f"🔍 Developer details ({len(attempt_log)} attempt(s))"):
                for entry in attempt_log:
                    status = "✅ succeeded" if entry["result"]["success"] else "❌ failed"
                    st.markdown(f"**Attempt {entry['attempt']} — {status}**")
                    if entry["retrieved_docs"]:
                        sources = ", ".join(d["source"] for d in entry["retrieved_docs"])
                        st.caption(f"📚 RAG grounded this fix in: {sources}")
                    st.code(entry["code"], language="python")
                    if not entry["result"]["success"]:
                        st.caption(f"Error: {entry['result']['error']}")

# NEW QUESTION INPUT
if "df" in st.session_state:
    question = st.chat_input("Ask a question about your data...")

    if question:
        df = st.session_state["df"]
        schema = build_schema_summary(df)

        with st.chat_message("user"):
            st.markdown(question)

        with st.chat_message("assistant"):
            previous_error = None
            result = None
            attempt_log = []

            for attempt in range(1, MAX_ATTEMPTS + 1):
                with st.spinner(f"Attempt {attempt}/{MAX_ATTEMPTS}: writing and running code..."):
                    code, retrieved_docs = generate_code(schema, question, previous_error=previous_error)
                    result = run_in_sandbox(code, df)

                attempt_log.append({
                    "attempt": attempt,
                    "code": code,
                    "result": result,
                    "retrieved_docs": retrieved_docs,
                })

                if result["success"]:
                    break
                previous_error = result["error"]

            if result["success"]:
                if len(attempt_log) > 1:
                    st.caption(f"✅ Succeeded after self-correcting {len(attempt_log) - 1} time(s)")
                if result["image_bytes"]:
                    st.image(result["image_bytes"])
                if result["insights"]:
                    for point in result["insights"]:
                        st.markdown(f"- {point}")
                if result["stdout"]:
                    st.text(result["stdout"])
            else:
                st.error(f"Couldn't complete this after {MAX_ATTEMPTS} attempts: {result['error']}")

            if dev_mode:
                with st.expander(f"🔍 Developer details ({len(attempt_log)} attempt(s))"):
                    for entry in attempt_log:
                        status = "✅ succeeded" if entry["result"]["success"] else "❌ failed"
                        st.markdown(f"**Attempt {entry['attempt']} — {status}**")
                        if entry["retrieved_docs"]:
                            sources = ", ".join(d["source"] for d in entry["retrieved_docs"])
                            st.caption(f"📚 RAG grounded this fix in: {sources}")
                        st.code(entry["code"], language="python")
                        if not entry["result"]["success"]:
                            st.caption(f"Error: {entry['result']['error']}")

        st.session_state["conversation"].append({
            "question": question,
            "result": result,
            "attempt_log": attempt_log,
        })
else:
    st.info("Upload a file above to start asking questions.")
