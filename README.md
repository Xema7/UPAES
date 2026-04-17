# 🧠 UPIAS — User Purchase Intent Analysis System

User Purchase Intent Analysis System is a **full-stack behavioral analytics system** that captures real user activity via a browser extension and transforms it into **AI-driven purchase intent insights**.

It combines:

* A **browser extension** for real-time behavioral tracking
* An **AI pipeline** that extracts decision journeys
* A **semantic model + LLM analysis** to explain *why* users purchase

---

## 🚀 What This Project Actually Does

User Purchase Intent Analysis System is not just a logger.

It is a **behavior → intent → explanation pipeline**:

```
User Activity → Structured Logs → Semantic Filtering → AI Analysis → Intent Score
```

It answers:

* What did the user do before purchasing?
* Which actions actually influenced the decision?
* Was the purchase **user-driven or marketing-driven?**
* What is the **intent score (0–100)?**

---

## 🧩 System Architecture

### 1. Browser Extension (Data Collection Layer)

Captures real-time behavioral signals across websites:

* Search queries
* Page visits
* Product views (Amazon, Flipkart, Myntra, etc.)
* Video interactions (play, pause, seek)
* Article reading (scroll-based inference)
* Ad clicks
* Purchase events

**Key Features**

* Structured event schema (analytics-grade)
* Dwell time + engagement tracking
* URL cleaning (removes trackers like utm, gclid)
* Session-based logging
* JSON export
* Auto-download logs

📄 Core files:

* `manifest.json` 
* `background.js` 
* `content.js` 

---

### 2. AI Processing Layer (Backend)

Processes logs and extracts **relevant actions before a purchase**.

📄 Core logic:

* `extractor.py` 

#### Pipeline:

1. Load logs (JSON)
2. Detect purchase events
3. Filter events within timeframe
4. Compute semantic similarity using:

   * `sentence-transformers (all-MiniLM-L6-v2)`
5. Keep only **relevant events**
6. Output structured journey

---

### 3. API + Analysis Layer

📄 Backend server:

* `server.py` 

#### Endpoints:

* `POST /upload`

  * Upload logs
  * Detect purchase events

* `POST /extract`

  * Extract relevant past actions
  * Timeframes: `1_day | 1_week | 1_month`

* `POST /analyse`

  * Sends extracted data to **Gemini**
  * Returns:

    * Human-like narrative
    * Intent type
    * Intent score
    * Key influencing events
    * Motivation summary

---

### 4. UI (Frontend Dashboard)

📄 Files:

* `index.html` 
* `styles.css` 

#### Features:

* Upload logs
* Select purchase event
* Choose timeframe
* View extracted actions (table)
* AI-powered explanation + intent score visualization

---

## 🔁 Data Flow

```
[Browser Extension]
        ↓
Structured JSON Logs
        ↓
[FastAPI Backend]
        ↓
Semantic Filtering (MiniLM)
        ↓
Relevant Events
        ↓
[Gemini LLM]
        ↓
Narrative + Intent Score
```

---

## 🧠 AI Logic (Core Innovation)

### Semantic Relevance Filtering

* Converts events → embeddings
* Computes cosine similarity with purchase context
* Filters noise using threshold (`0.25`)

This ensures:

> Only meaningful actions (not random browsing) are analyzed.

---

### Intent Classification

Gemini determines:

* **User-driven intent**

  * Searches
  * Comparisons
  * Repeated product views

* **Marketing-driven intent**

  * Ads
  * External triggers
  * sudden purchase

---

### Intent Score (0–100)

Based on:

* Frequency of interactions
* Engagement (scroll, dwell time)
* Repetition
* Ad influence

---

## ⚙️ Installation

### 1. Clone repo

```bash
git clone https://github.com/your-username/user-action-logger.git
cd user-action-logger
```

---

### 2. Backend Setup

```bash
pip install -r requirements.txt
```

📄 Requirements: 

Run server:

```bash
uvicorn server:app --reload
```

Server runs at:

```
http://127.0.0.1:8000
```

---

### 3. Load Browser Extension

1. Open Chrome
2. Go to `chrome://extensions`
3. Enable **Developer Mode**
4. Click **Load unpacked**
5. Select extension folder

---

## 📊 Usage

### Step 1 — Collect Data

* Browse normally
* Extension logs behavior automatically

### Step 2 — Export Logs

* Click extension popup → Export

### Step 3 — Upload Logs

* Open UI (`http://127.0.0.1:8000`)
* Upload `.json` log file

### Step 4 — Extract Journey

* Select purchase event
* Choose timeframe
* Click **Extract**

### Step 5 — Analyze Intent

* Click **Analyse Intent**
* Get:

  * Narrative
  * Intent type
  * Score
  * Key events

---

## 📁 Project Structure

```
UPIAS/
│
├── extension/
│   ├── manifest.json
│   ├── background.js
│   ├── content.js
│   ├── popup.html
│   ├── popup.js
│   └── popup.css
│
├── backend/
│   ├── server.py
│   ├── extractor.py
│   ├── requirements.txt
│
├── ui/
│   ├── index.html
│   ├── styles.css
│
└── README.md
```

---

## 🔐 Privacy Note

* All data is collected locally
* No automatic external transmission
* Logs are user-controlled and export-based

---

## ⚠️ Limitations

* Requires manual log upload
* Purchase detection depends on DOM patterns
* Semantic model may miss edge cases
* Gemini output depends on prompt quality

---

## 🚀 Future Improvements

* Real-time inference (no upload needed)
* On-device intent model (remove Gemini dependency)
* Multi-user analytics dashboard
* Stronger product/entity extraction
* Sequence modeling (RNN / Transformer)

---

## 💡 Use Cases

* Marketing analytics
* User behavior research
* Conversion funnel analysis
* E-commerce optimization
* AI-based personalization systems

---

## 🧑‍💻 Author

Built as a **behavioral AI system** combining:

* Browser instrumentation
* Semantic ML models
* LLM reasoning

---

## ⭐ Final Insight

This project demonstrates:

> How raw user activity can be transformed into **explainable AI-driven intent intelligence**.

---
