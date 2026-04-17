# Purchase Action Extractor

A fully local tool to extract past user actions leading up to a purchase event from structured log files.

---

## Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Start the server
```bash
python server.py
```

### 3. Open the UI
Visit: [http://localhost:8000](http://localhost:8000)

---

## How to use

1. **Upload** your `.json` log file
2. **Select** a purchase event from the list
3. **Choose a timeframe** — 1 Day, 1 Week, or 1 Month before the purchase
4. Click **Extract Past Actions**


---

## Log File Format

### JSON
Must be a list of event objects. Example:
```json
[
  { "timestamp": "2024-03-01T10:00:00Z", "event": "page_view", "user_id": "u123", "page": "/home" },
  { "timestamp": "2024-03-01T10:05:00Z", "event": "add_to_cart", "user_id": "u123", "product_id": "p456" },
  { "timestamp": "2024-03-01T10:10:00Z", "event": "purchase", "user_id": "u123", "order_id": "o789" }
]
```

**Auto-detected columns:**
- **Timestamp**: `timestamp`, `time`, `datetime`, `event_time`, `created_at`, `date`
- **Event**: `event`, `event_type`, `action`, `type`, `name`, `event_name`

---

## Project Structure

```
purchase-action-extractor/
├── server.py          ← FastAPI backend
├── extractor.py       ← Log parsing & filtering logic
├── requirements.txt
└── ui/
    └── index.html     ← Web UI
    └── style.css
```

---

## Timeframes

| Option | Looks back |
|--------|-----------|
| 1 Day  | 24 hours before purchase |
| 1 Week | 7 days before purchase |
| 1 Month | 30 days before purchase |
