
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
import json
import re

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- Input ----------
class TranscriptInput(BaseModel):
    transcript: str


# ---------- Ollama Call ----------
def call_ollama(prompt: str) -> str:
    print("\n================ PROMPT ================\n")
    print(prompt)

    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": "llama3.2",
            "prompt": prompt,
            "stream": False
        }
    )

    result = response.json()["response"]

    print("\n================ RAW OUTPUT ================\n")
    print(result)

    return result


# ---------- Robust JSON Parser ----------
def safe_parse(output: str):
    cleaned = output.strip()

    if cleaned.startswith("```"):
        parts = cleaned.split("```")
        for part in parts:
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            if part.startswith("{") or part.startswith("["):
                cleaned = part
                break

    try:
        return json.loads(cleaned)
    except Exception:
        pass

    match = re.search(r'(\{[\s\S]*\}|\[[\s\S]*\])', cleaned)
    if match:
        try:
            return json.loads(match.group(1))
        except Exception:
            pass

    print("\n❌ JSON PARSE FAILED")
    print("Raw output:", output)
    return None


# ---------- Ollama Call with Retry ----------
def call_ollama_with_retry(prompt: str, retries: int = 2):
    for attempt in range(retries + 1):
        raw = call_ollama(prompt)
        parsed = safe_parse(raw)
        if parsed is not None:
            return parsed
        print(f"\n⚠️ Attempt {attempt + 1} failed. Retrying...\n")
    return None


# ---------- Evidence Type Rules ----------
NEUTRAL_PHRASES = [
    "comes on time", "on time", "punctual", "shows up",
    "attends meetings", "is available", "is present",
    "helps manager", "assists manager", "supports manager",
    "follows instructions", "does what is asked",
    "responds to", "replies on time",
    "updates sheet", "updates the sheet", "fills sheet",
    "updates tracker", "updates the tracker",
]

POSITIVE_PHRASES = [
    "takes ownership", "identified", "solved", "improved",
    "created", "built", "documented", "trained", "automated",
    "without being asked", "proactively", "independently",
    "handles escalations", "resolves", "closes loop",
    "manages end to end", "drives",
]

NEGATIVE_PHRASES = [
    "missed deadline", "late submission", "made an error",
    "did not complete", "incomplete", "failed to",
    "confusion", "conflict", "complaint", "escalated",
    "doesn't take ownership", "avoids", "dependent on manager",
    "needs constant", "inconsistent", "sloppy", "careless"
]


def correct_evidence_type(quote: str) -> str | None:
    q = quote.lower()
    # Negative = actual performance failure (missed deadline, error, complaint)
    if any(sig in q for sig in NEGATIVE_PHRASES):
        return "negative"
    # Task absorption = neutral risk signal, not a failure
    # Fellow is taking on manager work — not bad execution, but not system building
    if any(sig in q for sig in TASK_ABSORPTION_SIGNALS):
        return "neutral"
    if any(sig in q for sig in POSITIVE_PHRASES):
        return "positive"
    if any(sig in q for sig in NEUTRAL_PHRASES):
        return "neutral"
    return None


# ---------- STEP 1: Evidence ----------
def get_evidence(transcript: str):
    prompt = f"""You MUST return valid JSON only. No explanation. No markdown. No extra text.

Extract behavioral evidence from this supervisor transcript.

Transcript:
{transcript}

Return EXACTLY this JSON format:
{{
  "evidence": [
    {{
      "quote": "exact or paraphrased text from transcript",
      "type": "positive"
    }}
  ]
}}

Rules:
- Minimum 3 items, maximum 10
- Allowed types: positive, negative, neutral
- neutral  = shows up, follows instructions, routine compliance
- positive = ownership, initiative, building, resolving, independent output
- negative = missed deadlines, errors, complaints, inconsistency
- Focus on behaviors, not personality
"""

    parsed = call_ollama_with_retry(prompt)

    if not parsed:
        print("❌ Evidence extraction failed: no valid JSON")
        return None

    if isinstance(parsed, list):
        print("⚠️ Ollama returned bare array — wrapping")
        parsed = {"evidence": parsed}

    if "evidence" not in parsed:
        print("❌ Evidence extraction failed: missing 'evidence' key")
        return None

    evidence = parsed["evidence"]

    for item in evidence:
        corrected = correct_evidence_type(item.get("quote", ""))
        if corrected is not None and corrected != item.get("type"):
            print(f"⚠️ Type corrected: '{item['quote']}' {item['type']} → {corrected}")
            item["type"] = corrected

    return evidence


