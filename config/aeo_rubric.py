# config/aeo_rubric.py
AEO_QUESTIONS = {
    1:  "What does this program cost, and is financial aid available?",
    2:  "What are my chances of getting a job, and what will I earn?",
    3:  "What do I need to apply, and when is the deadline?",
    4:  "How long will it take and how is it structured?",
    5:  "Is this program respected and accredited?",
    6:  "What is it actually like to be a student here?",
    7:  "Who do I contact if I have a question?",
    8:  "What will I actually learn and what courses will I take?",
    9:  "Who will teach me?",
    10: "How does this program compare to what I need?",
    11: "What happens after I apply?",
    12: "Is this program available in a format that works for my life?",
}

AEO_CRITERIA = {
    1: {
        2: "A specific cost figure is stated directly on the page (per credit hour, per semester, or total program cost). Financial aid availability is explicitly mentioned.",
        1: "Cost is referenced but only via a link to another page, or financial aid is mentioned without any cost figure present.",
        0: "No cost information and no financial aid reference of any kind on the page.",
    },
    2: {
        2: "Median salary or salary range is stated explicitly with a named source (BLS, NACE, or equivalent). Employment rate or job growth percentage also stated.",
        1: "Career paths or job titles are listed but no salary figures present, OR salary is mentioned without a source or is vague.",
        0: "No career outcome information of any kind.",
    },
    3: {
        2: "Specific application requirements (GPA, materials, prerequisites) AND at least one deadline (priority or final) are both stated explicitly on the page.",
        1: "Apply Now link is present but no requirements or deadlines on the page, OR requirements stated but no deadline, OR deadline stated but no requirements.",
        0: "No application information of any kind on the page.",
    },
    4: {
        2: "Credit hours AND duration in time (semesters or years) are both stated explicitly. Program structure (full-time, part-time, cohort, etc.) is clear.",
        1: "Only credit hours OR only duration stated, but not both. OR structure is vague.",
        0: "No information about program length or structure.",
    },
    5: {
        2: "A specific accrediting body is named explicitly (e.g., AACSB, CSWE, ABET, ABA, ACEN). The accreditation statement is present on the page, not just linked.",
        1: "A ranking or recognition is mentioned but no accrediting body named. OR accreditation is linked but not stated on page.",
        0: "No accreditation, rankings, or program credentials of any kind.",
    },
    6: {
        2: "At least one named student or alumni with a photo, a specific quote, and concrete detail about their experience.",
        1: "Generic student testimonial without a name or photo.",
        0: "No student experience content of any kind.",
    },
    7: {
        2: "A named individual with both an email address and a phone number specific to this program.",
        1: "A named individual present but missing email or phone. OR only a general office contact.",
        0: "No contact information of any kind on the page.",
    },
    8: {
        2: "Actual course names and numbers are listed on the page. At least 3 specific courses visible.",
        1: "Curriculum described in prose but no individual course names or numbers on the page.",
        0: "No curriculum or course information of any kind.",
    },
    9: {
        2: "At least one named faculty member with title and specialty or research focus.",
        1: "Faculty described in general terms but no individual names appear.",
        0: "No faculty information of any kind.",
    },
    10: {
        2: "Prerequisites or entry requirements explicitly stated, including transfer credit policy or minimum GPA.",
        1: "Some context about who the program is for but no explicit prerequisites for new applicants.",
        0: "No information about requirements or prerequisites.",
    },
    11: {
        2: "Clear post-application process described: review timeline, notification date, and next enrollment steps.",
        1: "Some post-application information present but full timeline not addressed.",
        0: "Nothing about what happens after submitting an application.",
    },
    12: {
        2: "Delivery format(s) explicitly stated: in-person campus location(s) named, or online/hybrid confirmed.",
        1: "Format implied but not explicit.",
        0: "No information about delivery format, location, or modality.",
    },
}

UNCLEAR_TYPES = {
    "extraction_failure":      "Page too thin, navigation-heavy, or broken to evaluate.",
    "content_behind_barrier":  "Information likely exists behind a login, form, or PDF.",
    "ambiguous_reference":     "Something relevant is present but cannot be confidently scored.",
    "contradictory_signals":   "Conflicting information present on the page.",
}

def severity_from_score(score: int) -> str:
    if score <= 6:  return "critical"
    if score <= 12: return "high"
    if score <= 18: return "improving"
    return "healthy"
