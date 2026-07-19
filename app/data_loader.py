"""
data_loader.py
--------------
Handles reading uploaded CSV / Excel / JSON files into a pandas DataFrame,
and building a compact schema summary to send to the LLM.

IMPORTANT: we never send the LLM the whole dataset — only a schema +
a small sample. This keeps prompts cheap and avoids leaking full data
into the LLM provider unnecessarily.
"""

import pandas as pd
import json


def load_file(uploaded_file) -> pd.DataFrame:
    """
    Load a Streamlit UploadedFile object into a DataFrame based on its
    extension.
    """
    name = uploaded_file.name.lower()

    if name.endswith(".csv"):
        return pd.read_csv(uploaded_file)

    elif name.endswith((".xlsx", ".xls")):
        return pd.read_excel(uploaded_file)

    elif name.endswith(".json"):
        # Try standard JSON first, fall back to lines-delimited JSON
        try:
            return pd.read_json(uploaded_file)
        except ValueError:
            uploaded_file.seek(0)
            return pd.read_json(uploaded_file, lines=True)

    else:
        raise ValueError(
            f"Unsupported file type: {name}. Please upload a .csv, .xlsx, or .json file."
        )


def build_schema_summary(df: pd.DataFrame, sample_rows: int = 3) -> str:
    """
    Build a compact text summary of a DataFrame's structure to send to the
    LLM: column names, dtypes, null counts, and a few sample rows.

    This is what lets the LLM write correct pandas code WITHOUT us ever
    sending the full dataset.
    """
    lines = []
    lines.append(f"Shape: {df.shape[0]} rows x {df.shape[1]} columns")
    lines.append("\nColumns (name : dtype : non-null count):")
    for col in df.columns:
        lines.append(f"  - {col} : {df[col].dtype} : {df[col].notna().sum()} non-null")

    lines.append(f"\nSample rows (first {sample_rows}):")
    lines.append(df.head(sample_rows).to_string())

    return "\n".join(lines)