# ---------- STEP 2: Score + Layer Classification ----------

EXECUTION_SIGNALS = [
    "comes on time", "on time", "punctual",
    "sends updates", "gives updates", "updates sheet", "updates tracker",
    "helps manager", "assists manager", "supports manager",
    "follows instructions", "does what is asked", "completes tasks",
    "attends meetings", "responsive", "available"
]

SYSTEM_SIGNALS = [
    # Explicit process/doc language
    "built a system", "created a process", "documented",
    "trained others", "onboarded", "delegation",
    "runs without", "works independently", "team can",
    "scaled", "automated", "framework", "standard operating",
    "sop", "playbook", "knowledge transfer",
    # Improvement & analysis language — Fellow is thinking, not just executing
    "suggested", "proposed", "recommended", "study on", "did a study",
    "cycle time", "layout", "set up", "redesigned", "optimised", "optimized",
    "moved the", "rearranged", "improved the", "reduced", "saved",
    "from the beginning", "involved from", "helped set up",
    "identified a", "spotted", "analysed", "analyzed",
    "efficiency", "bottleneck", "root cause",
]

SURVIVABILITY_SIGNALS = [
    "team can handle", "others can continue", "documented process",
    "trained the team", "independent of", "not dependent on",
    "continues without", "self-sustaining", "hand off"
]

NEGATIVE_PERFORMANCE_SIGNALS = [
    "missed deadline", "late submission", "error", "incomplete",
    "failed to", "complaint", "escalated", "inconsistent",
    "careless", "sloppy", "needs constant supervision"
]

# Task absorption: Fellow is taking manager's work personally,
# increasing dependency rather than distributing capability.
# Covers: coordination, escalation handling, call-taking, first-response.
TASK_ABSORPTION_SIGNALS = [
    "helps manager", "assists manager", "supports manager",
    "takes over", "handles manager", "does manager",
    "manager's calls", "manager's tasks", "manager's work",
    "handles a lot of the coordination", "handles coordination",
    "takes the first call", "takes first call", "first point of contact",
    "takes the call", "handles the call", "handles calls",
    "handles escalation", "handles complaint", "handles quality",
    "coordinates everything", "manages coordination",
]


def classify_layer(evidence: list) -> dict:
    """
    Layer 1: Task execution — Fellow does assigned work. Work stops if they leave.
    Layer 2: System building — Fellow creates processes. Work continues without them.
    """
    evidence_text = " ".join([e["quote"].lower() for e in evidence])

    has_system        = any(sig in evidence_text for sig in SYSTEM_SIGNALS)
    has_survivability = any(sig in evidence_text for sig in SURVIVABILITY_SIGNALS)
    has_absorption    = any(sig in evidence_text for sig in TASK_ABSORPTION_SIGNALS)

    if has_survivability:
        layer = 2
        label = "System Builder"
        description = "Work would continue without this Fellow. Processes or knowledge exist independently."
    elif has_system and has_absorption:
        layer = 2
        label = "Emerging System Builder"
        description = (
            "Fellow shows both system-building and task absorption. "
            "Process thinking is present, but work is not yet self-sustaining. "
            "Risk: absorption pattern may undercut the systems being built."
        )
    elif has_system:
        layer = 2
        label = "Emerging System Builder"
        description = "Fellow is building systems but survivability is not yet confirmed."
    elif has_absorption:
        layer = 1
        label = "Task Absorber"
        description = (
            "Fellow is taking on manager's operational load personally. "
            "This reduces the manager's burden but increases dependency on the Fellow — "
            "the opposite of system building."
        )
    else:
        layer = 1
        label = "Task Executor"
        description = "Fellow completes assigned work reliably. No evidence of building beyond the task."

    return {"layer": layer, "label": label, "description": description}


