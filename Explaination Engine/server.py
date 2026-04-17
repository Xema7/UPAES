from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import tempfile
import shutil
import traceback
from pathlib import Path
from extractor import load_log, get_purchase_events, extract_past_actions, save_output, detect_event_column, detect_timestamp_column
import pandas as pd
import httpx
import json

app = FastAPI(title="Purchase Action Extractor")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    traceback.print_exc()
    return JSONResponse(status_code=500, content={"detail": str(exc)})

session = {}

@app.on_event("startup")
async def warmup_model():
    try:
        from extractor import get_model
        print("Loading AI model (all-MiniLM-L6-v2)...")
        get_model()
        print("AI model loaded and ready.")
    except Exception as e:
        print(f"Model warmup skipped: {e}")


@app.post("/upload")
async def upload_log(file: UploadFile = File(...)):
    suffix = Path(file.filename).suffix.lower()
    if suffix != ".json":
        raise HTTPException(status_code=400, detail="Only .json files are supported.")

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    shutil.copyfileobj(file.file, tmp)
    tmp.close()

    try:
        df = load_log(tmp.name)
        purchases = get_purchase_events(df)

        if purchases.empty:
            raise HTTPException(status_code=404, detail="No purchase events found in log.")

        session["df"] = df
        session["filepath"] = tmp.name
        session["filename"] = file.filename

        purchase_list = []
        for _, row in purchases.iterrows():
            purchase_list.append({
                "row_index": int(row["_row_index"]),
                "timestamp": str(row["timestamp"]),
                "event": str(row["event"]),
            })

        return {
            "filename": file.filename,
            "total_events": len(df),
            "purchase_events": purchase_list,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class ExtractRequest(BaseModel):
    purchase_row_index: int
    timeframe: str  # "1_day" | "1_week" | "1_month"


@app.post("/extract")
def extract(req: ExtractRequest):
    if "df" not in session:
        raise HTTPException(status_code=400, detail="No log file uploaded. Upload a file first.")

    valid_timeframes = ["1_day", "1_week", "1_month"]
    if req.timeframe not in valid_timeframes:
        raise HTTPException(status_code=400, detail=f"Timeframe must be one of {valid_timeframes}")

    try:
        df = session["df"]
        past_actions = extract_past_actions(df, req.purchase_row_index, req.timeframe)

        if past_actions.empty:
            return {
                "count": 0,
                "message": "No actions found in the selected timeframe before this purchase.",
                "rows": [],
            }

        result_df = past_actions.copy()
        for col in result_df.columns:
            if pd.api.types.is_datetime64_any_dtype(result_df[col]):
                result_df[col] = result_df[col].dt.strftime("%Y-%m-%d %H:%M:%S UTC")

        rows = []
        for row in result_df.to_dict(orient="records"):
            clean_row = {}
            for k, v in row.items():
                if hasattr(v, "isoformat"):
                    clean_row[k] = v.isoformat()
                elif not isinstance(v, (list, dict)) and pd.isna(v):
                    clean_row[k] = None
                else:
                    clean_row[k] = v
            rows.append(clean_row)

        session["last_extracted"] = rows

        return {
            "count": len(rows),
            "rows": rows,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class GeminiRequest(BaseModel):
    api_key: str
    rows: list


@app.post("/analyse")
async def analyse_with_gemini(req: GeminiRequest):
    """Send extracted logs to Gemini API for human-like explanation and intent scoring."""
    if not req.api_key:
        raise HTTPException(status_code=400, detail="Gemini API key is required.")
    if not req.rows:
        raise HTTPException(status_code=400, detail="No rows to analyse.")

    logs_text = json.dumps(req.rows, indent=2, ensure_ascii=False)

    prompt = f"""
You are a behavioral analyst.

You are given a sequence of user activity events BEFORE a purchase.
Events are already relevant and sorted chronologically.
The LAST event is the purchase.

-------------------------
TASK
-------------------------

Analyze the user's behavior and return:

1. USER JOURNEY (human-like, simple)
   - Explain what the user did step-by-step - their journey, interests, and browsing behaviour
   - Include exploration → comparison → decision

2. INTENT TYPE
   - "marketing_driven" (ads, campaigns, external triggers)
   - "user_driven" (search, comparison, repeated evaluation)

3. INTENT SCORE (0–100)
   Base it on:
   - repeated product views
   - searches
   - dwell time / engagement
   - ad exposure

4. KEY EVENTS (VERY IMPORTANT)
   - Pick ONLY 3–5 most important events
   - MUST include reasoning (why it matters)
   - MUST reference actual behavior from logs

5. MOTIVATION
   - Explain WHY user purchased (clear, concrete)

-------------------------
STRICT RULES
-------------------------

- Do NOT skip any section
- Do NOT be generic
- Every key event MUST include a reason
- If data is weak, say so explicitly
- Keep explanation simple and human-like

-------------------------
OUTPUT FORMAT (STRICT JSON)
-------------------------

{{
  "narrative": "...",
  "intent_type": "...",
  "intent_score": 0,
  "key_events": [
    {{
      "event": "...",
      "impact": "..."
    }}
  ],
  "motivation_summary": "..."
}}

-------------------------
LOG EVENTS
-------------------------
{logs_text}
"""

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent?key={req.api_key}"

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(url, json={
                "contents": [{"parts": [{"text": prompt}]}]
            })

        if response.status_code != 200:
            detail = response.json().get("error", {}).get("message", response.text)
            raise HTTPException(status_code=response.status_code, detail=f"Gemini API error: {detail}")

        data = response.json()
        raw_text = data["candidates"][0]["content"]["parts"][0]["text"]

        clean = raw_text.strip()
        if clean.startswith("```"):
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
        clean = clean.strip().rstrip("```").strip()

        parsed = json.loads(clean)
        return parsed

    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Gemini returned invalid JSON. Try again.")
    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Network error contacting Gemini: {str(e)}")


# Serve UI
ui_path = Path(__file__).parent / "ui"
if ui_path.exists():
    app.mount("/", StaticFiles(directory=str(ui_path), html=True), name="ui")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)
