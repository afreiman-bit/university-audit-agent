# University Web Audit Agent System

A multi-agent system that crawls university program pages, scores them for AI-era discoverability, surfaces cross-page conflicts using Elastic semantic search, and routes prioritized findings into an editorial project management workflow for human remediation.

Built for the [Google Cloud Rapid Agent Hackathon](https://rapid-agent.devpost.com) · Elastic Track.

---

## The Problem

University program pages are broadly invisible to AI. When a prospective student asks an AI assistant about nursing programs, financial aid, or application requirements, the answer is synthesized from whatever is machine-readable and well-structured on those pages. If the information isn't there — or isn't structured — the institution simply doesn't appear in the answer.

Beyond AI visibility, universities face a deeper problem: they don't know what they don't know. Duplicate content, conflicting information across departments, no clear source of truth — these are daily realities for university communications teams with no systematic way to find them.

This system solves both problems.

---

## Architecture

```
Sitemap / Discovery Agent
        ↓
Orchestrator (Google ADK + Gemini)
        ↓
┌─────────────────────────────────────┐
│           Core Agent Fleet          │
│                                     │
│  Agent 1 — Crawl & Extraction       │
│  Fact Extraction Step               │
│  Agent 2 — Technical Health         │
│  Agent 3 — AEO Scoring (12 prompts) │
│  Agent 4 — WCAG Triage              │
│  Agent 8 — Prompt Gap               │
│  Agent 9 — Card Metadata Tagger     │
│                                     │
│  [Per-agent Integrity checks]       │
└─────────────────────────────────────┘
        ↓
Elastic Agent Builder (Agent 5)
Cross-Page Coherence via A2A
        ↓
Integrity Agent — Cross-Finding Check
        ↓
Pipeline (Dedup · Diff · Routing · Validation)
        ↓
Contoro Inbound Card API
```

---

## Agent Fleet

| Agent | Responsibility |
|---|---|
| **Sitemap / Discovery** | Reads sitemap.xml, applies scope rules, hands URL list to Orchestrator |
| **Orchestrator** | Root ADK agent — spawns agents, tracks progress, handles retries |
| **Crawl & Extraction** | Fetches pages, strips navigation noise, extracts PDFs, builds structured payload |
| **Fact Extraction** | Pulls 6 fact-shaped fields (cost, deadlines, accreditation, contact, duration, format) into structured table — original prose always travels alongside |
| **Technical Health** | Schema markup, stale data, broken links, orphaned pages, PDF flags |
| **AEO Scoring** | 12 individual prompts evaluating the questions prospective students ask AI assistants |
| **WCAG Triage** | Heading hierarchy, alt text, link text, contrast — routes findings to accessibility team |
| **Prompt Gap** | Generates the questions a page should answer, checks whether it actually does — identifies invisible content gaps |
| **Card Metadata Tagger** | Attaches structured metadata to every finding (URL, issue type, prompt, platform, timestamp) — the attribution bridge to GA4 |
| **Cross-Page Coherence** | Elastic-native — semantic search and vector similarity across the full indexed corpus to surface duplicates and conflicts |
| **Integrity Agent** | Adversarial safety layer — challenges every finding, downgrades weak scores, flags fabricated evidence. Grounded in Anthropic's 2026 multi-agent alignment research. |

---

## The AEO Scoring Rubric

The 12 questions a prospective student would ask an AI assistant about any program page:

1. What does this program cost, and is financial aid available?
2. What are my chances of getting a job, and what will I earn?
3. What do I need to apply, and when is the deadline?
4. How long will it take and how is it structured?
5. Is this program respected and accredited?
6. What is it actually like to be a student here?
7. Who do I contact if I have a question?
8. What will I actually learn and what courses will I take?
9. Who will teach me?
10. How does this program compare to what I need?
11. What happens after I apply?
12. Is this program available in a format that works for my life?

Each question scores 0 (absent) / 1 (partial) / 2 (present and machine-readable). Pages are evaluated with four typed uncertain states — `extraction_failure`, `content_behind_barrier`, `ambiguous_reference`, `contradictory_signals` — rather than a single catch-all unclear.

---

## The Integrity Agent

This system directly addresses Anthropic's 2026 finding that teams of AI agents consistently score higher on business goals and lower on ethics than single agents — what researchers call diffusion of responsibility. Each agent assumes another will flag the problem. None do.

The Integrity Agent counteracts this with an explicitly adversarial role:

> *"Your job is not to be helpful. Your job is to find what is wrong with the findings you are given. Be skeptical. Not helpful."*

It runs in two modes:
- **Per-agent** — immediately after each individual agent, scoped to that agent's output only
- **Cross-finding** — once after all agents complete, checking for inter-agent contradictions

Findings that fail integrity review become Human Review Cards with the specific objection noted, rather than creating standard audit cards.

---

## Elastic Integration

Elastic Agent Builder powers Agent 5 — the Cross-Page Coherence agent. Every swept page is indexed into Elasticsearch. Agent 5 queries the full corpus using vector similarity search to surface:

- **Duplicate content** — pages saying the same thing in different words
- **Conflicting information** — pages that contradict each other on facts, policy, or contacts
- **Authority gaps** — no clear source of truth when multiple pages cover the same topic

Agent 5 exposes its findings to the Google ADK Orchestrator via **A2A (Agent-to-Agent) protocol** — Google's open standard for cross-framework agent communication. Elastic and Google ADK both support A2A natively.

This cross-page coherence capability is the demo's centerpiece. It surfaces findings that are impossible to make by auditing pages in isolation — and it's the most common, most painful problem university communications teams face.

---

## Contoro Integration

Findings route to [Contoro](https://contoro.app) — an editorial project management system for university communications teams — via an inbound card API. Each finding becomes an audit card on the Site Health board.

- **One card per URL** — persistent across sweeps, accumulates history
- **Bundle routing** — findings spawn work cards routed to the appropriate team (IT for schema issues, content team for AEO gaps, accessibility office for WCAG findings)
- **Sweep-driven lane movement** — cards move between severity bands automatically as scores change
- **Verification loop** — when all work cards in a bundle resolve, a verification sweep fires to confirm fixes landed

---

## Tech Stack

- **Google ADK** — agent orchestration
- **Gemini** — reasoning for all evaluation prompts
- **Elastic Agent Builder** — cross-page coherence agent, Elasticsearch indexing
- **A2A Protocol** — Google ADK ↔ Elastic Agent Builder communication
- **MCP** — Elastic MCP server integration
- **Cloud Run** — agent orchestrator hosting
- **Node.js / Express** — Contoro inbound card API

---

## Tenant Configuration

Each university is configured with a scope object that defines what the crawler includes:

```json
{
  "tenant": "olemiss",
  "scope_name": "University of Mississippi — Full Audit",
  "seed_urls": [
    "https://olemiss.edu/programs/",
    "https://olemiss.edu/departments/"
  ],
  "include_patterns": [
    "olemiss.edu/programs/*",
    "olemiss.edu/departments/*",
    "*.olemiss.edu/*"
  ],
  "exclude_patterns": [
    "*/news/*",
    "*/events/*",
    "*/login*",
    "*/wp-admin*"
  ],
  "school_tagging": {
    "pattern": "olemiss.edu/programs/{school}/{program}",
    "extract_school_from": "path_segment_3",
    "extract_program_from": "path_segment_4"
  },
  "canonical_priority": true
}
```

School and department tags extracted from URL path structure travel on every card and every work item, enabling institution-wide analytics by school and department over time.

---

## Getting Started

```bash
git clone https://github.com/your-username/university-audit-agent
cd university-audit-agent
cp config/tenant_example.json config/tenant_local.json
# Add your Google Cloud and Elastic credentials to .env
npm install
npm run orchestrator
```

Full setup documentation in [`/docs/setup.md`](docs/setup.md).

---

## License

MIT — see [LICENSE](LICENSE).

---

*Built for the Google Cloud Rapid Agent Hackathon · Elastic Track · June 2026*
