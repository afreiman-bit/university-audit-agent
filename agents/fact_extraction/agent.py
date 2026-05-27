import re
from typing import Optional
from pydantic import BaseModel


class ExtractedFacts(BaseModel):
    costs: list[str]
    deadlines: list[str]
    accreditation: Optional[str]
    contact: Optional[str]
    duration: Optional[str]
    format_modality: Optional[str]
    pdfs_detected: bool
    word_count: int


COST_PATTERNS = [
    r"\$[\d,]+(?:\.\d{2})?\s*(?:per\s+credit(?:\s+hour)?|per\s+semester|per\s+year|total|annually)?",
    r"tuition[:\s]+\$[\d,]+",
    r"(?:cost|fee|price)[:\s]+\$[\d,]+",
]

DEADLINE_PATTERNS = [
    r"(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}(?:,?\s+\d{4})?",
    r"(?:priority|final|application)\s+deadline[:\s]+[^\n\.]+",
    r"deadline[:\s]+[^\n\.]+",
]

ACCREDITATION_BODIES = [
    "AACSB", "CSWE", "ABET", "ACEN", "CCNE", "ABA", "LCME", "CEPH",
    "NAEYC", "NASAD", "NASM", "NAST", "CAEP", "APA", "CAHIIM",
    "ACPE", "CoARC", "JRCERT", "NAACLS", "ACOTE", "CAA", "ASHA",
    "Council on Social Work Education",
    "Association to Advance Collegiate Schools of Business",
    "Accreditation Board for Engineering and Technology",
    "American Bar Association",
]

LOCATION_KEYWORDS = [
    "Oxford", "Tupelo", "DeSoto", "Booneville", "Jackson",
    "Online", "online", "hybrid", "Hybrid",
    "in-person", "in person", "on-campus", "on campus",
    "distance learning", "remote",
]

EMAIL_PATTERN = r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"
PHONE_PATTERN = r"(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}"
CREDIT_PATTERN = r"(\d{2,3})\s*(?:credit\s*hours?|credits?|semester\s*hours?)"
DURATION_PATTERN = r"(\d+)\s*(?:year|semester|month)s?"


def extract_facts(body_text: str, pdfs_detected: bool, word_count: int) -> ExtractedFacts:
    costs = []
    for pattern in COST_PATTERNS:
        matches = re.findall(pattern, body_text, re.IGNORECASE)
        costs.extend(m.strip() for m in matches if m.strip())
    costs = list(dict.fromkeys(costs))[:5]

    deadlines = []
    for pattern in DEADLINE_PATTERNS:
        matches = re.findall(pattern, body_text, re.IGNORECASE)
        deadlines.extend(m.strip() for m in matches if m.strip())
    deadlines = list(dict.fromkeys(deadlines))[:5]

    accreditation = None
    for body in ACCREDITATION_BODIES:
        if body.lower() in body_text.lower():
            accreditation = body
            break

    contact_parts = []
    emails = re.findall(EMAIL_PATTERN, body_text)
    phones = re.findall(PHONE_PATTERN, body_text)
    if emails:
        contact_parts.append(emails[0])
    if phones:
        contact_parts.append(phones[0])
    contact = ", ".join(contact_parts) if contact_parts else None

    credits_match = re.search(CREDIT_PATTERN, body_text, re.IGNORECASE)
    duration_match = re.search(DURATION_PATTERN, body_text, re.IGNORECASE)
    duration_parts = []
    if credits_match:
        duration_parts.append(f"{credits_match.group(1)} credit hours")
    if duration_match:
        duration_parts.append(duration_match.group())
    duration = ", ".join(duration_parts) if duration_parts else None

    found_locations = []
    for keyword in LOCATION_KEYWORDS:
        if keyword in body_text:
            found_locations.append(keyword)
    format_modality = ", ".join(dict.fromkeys(found_locations)) if found_locations else None

    return ExtractedFacts(
        costs=costs,
        deadlines=deadlines,
        accreditation=accreditation,
        contact=contact,
        duration=duration,
        format_modality=format_modality,
        pdfs_detected=pdfs_detected,
        word_count=word_count,
    )
