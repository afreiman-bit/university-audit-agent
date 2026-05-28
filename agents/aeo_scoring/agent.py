import json
import os
from typing import Optional
from pydantic import BaseModel
from google import genai
from google.genai import types
from config.aeo_rubric import AEO_QUESTIONS, AEO_CRITERIA, UNCLEAR_TYPES

# Uses Application Default Credentials — no API key needed
client = genai.Client()


class QuestionScore(BaseModel):
    question_id: int
    question_label: str
    score: Optional[int]
    unclear_type: Optional[str]
    finding: str
    evidence: Optional[str]
    staleness_flag: bool
    multi_program_flag: bool
    recommendation: Optional[str]


def build_scoring_prompt(question_id, question_label, criteria, body_text, extracted_facts):
    facts_summary = json.dumps(extracted_facts, indent=2)
    return f"""You are evaluating a university program page for AI discoverability.

Score this page on ONE question a prospective student would ask an AI assistant.

QUESTION {question_id}: {question_label}

SCORING RUBRIC:
- Score 2: {criteria[2]}
- Score 1: {criteria[1]}
- Score 0: {criteria[0]}

UNCLEAR STATES:
- unclear: extraction_failure — {UNCLEAR_TYPES['extraction_failure']}
- unclear: content_behind_barrier — {UNCLEAR_TYPES['content_behind_barrier']}
- unclear: ambiguous_reference — {UNCLEAR_TYPES['ambiguous_reference']}
- unclear: contradictory_signals — {UNCLEAR_TYPES['contradictory_signals']}

EXTRACTED FACTS:
{facts_summary}

PAGE BODY TEXT:
---
{body_text[:6000]}
---

RULES:
1. Evidence must be verbatim text from the page. Never invent evidence.
2. Score 2 requires explicit extractable information — not linked or implied.
3. Flag staleness if salary data references a year more than 2 years ago.
4. Flag multi_program if page covers more than one distinct degree program.
5. Recommendation must be specific, not generic.

Respond ONLY with JSON — no markdown:
{{
  "score": <0, 1, 2, or null>,
  "unclear_type": <"extraction_failure" | "content_behind_barrier" | "ambiguous_reference" | "contradictory_signals" | null>,
  "finding": "<one sentence>",
  "evidence": "<verbatim quote under 120 chars, or null>",
  "staleness_flag": <true | false>,
  "multi_program_flag": <true | false>,
  "recommendation": "<specific fix, or null if score is 2>"
}}"""


async def score_page(url, body_text, extracted_facts, question_ids=None):
    if question_ids is None:
        question_ids = list(AEO_QUESTIONS.keys())

    results = []

    for qid in question_ids:
        question_label = AEO_QUESTIONS[qid]
        criteria = AEO_CRITERIA[qid]
        prompt = build_scoring_prompt(qid, question_label, criteria, body_text, extracted_facts)

        try:
            response = client.models.generate_content(
                model="models/gemini-2.0-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.1,
                    max_output_tokens=512,
                ),
            )
            raw = response.text.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            data = json.loads(raw)

            results.append(QuestionScore(
                question_id=qid,
                question_label=question_label,
                score=data.get("score"),
                unclear_type=data.get("unclear_type"),
                finding=data.get("finding", ""),
                evidence=data.get("evidence"),
                staleness_flag=data.get("staleness_flag", False),
                multi_program_flag=data.get("multi_program_flag", False),
                recommendation=data.get("recommendation"),
            ))

        except Exception as e:
            results.append(QuestionScore(
                question_id=qid,
                question_label=question_label,
                score=None,
                unclear_type="extraction_failure",
                finding=f"Scoring error: {str(e)[:100]}",
                evidence=None,
                staleness_flag=False,
                multi_program_flag=False,
                recommendation=None,
            ))

    return results
