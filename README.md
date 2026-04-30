# 🧠 Supervisor Feedback Analyzer (Trinethra Module)

This project converts raw supervisor feedback into structured performance analysis using a local LLM (Ollama).

---

## 🚀 What this project does

User provides a supervisor transcript (unstructured text).

The system:

1. Sends transcript to a local LLM (Ollama)
2. Extracts structured signals:
   - Evidence quotes
   - Behavioral indicators
3. Applies backend logic to:
   - Correct weak or misleading AI outputs
   - Enforce scoring rules
4. Returns structured JSON:
   - Score (1–10)
   - Reasoning
   - KPI mapping
   - Gaps
   - Follow-up questions

---

## 🧩 Problem Statement

Manual process today:

- Read transcript (10–15 min call)
- Extract evidence
- Decide score
- Identify gaps
- Write questions

⏱️ Takes **45–60 minutes per transcript**

Problems:
- Subjective
- Inconsistent scoring
- Slow
- Hard to scale

---

## 💡 Solution

Automate the pipeline:

- LLM handles **extraction**
- Backend handles **logic**
- Output is **structured + consistent**

---

## 🧠 Core Principle

> **AI extracts. Backend decides. Human reviews.**

LLM is **not trusted for scoring**  
All final decisions come from rule-based logic.

---

## 🏗️ Architecture


Transcript Input
↓
Ollama (LLM)
↓
Backend Logic (FastAPI)
↓
Structured JSON Output


---

## 🧱 Tech Stack

- **Backend:** FastAPI (Python)
- **LLM:** Ollama (Llama 3.2)
- **API:** REST
- **Parsing:** JSON + Regex fallback

---

## ⚙️ Setup Instructions

### 1. Install Ollama

Download:
https://ollama.com

Run:

```bash
ollama pull llama3.2

Test:

ollama run llama3.2 "Hello"
2. Setup Backend
cd backend
python -m venv venv
venv\Scripts\activate   # Windows
pip install -r requirements.txt
3. Run Server
cd backend
cd app
uvicorn main:app --reload

Server runs at:

http://127.0.0.1:8000
🔌 API Endpoint
POST /analyze
Request
{
  "transcript": "He comes on time and updates sheet daily..."
}
Response
{
  "evidence": [
    {
      "quote": "He comes on time",
      "type": "neutral"
    }
  ],
  "score": 5,
  "raw_score": 6,
  "correction_applied": true,
  "reasoning": "Task execution only. No system building.",
  "kpis": [],
  "gaps": [
    "No ownership",
    "No system building"
  ],
  "questions": [
    "What happens if he leaves?"
  ]
}
