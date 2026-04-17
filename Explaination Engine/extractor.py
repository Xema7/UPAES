import pandas as pd
import json
from datetime import timedelta
from pathlib import Path
import numpy as np

TIMEFRAME_DELTAS = {
    "1_day": timedelta(days=1),
    "1_week": timedelta(weeks=1),
    "1_month": timedelta(days=30),
}

FIELDS_TO_EXTRACT = [
    "event_type",
    "timestamp_local",
    "domain",
    "url",
    "referrer",
    "dwell_time_sec",
    "engagement",
    "event_properties",
]

TIMESTAMP_CANDIDATES = [
    "timestamp_local", "timestamp", "time", "datetime",
    "event_time", "created_at", "date"
]

EVENT_CANDIDATES = ["event_type", "event", "action", "type", "name", "event_name"]

# Relevance threshold — events scoring below this are excluded
SIMILARITY_THRESHOLD = 0.25

_model = None

def get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-10))


def build_purchase_context(row: pd.Series) -> str:
    """
    Build a rich semantic context string from the purchase event.
    Expands product name with related concepts using event_properties.
    """
    parts = []

    event_type = str(row.get("event_type", ""))
    parts.append(event_type)

    props = row.get("event_properties", {})
    if isinstance(props, dict):
        product = props.get("product_name") or props.get("product") or props.get("item", "")
        if product:
            parts.append(str(product))
        category = props.get("category") or props.get("product_category", "")
        if category:
            parts.append(str(category))
        brand = props.get("brand", "")
        if brand:
            parts.append(str(brand))

    domain = str(row.get("domain", ""))
    if domain:
        parts.append(domain)

    url = str(row.get("url", ""))
    if url:
        parts.append(url)

    context = " ".join(filter(None, parts))
    return context


def build_event_text(row: pd.Series) -> str:
    """
    Build a descriptive text for each candidate event so the model
    understands what the event is about semantically.
    """
    event_type = str(row.get("event_type", ""))
    domain = str(row.get("domain", ""))
    url = str(row.get("url", ""))
    parts = [event_type, domain]

    props = row.get("event_properties", {})
    if not isinstance(props, dict):
        try:
            props = json.loads(props) if props else {}
        except Exception:
            props = {}

    # Pull meaningful text from event_properties based on event type
    extractors = [
        "search_query", "query",
        "product_name", "product", "item",
        "video_title", "title",
        "article_title",
        "campaign", "ad_text",
        "category", "brand",
        "page_title",
    ]
    for key in extractors:
        val = props.get(key)
        if val:
            parts.append(str(val))

    # Also include URL path as it often contains product/topic info
    if url and url not in ("None", "nan"):
        parts.append(url)

    return " ".join(filter(lambda x: x and x not in ("None", "nan", ""), parts))


def load_log(filepath: str) -> pd.DataFrame:
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Log file not found: {filepath}")

    suffix = path.suffix.lower()
    if suffix == ".json":
        with open(path, "r", encoding="utf-8") as f:
            content = f.read().strip()
        try:
            raw = json.loads(content)
            if isinstance(raw, list):
                df = pd.DataFrame(raw)
            elif isinstance(raw, dict):
                df = pd.DataFrame([raw])
            else:
                raise ValueError("Unrecognised JSON structure.")
        except json.JSONDecodeError:
            try:
                lines = [l.strip() for l in content.splitlines() if l.strip()]
                records = [json.loads(l) for l in lines]
                df = pd.DataFrame(records)
            except Exception:
                raise ValueError("Could not parse JSON. Must be a JSON array or NDJSON.")
    else:
        raise ValueError("Unsupported format. Only .json files are supported.")

    ts_col = detect_timestamp_column(df)
    df["_parsed_ts"] = pd.to_datetime(df[ts_col], utc=True, errors="coerce")
    df = df.dropna(subset=["_parsed_ts"])
    df = df.sort_values("_parsed_ts").reset_index(drop=True)
    df["_ts_col"] = ts_col
    return df


def detect_timestamp_column(df: pd.DataFrame) -> str:
    for col in TIMESTAMP_CANDIDATES:
        if col in df.columns:
            return col
    for col in df.columns:
        try:
            pd.to_datetime(df[col], utc=True, errors="raise")
            return col
        except Exception:
            continue
    raise ValueError("No timestamp column found in log file.")