def apply_score_correction(score: int, evidence: list) -> tuple[int, str]:
    evidence_text = " ".join([e["quote"].lower() for e in evidence])

    has_execution     = any(sig in evidence_text for sig in EXECUTION_SIGNALS)
    has_system        = any(sig in evidence_text for sig in SYSTEM_SIGNALS)
    has_survivability = any(sig in evidence_text for sig in SURVIVABILITY_SIGNALS)
    has_negative      = any(sig in evidence_text for sig in NEGATIVE_PERFORMANCE_SIGNALS)
    correction_note   = ""

    if has_survivability:
        if score < 8:
            score = 8
            correction_note = "raised to 8: survivability confirmed"
        return score, correction_note

    if has_system and not has_survivability:
        score = max(min(score, 7), 6)
        correction_note = "bounded 6–7: system building present, survivability not confirmed"
        return score, correction_note

    if has_execution and has_negative and not has_system:
        score = min(score, 4)
        correction_note = "capped at 4: execution with negative performance signals"
        return score, correction_note

    if has_execution and not has_system and not has_survivability and not has_negative:
        score = 5
        correction_note = "set to 5: consistent execution only"
        return score, correction_note

    if not has_system and not has_survivability and score > 6:
        score = 6
        correction_note = "capped at 6: AI over-scored — no system or survivability evidence"

    return score, correction_note


