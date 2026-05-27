import os
import httpx
import uuid
from config.aeo_rubric import severity_from_score

ENDPOINT = os.environ.get(
    "CONTORO_API_ENDPOINT",
    "https://content-workflow-backend-production.up.railway.app/api/audit/inbound"
)
API_KEY = os.environ.get("CONTORO_AUDIT_API_KEY", "")
TENANT_ID = os.environ.get("CONTORO_TENANT_ID", "")
BOARD_ID = os.environ.get("CONTORO_BOARD_ID", "")


def build_payload(url, canonical_url, page_title, page_type, school, department,
                  aeo_scores, wcag_findings, integrity_challenges, coherence_findings,
                  sweep_type="agent_sweep", previous_score=None):

    numeric_scores = [q["score"] for q in aeo_scores if q.get("score") is not None]
    total_score = sum(numeric_scores)
    severity = severity_from_score(total_score)
    delta_score = (total_score - previous_score) if previous_score is not None else 0

    integrity_passed = not any(not c.get("passed", True) for c in integrity_challenges)

    failed_count = sum(1 for c in integrity_challenges if not c.get("passed", True))
    if failed_count == 0:
        agent_confidence = "high"
    elif failed_count <= 2:
        agent_confidence = "medium"
    else:
        agent_confidence = "low"

    findings = []
    for q in aeo_scores:
        if q.get("score", 2) < 2:
            findings.append({
                "question_id": q["question_id"],
                "finding": q.get("finding", ""),
                "score": q.get("score"),
                "recommendation": q.get("recommendation"),
            })
    for cf in coherence_findings:
        findings.append({
            "finding_type": cf.get("finding_type"),
            "description": cf.get("description"),
            "affected_urls": cf.get("affected_urls", []),
            "recommendation": cf.get("recommendation"),
        })

    return {
        "tenant_id": TENANT_ID,
        "board_id": BOARD_ID,
        "audit_run_id": str(uuid.uuid4()),
        "source_url": url,
        "canonical_url": canonical_url,
        "page_title": page_title,
        "page_type": page_type or "program",
        "institution": TENANT_ID,
        "school": school,
        "department": department,
        "url_pattern": None,
        "sweep_type": sweep_type,
        "triggered_by": "agent_pipeline",
        "aeo_score": total_score,
        "severity": severity,
        "delta_score": delta_score,
        "improved_questions": [],
        "regressed_questions": [],
        "findings": findings,
        "wcag_triage": wcag_findings or {},
        "pdf_findings": [],
        "page_content": {"word_count": 0},
        "integrity_challenges": integrity_challenges,
        "integrity_passed": integrity_passed,
        "agent_confidence": agent_confidence,
        "aeo_scores": [
            {
                "question_id": q["question_id"],
                "question_label": q["question_label"],
                "score": q.get("score"),
                "unclear_type": q.get("unclear_type"),
                "finding": q.get("finding", ""),
                "evidence": q.get("evidence"),
                "staleness_flag": q.get("staleness_flag", False),
                "multi_program_flag": q.get("multi_program_flag", False),
                "integrity_challenged": q.get("integrity_challenged", False),
                "integrity_objection": q.get("integrity_objection"),
                "recommendation": q.get("recommendation"),
            }
            for q in aeo_scores
        ],
    }


async def deliver_to_contoro(payload):
    if not API_KEY:
        raise ValueError("CONTORO_AUDIT_API_KEY not set")
    if not TENANT_ID:
        raise ValueError("CONTORO_TENANT_ID not set")
    if not BOARD_ID:
        raise ValueError("CONTORO_BOARD_ID not set")

    headers = {
        "Content-Type": "application/json",
        "X-Audit-Api-Key": API_KEY,
    }

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(ENDPOINT, json=payload, headers=headers)

    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Contoro API error {response.status_code}: {response.text[:200]}")
