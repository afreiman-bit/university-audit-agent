import json
import os
from typing import Optional
from pydantic import BaseModel
from google import genai
from google.genai import types

client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])


class IntegrityResult(BaseModel):
    question_id: int
    passed: bool
    challenged_score: Optional[int]
    revised_score: Optional[int]
    revised_unclear_type: Optional[str]
    objection: Optional[str]
    evidence_verified: bool


PER_AGENT_PROMPT = """You are the Integrity Agent. Your job is NOT to be helpful.
Your job is to find what is WRONG with the scoring finding you are given.

SCORING AGENT'S FINDING:
Question {question_id}: {question_label}
Score: {score}
Unclear type: {unclear_type}
Finding: {finding}
Evidence: {evidence}

PAGE BODY TEXT (first 6000 chars):
---
{body_text}
---

YOUR CHECKS:
1. EVIDENCE VERIFICATION — find the exact quote in the body text. If not found verbatim, it was fabricated.
2. SCORE CONSISTENCY — score 2 with no verbatim evidence must be downgraded to 1.
3. SCORE INFLATION — did the agent round up from partial evidence?
4. UNCLEAR TYPE — if evidence is weak, should this be unclear: ambiguous_reference?

Respond ONLY with JSON — no markdown:
{{
  "passed": <true if valid, false if challenged>,
  "evidence_verified": <true | false>,
  "objection": "<specific objection, or null>",
  "revised_score": <revised score, or null if should become unclear>,
  "revised_unclear_type": <"ambiguous_reference" | "contradictory_signals" | null>
}}

Be skeptical. Not helpful."""


CROSS_FINDING_PROMPT = """You are the Integrity Agent checking for contradictions BETWEEN agents.

PAGE URL: {url}
ALL FINDINGS:
{findings_summary}

Look for inter-agent contradictions only:
- Fact extraction found no cost data but AEO Q1 scored 1 or 2
- PDFs detected but scores assume content is directly readable
- Technical issues that undermine content scores

Respond ONLY with JSON:
{{
  "contradictions_found": <true | false>,
  "flags": [
    {{
      "question_ids": [<affected IDs>],
      "description": "<contradiction>",
      "recommended_action": "<what to check>"
    }}
  ]
}}"""


async def check_finding(question_id, question_label, score, unclear_type, finding, evidence, body_text):
    prompt = PER_AGENT_PROMPT.format(
        question_id=question_id,
        question_label=question_label,
        score=score,
        unclear_type=unclear_type,
        finding=finding,
        evidence=evidence,
        body_text=body_text[:6000],
    )

    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.1, max_output_tokens=512),
        )
        raw = response.text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        data = json.loads(raw)

        passed = data.get("passed", True)
        return IntegrityResult(
            question_id=question_id,
            passed=passed,
            challenged_score=score,
            revised_score=data.get("revised_score", score) if not passed else score,
            revised_unclear_type=data.get("revised_unclear_type"),
            objection=data.get("objection"),
            evidence_verified=data.get("evidence_verified", True),
        )

    except Exception as e:
        return IntegrityResult(
            question_id=question_id,
            passed=True,
            challenged_score=score,
            revised_score=score,
            revised_unclear_type=None,
            objection=f"Integrity check error: {str(e)[:100]}",
            evidence_verified=False,
        )


async def cross_finding_check(url, all_findings):
    findings_summary = json.dumps(all_findings, indent=2)[:4000]
    prompt = CROSS_FINDING_PROMPT.format(url=url, findings_summary=findings_summary)

    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.1, max_output_tokens=1024),
        )
        raw = response.text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw)

    except Exception as e:
        return {"contradictions_found": False, "flags": [], "error": str(e)[:100]}
