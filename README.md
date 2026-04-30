# Project README
# Project README
# 🧠 Supervisor Feedback Analyzer (Trinethra Module)

## 🚀 Overview

This project is a backend system that converts raw supervisor feedback (unstructured text) into a structured performance evaluation using a local LLM (Ollama).

The system is designed to **assist (not replace)** human judgment by generating a draft analysis that a psychology intern can review and refine.

---

## 🧩 Problem Statement

Currently, supervisor feedback is processed manually:

- Intern reads transcript (10–15 min call)
- Extracts behavioral evidence
- Maps to a performance rubric (1–10)
- Identifies gaps
- Writes follow-up questions

⏱️ This takes **45–60 minutes per transcript**

---

## 💡 Solution

This system reduces that time by:

1. Using a local LLM (Ollama) to extract raw signals from the transcript
2. Applying deterministic backend logic to:
   - Clean and validate AI output
   - Enforce scoring rules
   - Prevent hallucinations
3. Returning a structured JSON output ready for human review

---

## 🧠 Key Design Principle

> **AI suggests. System decides. Human reviews.**

The LLM is **not trusted for final decisions**.  
All scoring and logic are enforced using rule-based corrections.

---

## ⚙️ Tech Stack

- **Backend:** FastAPI (Python)
- **LLM:** Ollama (Llama 3.2)
- **Communication:** REST API (HTTP)
- **Parsing & Validation:** JSON + Regex fallback

---

## 🏗️ System Architecture
Transcript Input
↓
Ollama (raw extraction only)
↓
Backend Rule Engine (deterministic logic)
↓
Structured JSON Output
↓
Frontend / User Review

---

## 🔌 API Endpoint

### POST `/analyze`

### Request
```json
{
  "transcript": "Supervisor feedback text..."
}
Response
{
  "evidence": [
    { "quote": "...", "type": "neutral" }
  ],
  "score": 5,
  "raw_score": 6,
  "correction_applied": true,
  "reasoning": "...",
  "kpis": [...],
  "gaps": [...],
  "questions": [...]
}
