from fastapi import FastAPI
from pydantic import BaseModel
import requests

app = FastAPI()

class TranscriptInput(BaseModel):
    transcript: str


def call_ollama(prompt: str):
    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": "llama3.2",
            "prompt": prompt,
            "stream": False
        }
    )
    return response.json()["response"]


def build_prompt(transcript: str):
    return f"""
Analyze this supervisor transcript and return JSON.

Transcript:
{transcript}

Return JSON with:
- evidence
- score
- reasoning
- kpis
- gaps
- questions

ONLY return JSON.
"""


@app.post("/analyze")
def analyze(input: TranscriptInput):
    prompt = build_prompt(input.transcript)
    output = call_ollama(prompt)

    return {"result": output}