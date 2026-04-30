from fastapi import FastAPI
from pydantic import BaseModel
import requests

app = FastAPI()

# ---------- Request Model ----------
class TranscriptInput(BaseModel):
    transcript: str


# ---------- Ollama Call ----------
def call_ollama(prompt: str):
    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": "llama3.2",   # change if needed
            "prompt": prompt,
            "stream": False
        }
    )
    return response.json()["response"]


# ---------- Basic Prompt ----------
def build_prompt(transcript: str):
    return f"""
You are an expert evaluator.

Analyze the following supervisor transcript and return JSON only.

Transcript:
{transcript}

Return JSON with:
- evidence (list of quotes with positive/negative/neutral)
- score (1-10)
- reasoning (short explanation)
- kpis (list)
- gaps (list)
- questions (list)

IMPORTANT:
- Do not add extra text
- Only return valid JSON
"""


# ---------- API Endpoint ----------
@app.post("/analyze")
def analyze(input: TranscriptInput):
    prompt = build_prompt(input.transcript)
    
    raw_output = call_ollama(prompt)

    return {
        "raw_output": raw_output
    }


# ---------- Run