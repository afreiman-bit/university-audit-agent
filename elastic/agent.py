import os
import json
import hashlib
from datetime import datetime
from elasticsearch import AsyncElasticsearch
from pydantic import BaseModel
from typing import Optional

ES_INDEX = os.environ.get("ELASTIC_INDEX", "university-pages")

INDEX_MAPPING = {
    "mappings": {
        "properties": {
            "tenant":          {"type": "keyword"},
            "url":             {"type": "keyword"},
            "canonical_url":   {"type": "keyword"},
            "page_title":      {"type": "text"},
            "school":          {"type": "keyword"},
            "department":      {"type": "keyword"},
            "page_type":       {"type": "keyword"},
            "body_text":       {"type": "text"},
            "aeo_score":       {"type": "integer"},
            "severity":        {"type": "keyword"},
            "sweep_date":      {"type": "date"},
            "accreditation":   {"type": "keyword"},
            "costs":           {"type": "keyword"},
            "deadlines":       {"type": "keyword"},
            "contacts":        {"type": "keyword"},
            "duration":        {"type": "keyword"},
            "format_modality": {"type": "keyword"},
        }
    },
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0,
    }
}


class CoherenceFinding(BaseModel):
    finding_type: str
    affected_urls: list[str]
    description: str
    similarity_score: Optional[float]
    recommendation: str


def get_es_client():
    cloud_id = os.environ.get("ELASTIC_CLOUD_ID")
    api_key = os.environ.get("ELASTIC_API_KEY")
    if cloud_id and api_key:
        return AsyncElasticsearch(cloud_id=cloud_id, api_key=api_key)
    return AsyncElasticsearch(hosts=[os.environ.get("ELASTIC_URL", "http://localhost:9200")])


async def ensure_index(es):
    exists = await es.indices.exists(index=ES_INDEX)
    if not exists:
        await es.indices.create(index=ES_INDEX, body=INDEX_MAPPING)


async def index_page(tenant, url, canonical_url, page_title, school, department,
                     page_type, body_text, aeo_score, severity, extracted_facts):
    es = get_es_client()
    await ensure_index(es)

    doc_id = hashlib.md5(f"{tenant}:{url}".encode()).hexdigest()
    doc = {
        "tenant":          tenant,
        "url":             url,
        "canonical_url":   canonical_url,
        "page_title":      page_title,
        "school":          school,
        "department":      department,
        "page_type":       page_type,
        "body_text":       body_text[:10000],
        "aeo_score":       aeo_score,
        "severity":        severity,
        "sweep_date":      datetime.utcnow().isoformat(),
        "accreditation":   extracted_facts.get("accreditation"),
        "costs":           extracted_facts.get("costs", []),
        "deadlines":       extracted_facts.get("deadlines", []),
        "contacts":        extracted_facts.get("contact"),
        "duration":        extracted_facts.get("duration"),
        "format_modality": extracted_facts.get("format_modality"),
    }

    await es.index(index=ES_INDEX, id=doc_id, document=doc)
    await es.close()


async def find_coherence_issues(tenant, url, page_title, body_text, school, similarity_threshold=0.85):
    es = get_es_client()
    findings = []

    try:
        similar_query = {
            "query": {
                "bool": {
                    "must": [
                        {"term": {"tenant": tenant}},
                        {"more_like_this": {
                            "fields": ["body_text", "page_title"],
                            "like": body_text[:2000],
                            "min_term_freq": 2,
                            "max_query_terms": 25,
                            "min_doc_freq": 1,
                        }},
                    ],
                    "must_not": [{"term": {"url": url}}]
                }
            },
            "size": 5,
            "_source": ["url", "page_title", "school", "department"],
        }

        similar_results = await es.search(index=ES_INDEX, body=similar_query)
        hits = similar_results["hits"]["hits"]

        for hit in hits:
            score = hit.get("_score", 0)
            if score > 5:
                findings.append(CoherenceFinding(
                    finding_type="duplicate_content",
                    affected_urls=[url, hit["_source"]["url"]],
                    description=(
                        f"'{page_title}' and '{hit['_source']['page_title']}' "
                        f"cover similar content. One may be redundant."
                    ),
                    similarity_score=round(score, 2),
                    recommendation=(
                        "Review both pages for overlapping content. "
                        "Designate one as canonical and differentiate the other."
                    ),
                ))

        gap_query = {
            "query": {"term": {"tenant": tenant}},
            "aggs": {
                "avg_score": {"avg": {"field": "aeo_score"}},
                "low_scores": {
                    "filter": {"range": {"aeo_score": {"lte": 6}}},
                    "aggs": {"count": {"value_count": {"field": "url"}}}
                },
            },
            "size": 0,
        }

        gap_results = await es.search(index=ES_INDEX, body=gap_query)
        aggs = gap_results.get("aggregations", {})
        critical_count = aggs.get("low_scores", {}).get("count", {}).get("value", 0)
        avg_score = aggs.get("avg_score", {}).get("value", 0)

        if critical_count and critical_count > 3:
            findings.append(CoherenceFinding(
                finding_type="authority_gap",
                affected_urls=[url],
                description=(
                    f"Institutional pattern: {int(critical_count)} pages score "
                    f"6/24 or below. Institution average: {round(avg_score or 0, 1)}/24."
                ),
                similarity_score=None,
                recommendation=(
                    "Run a full institutional audit to identify systemic content gaps."
                ),
            ))

    except Exception as e:
        findings.append(CoherenceFinding(
            finding_type="authority_gap",
            affected_urls=[url],
            description=f"Cross-page coherence check error: {str(e)[:100]}",
            similarity_score=None,
            recommendation="Re-run coherence check after resolving index connection.",
        ))
    finally:
        await es.close()

    return findings