def build_reasoning(score: int, raw_score: int, evidence: list, layer_info: dict) -> str:
    evidence_text = " ".join([e["quote"].lower() for e in evidence])

    has_system        = any(sig in evidence_text for sig in SYSTEM_SIGNALS)
    has_survivability = any(sig in evidence_text for sig in SURVIVABILITY_SIGNALS)
    has_negative      = any(sig in evidence_text for sig in NEGATIVE_PERFORMANCE_SIGNALS)
    has_absorption    = any(sig in evidence_text for sig in TASK_ABSORPTION_SIGNALS)
    has_scale         = any(sig in evidence_text for sig in SYSTEM_SIGNALS + SURVIVABILITY_SIGNALS)

    parts = []

    # Paragraph 1: What is observed — factual summary, not a raw quote dump
    n_positive  = len([e for e in evidence if e["type"] == "positive"])
    n_neutral   = len([e for e in evidence if e["type"] == "neutral"])
    n_negative  = len([e for e in evidence if e["type"] == "negative"])

    behavior_summary = []
    if n_positive > 0:
        behavior_summary.append(f"{n_positive} positive contribution{'s' if n_positive > 1 else ''}")
    if n_neutral > 0:
        behavior_summary.append(f"{n_neutral} neutral/routine behavior{'s' if n_neutral > 1 else ''}")
    if n_negative > 0:
        behavior_summary.append(f"{n_negative} negative signal{'s' if n_negative > 1 else ''}")

    parts.append(
        f"The supervisor described {', '.join(behavior_summary)}. "
        f"All observed work is execution within a manager-defined scope."
    )

    # Paragraph 2: Causal diagnostic — system signals take priority over absorption
    if has_system and has_absorption:
        parts.append(
            "The Fellow shows a mixed pattern: there is evidence of process thinking "
            "(analysis, layout improvements, cycle time studies) alongside task absorption "
            "(handling calls, coordination). "
            "The system-building signals are real, but the work is not yet self-sustaining — "
            "documentation and delegation are not confirmed."
        )
    elif has_system and not has_survivability:
        parts.append(
            "The Fellow has moved beyond task execution into process thinking — "
            "identifying improvements, suggesting structural changes, and contributing to setup decisions. "
            "However, it is unclear whether this work would continue without them. "
            "System building is present but not yet confirmed as self-sustaining."
        )
    elif has_system and has_survivability:
        parts.append(
            "The Fellow has built systems that appear to operate independently. "
            "There is evidence of scalability and continuity beyond individual effort."
        )
    elif has_absorption and not has_system:
        parts.append(
            "Activities like updating sheets and handling calls provide short-term visibility and responsiveness, "
            "but are not converted into systems or processes. "
            "Tasks like handling calls shift workload from the manager to the Fellow "
            "rather than eliminating or systemizing the need — this increases dependency risk, not operational resilience. "
            "The operation remains person-dependent and does not scale."
        )
    else:
        parts.append(
            "There is no evidence of documentation, delegation, or process design. "
            "The work is person-dependent — it exists because the Fellow is present, "
            "not because a system supports it. The operation does not scale."
        )

    # Paragraph 3: Survivability — direct verdict, no hedging
    if has_survivability:
        parts.append(
            "Survivability is confirmed — there is evidence the work would continue without this Fellow."
        )
    elif has_system:
        parts.append(
            "Survivability is unconfirmed — systems exist, but the supervisor gave no indication "
            "the team could operate independently without this Fellow."
        )
    else:
        parts.append(
            "Evidence suggests the work would not continue without the Fellow. "
            "There is no delegation, no documentation, and no sign the Fellow is thinking about scale. "
            "This is the primary ceiling on the score."
        )

    if has_negative:
        parts.append("There are also performance concerns that further constrain the score.")

    # Paragraph 4: Score verdict — operator language, causally grounded
    if score == 5:
        parts.append(
            "Score: 5. Reliable executor, but entirely within a manager-defined scope. "
            "No system building, no scalability, no evidence of value that outlasts individual effort."
        )
    elif score == 4:
        parts.append(
            "Score: 4. Present and active, but performance signals indicate inconsistency "
            "or dependency on supervision. Execution is not yet reliable."
        )
    elif score == 6:
        parts.append(
            "Score: 6. Works independently without direction, but has not built anything "
            "reusable or transferable. Output stops when the Fellow stops."
        )
    elif score >= 7:
        parts.append(
            f"Score: {score}. System-level contributor — evidence of processes, documentation, "
            f"or knowledge transfer that creates value beyond individual effort."
        )

    if raw_score != score:
        parts.append(f"(AI suggested {raw_score}/10 — overridden by scoring logic.)")

    return " ".join(parts)


def get_score(evidence: list):
    prompt = f"""You MUST return valid JSON only. No explanation. No markdown. No extra text.

Score this Fellow's performance from 1 to 10.

Evidence:
{json.dumps(evidence, indent=2)}

Rubric:
- 4: Present but inconsistent — needs supervision, performance gaps
- 5: Consistent execution — shows up, does the work reliably, no gaps
- 6: Independent — works without direction, proactive
- 7-8: System builder — created processes, trained others, documented
- 9-10: Transformational — work continues and scales after they leave

Important: Score 5 = reliable, not weak. Score 4 = inconsistent, not just basic.

Return ONLY this:
{{"score": 5}}
"""

    parsed = call_ollama_with_retry(prompt)

    if not parsed:
        print("❌ Scoring failed")
        return None

    raw_score = int(parsed.get("score", 5))
    raw_score = max(1, min(10, raw_score))

    corrected_score, correction_note = apply_score_correction(raw_score, evidence)
    layer_info = classify_layer(evidence)
    reasoning  = build_reasoning(corrected_score, raw_score, evidence, layer_info)

    return {
        "score": corrected_score,
        "raw_score": raw_score,
        "layer": layer_info,
        "reasoning": reasoning,
        "correction_applied": bool(correction_note)
    }


# ---------- STEP 3: KPI Mapping ----------
# Logic: map behavior → business impact → KPI
# Not keyword match — causal chain