def detect_event_column(df: pd.DataFrame) -> str:
    for col in EVENT_CANDIDATES:
        if col in df.columns:
            return col
    raise ValueError("No event/action column found in log file.")


def get_purchase_label(row: pd.Series, event_col: str) -> str:
    event_name = str(row.get(event_col, "purchase"))
    props = row.get("event_properties", {})
    if isinstance(props, dict):
        product = props.get("product_name") or props.get("product") or props.get("item")
        if product:
            return f"{event_name} — {product}"
    return event_name


def get_purchase_events(df: pd.DataFrame) -> pd.DataFrame:
    event_col = detect_event_column(df)
    purchase_keywords = ["purchase", "buy", "checkout", "order", "payment", "paid", "bought"]
    mask = df[event_col].str.lower().str.contains("|".join(purchase_keywords), na=False)
    purchases = df[mask].copy()

    result = []
    for idx, row in purchases.iterrows():
        ts_col = row["_ts_col"]
        raw_ts = str(row[ts_col])
        result.append({
            "_row_index": idx,  
            "timestamp": raw_ts,
            "event": get_purchase_label(row, event_col),
        })

    return pd.DataFrame(result)


def extract_past_actions(df: pd.DataFrame, purchase_row_index: int, timeframe_key: str) -> pd.DataFrame:
    """
    Step 1: Filter events in the timeframe window before the purchase.
    Step 2: Use sentence-transformers to score each event's semantic
            relevance to the purchased product.
    Step 3: Return only events above the similarity threshold,
            sorted by time, with the purchase appended at the end.
    """
    delta = TIMEFRAME_DELTAS.get(timeframe_key)
    if delta is None:
        raise ValueError(f"Invalid timeframe: {timeframe_key}")

    purchase_row = df.loc[purchase_row_index]
    purchase_time = purchase_row["_parsed_ts"]
    window_start = purchase_time - delta

    # Step 1 — timeframe filter
    candidates = df[
        (df["_parsed_ts"] >= window_start) &
        (df["_parsed_ts"] < purchase_time)
    ].copy()

    if candidates.empty:
        # Still append purchase row and return
        result = df.loc[[purchase_row_index]].copy()
        result = result.drop(columns=["_parsed_ts", "_ts_col"], errors="ignore")
        available = [f for f in FIELDS_TO_EXTRACT if f in result.columns]
        return result[available].reset_index(drop=True)

    # Step 2 — semantic relevance scoring
    model = get_model()

    purchase_context = build_purchase_context(purchase_row)
    purchase_embedding = model.encode(purchase_context, convert_to_numpy=True)

    event_texts = candidates.apply(build_event_text, axis=1).tolist()
    event_embeddings = model.encode(event_texts, convert_to_numpy=True, batch_size=32, show_progress_bar=False)

    scores = [cosine_similarity(purchase_embedding, e) for e in event_embeddings]
    candidates = candidates.copy()
    candidates["_similarity"] = scores

    # Step 3 — keep only relevant events
    related = candidates[candidates["_similarity"] >= SIMILARITY_THRESHOLD].copy()
    related = related.sort_values("_parsed_ts")

    # Append the purchase event at the end
    purchase_df = df.loc[[purchase_row_index]].copy()
    purchase_df["_similarity"] = 1.0
    result = pd.concat([related, purchase_df], ignore_index=True)

    # Drop internal columns
    result = result.drop(columns=["_parsed_ts", "_ts_col", "_similarity"], errors="ignore")

    available = [f for f in FIELDS_TO_EXTRACT if f in result.columns]
    if available:
        result = result[available]

    return result.reset_index(drop=True)


def save_output(df: pd.DataFrame, output_path: str, fmt: str = "json"):
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "json":
        records = json.loads(df.to_json(orient="records", date_format="iso", force_ascii=False))
        with open(path, "w", encoding="utf-8") as f:
            for record in records:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
    elif fmt == "csv":
        df.to_csv(path, index=False)
    else:
        raise ValueError("Output format must be 'json' or 'csv'")
    return str(path)
