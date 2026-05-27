import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv
load_dotenv()

from agents.crawl_extraction.agent import crawl_page
from agents.fact_extraction.agent import extract_facts
from agents.aeo_scoring.agent import score_page
from agents.integrity.agent import check_finding, cross_finding_check
from elastic.agent import index_page, find_coherence_issues
from contoro_api.deliver import build_payload, deliver_to_contoro
from config.aeo_rubric import severity_from_score


async def sweep_url(url, tenant, school=None, department=None,
                    page_type="program", deliver=True, verbose=True):

    def log(msg):
        if verbose:
            print(f"  {msg}")

    log(f"→ Crawling {url}")

    crawl = await crawl_page(url)
    if crawl.crawl_error:
        log(f"✗ Crawl failed: {crawl.crawl_error}")
        return {"url": url, "error": crawl.crawl_error, "aeo_score": 0}

    log(f"✓ Crawled — {crawl.body_word_count} words, {'PDFs detected' if crawl.pdfs_detected else 'no PDFs'}")

    facts = extract_facts(crawl.body_text, crawl.pdfs_detected, crawl.body_word_count)
    log(f"✓ Facts — costs: {facts.costs[:1] or 'none'}, accreditation: {facts.accreditation or 'none'}")

    log(f"→ Scoring 12 AEO questions...")
    raw_scores = await score_page(url=url, body_text=crawl.body_text, extracted_facts=facts.model_dump())

    log(f"→ Running integrity checks...")
    integrity_challenges = []
    verified_scores = []

    for qs in raw_scores:
        integrity = await check_finding(
            question_id=qs.question_id,
            question_label=qs.question_label,
            score=qs.score,
            unclear_type=qs.unclear_type,
            finding=qs.finding,
            evidence=qs.evidence,
            body_text=crawl.body_text,
        )

        if not integrity.passed:
            log(f"  ⚠ Q{qs.question_id} challenged: {integrity.objection[:80] if integrity.objection else ''}")
            integrity_challenges.append({
                "question_id": qs.question_id,
                "passed": False,
                "original_score": integrity.challenged_score,
                "revised_score": integrity.revised_score,
                "objection": integrity.objection,
                "evidence_verified": integrity.evidence_verified,
            })
            verified_scores.append({
                **qs.model_dump(),
                "score": integrity.revised_score,
                "unclear_type": integrity.revised_unclear_type or qs.unclear_type,
                "integrity_challenged": True,
                "integrity_objection": integrity.objection,
            })
        else:
            verified_scores.append({
                **qs.model_dump(),
                "integrity_challenged": False,
                "integrity_objection": None,
            })

    numeric = [q["score"] for q in verified_scores if q.get("score") is not None]
    total_score = sum(numeric)
    severity = severity_from_score(total_score)
    log(f"✓ AEO Score: {total_score}/24 ({severity}), {len(integrity_challenges)} integrity challenges")

    cross_check = await cross_finding_check(url=url, all_findings=verified_scores)
    if cross_check.get("contradictions_found"):
        log(f"⚠ Cross-finding contradictions: {len(cross_check.get('flags', []))}")

    log(f"→ Indexing into Elastic...")
    coherence_findings = []
    try:
        await index_page(
            tenant=tenant, url=url, canonical_url=crawl.canonical_url,
            page_title=crawl.page_title, school=school or "untagged",
            department=department or "untagged", page_type=page_type,
            body_text=crawl.body_text, aeo_score=total_score, severity=severity,
            extracted_facts=facts.model_dump(),
        )
        coherence_findings = await find_coherence_issues(
            tenant=tenant, url=url, page_title=crawl.page_title,
            body_text=crawl.body_text, school=school or "untagged",
        )
        log(f"✓ Elastic: {len(coherence_findings)} coherence findings")
    except Exception as e:
        log(f"✗ Elastic error (skipping): {e}")

    result = {
        "url": url,
        "canonical_url": crawl.canonical_url,
        "page_title": crawl.page_title,
        "page_type": page_type,
        "school": school,
        "department": department,
        "aeo_score": total_score,
        "severity": severity,
        "aeo_scores": verified_scores,
        "integrity_challenges": integrity_challenges,
        "integrity_passed": len(integrity_challenges) == 0,
        "coherence_findings": [cf.model_dump() for cf in coherence_findings],
        "cross_check": cross_check,
        "word_count": crawl.body_word_count,
    }

    if deliver:
        log(f"→ Delivering to Contoro...")
        try:
            payload = build_payload(
                url=url, canonical_url=crawl.canonical_url,
                page_title=crawl.page_title, page_type=page_type,
                school=school or "", department=department or "",
                aeo_scores=verified_scores, wcag_findings={},
                integrity_challenges=integrity_challenges,
                coherence_findings=[cf.model_dump() for cf in coherence_findings],
            )
            contoro_response = await deliver_to_contoro(payload)
            result["contoro"] = contoro_response
            log(f"✓ Contoro: card {'created' if contoro_response.get('is_new') else 'updated'}")
        except Exception as e:
            log(f"✗ Contoro delivery failed: {e}")
            result["contoro_error"] = str(e)

    return result


async def sweep_url_list(urls, tenant, deliver=True, concurrency=3):
    semaphore = asyncio.Semaphore(concurrency)

    async def bounded_sweep(url_config):
        async with semaphore:
            return await sweep_url(
                url=url_config["url"], tenant=tenant,
                school=url_config.get("school"),
                department=url_config.get("department"),
                page_type=url_config.get("page_type", "program"),
                deliver=deliver,
            )

    tasks = [bounded_sweep(u) for u in urls]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return [
        r if isinstance(r, dict) else {"url": urls[i]["url"], "error": str(r)}
        for i, r in enumerate(results)
    ]