KPI_RULES = [
    {
        "kpi": "Turnaround Time (TAT)",
        "triggers": [
            "updates sheet", "updates tracker", "updates daily", "fills sheet",
            "tracks", "deadline", "turnaround", "delivery", "submitted on time",
            "delivered on time", "late submission", "speed", "delay"
        ],
        "impact": "Improves short-term visibility into progress and accelerates decision-making. Risk: this visibility is person-dependent — if the Fellow is absent, tracking stops and delays follow."
    },
    {
        "kpi": "Customer Satisfaction (NPS)",
        "triggers": [
            "helps manager with calls", "assists with calls", "handles calls",
            "client", "customer", "satisfaction", "complaint", "nps",
            "rating", "experience", "support calls", "call handling"
        ],
        "impact": "Improves response time in the short term. Risk: this creates dependency — long-term consistency depends on the Fellow remaining available, not on a system that handles calls reliably."
    },
    {
        "kpi": "Quality",
        "triggers": [
            "quality", "accurate", "error", "mistake", "correct",
            "standard", "review", "rework", "precision", "checks"
        ],
        "impact": "Attention to accuracy and review behavior directly reduces rework and error rates."
    },
    {
        "kpi": "Team Productivity",
        "triggers": [
            "trained", "onboard", "delegation", "team can",
            "knowledge transfer", "collaboration", "efficiency"
        ],
        "impact": "Knowledge transfer and training multiplies team output beyond the Fellow's individual contribution."
    },
    {
        "kpi": "Process & Systems",
        "triggers": [
            "process", "system", "documented", "sop", "framework",
            "playbook", "automated", "standardized", "scalable"
        ],
        "impact": "Building reusable processes reduces reliance on individual effort and enables scale."
    }
]


def map_kpis(evidence: list) -> list:
    kpi_map = {}
    for item in evidence:
        quote_lower = item["quote"].lower()
        for rule in KPI_RULES:
            if any(trigger in quote_lower for trigger in rule["triggers"]):
                kpi = rule["kpi"]
                if kpi not in kpi_map:
                    kpi_map[kpi] = {"evidence": [], "impact": rule["impact"]}
                if item["quote"] not in kpi_map[kpi]["evidence"]:
                    kpi_map[kpi]["evidence"].append(item["quote"])

    return [
        {"kpi": kpi, "evidence": data["evidence"], "impact": data["impact"]}
        for kpi, data in kpi_map.items()
    ]


# ---------- STEP 4: Gaps + Questions ----------

CORE_DIMENSIONS = [
    {
        "name": "ownership",
        "signals": ["ownership", "owns", "responsible for", "accountable"],
        "gap": "No evidence of ownership — the supervisor describes task completion, not outcome responsibility.",
    },
    {
        "name": "independence",
        "signals": ["independent", "without supervision", "without being asked", "on their own"],
        "gap": "Independence is unclear — it is unknown whether the Fellow works without direction or requires ongoing guidance.",
    },
    {
        "name": "initiative",
        "signals": ["proactive", "initiative", "flagged", "identified a problem", "suggested", "without being asked"],
        "gap": "No mention of initiative — there is no evidence the Fellow acts before being prompted.",
    },
    {
        "name": "system building",
        "signals": ["documented", "process", "system", "sop", "playbook", "trained", "framework"],
        "gap": "No system building detected — the Fellow is executing tasks personally with no documentation, delegation, or reusable output.",
    },
    {
        "name": "survivability",
        "signals": ["team can", "continues without", "others can", "hand off", "not dependent", "trained the team"],
        "gap": "Survivability not addressed — there is no indication work would continue if this Fellow were absent.",
    },
    {
        "name": "change management",
        "signals": ["team", "adoption", "change", "influenced", "how others", "response", "buy-in"],
        "gap": "Change management is not addressed — no information on how the Fellow works with or influences the team around them.",
    },
]

SURVIVABILITY_QUESTION = "If this Fellow were absent for two weeks, what would break or stop?"


def get_gaps_and_questions(evidence: list):
    prompt = f"""You MUST return valid JSON only. No explanation. No markdown. No extra text.

Based on the evidence below, identify what is MISSING and write targeted follow-up questions for the next supervisor call.

Evidence:
{json.dumps(evidence, indent=2)}

Evaluate these five dimensions. Flag each one that is absent or unclear:
1. Ownership — does the Fellow take responsibility for outcomes, not just tasks?
2. Independence — do they work without needing direction?
3. Initiative — do they identify and act on problems before being asked?
4. System building — have they created anything documented or reusable?
5. Change management — how does the Fellow influence or work with the team?

Return EXACTLY this JSON format:
{{
  "gaps": [
    "No evidence of ownership — supervisor only describes task completion",
    "Initiative is not mentioned — unclear if Fellow acts without being prompted",
    "No documentation or systems mentioned — work appears person-dependent",
    "Change management is not addressed — no information on team influence or adoption"
  ],
  "questions": [
    "If this Fellow were absent for two weeks, what would break or stop?",
    "Has the Fellow ever flagged a problem or suggested a change without being asked?",
    "What has this Fellow built or documented that the team could use without them?",
    "Does the supervisor feel the Fellow owns the outcome, or just the task?",
    "How does the rest of the team respond to or depend on this Fellow's work?"
  ]
}}

Rules:
- Return 3–5 gaps — only for dimensions genuinely absent from the evidence
- Return exactly 4–5 questions — sharp, specific, usable in a real call
- The survivability question is mandatory
"""

    parsed = call_ollama_with_retry(prompt)

    if not parsed:
        print("❌ Gap analysis failed")
        return None

    gaps      = parsed.get("gaps", [])
    questions = parsed.get("questions", [])

    # Safety net: enforce all five core dimensions
    evidence_text = " ".join([e["quote"].lower() for e in evidence])
    for dim in CORE_DIMENSIONS:
        dimension_present = any(sig in evidence_text for sig in dim["signals"])
        already_in_gaps   = any(dim["name"] in g.lower() for g in gaps)
        if not dimension_present and not already_in_gaps:
            gaps.append(dim["gap"])

    # Survivability question is non-negotiable
    has_survivability_q = any(
        kw in q.lower() for q in questions
        for kw in ["absent", "leave", "without", "stop", "break"]
    )
    if not has_survivability_q:
        questions.insert(0, SURVIVABILITY_QUESTION)

    # System adoption question — tests whether systems actually exist in use
    ADOPTION_QUESTION = "Has the Fellow created anything that someone else is currently using without their involvement?"
    has_adoption_q = any("using" in q.lower() or "adoption" in q.lower() or "without their" in q.lower() for q in questions)
    if not has_adoption_q and len(questions) < 5:
        questions.append(ADOPTION_QUESTION)

    gaps      = gaps[:5]
    questions = questions[:5]

    return {"gaps": gaps, "questions": questions}


# ---------- FINAL API ----------
@app.post("/analyze")
def analyze(input: TranscriptInput):
    transcript = input.transcript.strip()

    if not transcript:
        return {"error": "Transcript is empty"}

    evidence = get_evidence(transcript)
    if not evidence:
        return {"error": "Evidence extraction failed", "hint": "Check terminal logs"}

    score_data = get_score(evidence)
    if not score_data:
        return {"error": "Scoring failed", "hint": "Check terminal logs"}

    kpis = map_kpis(evidence)

    gaps_data = get_gaps_and_questions(evidence)
    if not gaps_data:
        return {"error": "Gap analysis failed", "hint": "Check terminal logs"}

    return {
        "evidence": evidence,
        "score": score_data["score"],
        "raw_score": score_data["raw_score"],
        "layer": score_data["layer"],
        "correction_applied": score_data["correction_applied"],
        "reasoning": score_data["reasoning"],
        "kpis": kpis,
        "gaps": gaps_data["gaps"],
        "questions": gaps_data["questions"]
    }