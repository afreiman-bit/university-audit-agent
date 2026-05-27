#!/usr/bin/env python3
import asyncio
import argparse
import json
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).parent))
from agents.orchestrator.agent import sweep_url, sweep_url_list
from config.aeo_rubric import severity_from_score

GROUND_TRUTH_URLS = [
    {"url": "https://olemiss.edu/programs/bus/bachelor-business-administration/",
     "school": "business", "department": "general-business", "page_type": "program"},
    {"url": "https://olemiss.edu/programs/accy/bachelor-accountancy-accountancy/",
     "school": "accountancy", "department": "accountancy", "page_type": "program"},
    {"url": "https://olemiss.edu/programs/applsci/bachelor-social-work/",
     "school": "applied-sciences", "department": "social-work", "page_type": "program"},
    {"url": "https://olemiss.edu/programs/libarts/bachelor-arts-english/",
     "school": "liberal-arts", "department": "english", "page_type": "program"},
    {"url": "https://olemiss.edu/programs/school-of-law/air-space-cert/",
     "school": "law", "department": "center-air-space-law", "page_type": "certificate"},
]

GROUND_TRUTH_EXPECTED = {
    "https://olemiss.edu/programs/bus/bachelor-business-administration/": 11,
    "https://olemiss.edu/programs/accy/bachelor-accountancy-accountancy/": 16,
    "https://olemiss.edu/programs/applsci/bachelor-social-work/": 18,
    "https://olemiss.edu/programs/libarts/bachelor-arts-english/": 15,
    "https://olemiss.edu/programs/school-of-law/air-space-cert/": 6,
}


async def main():
    parser = argparse.ArgumentParser(description="University Audit Agent CLI")
    parser.add_argument("--url", help="Single URL to audit")
    parser.add_argument("--ground-truth", action="store_true",
                        help="Run against all 5 Ole Miss ground truth pages")
    parser.add_argument("--urls-file", help="JSON file with URL list")
    parser.add_argument("--tenant", default="olemiss")
    parser.add_argument("--school", help="School tag (single URL mode)")
    parser.add_argument("--department", help="Department tag (single URL mode)")
    parser.add_argument("--deliver", action="store_true",
                        help="Deliver results to Contoro")
    parser.add_argument("--output", help="Save results to JSON file")
    args = parser.parse_args()

    results = []

    if args.url:
        print(f"\n▶ Auditing: {args.url}\n")
        result = await sweep_url(
            url=args.url,
            tenant=args.tenant,
            school=args.school,
            department=args.department,
            deliver=args.deliver,
        )
        results = [result]

    elif args.ground_truth:
        print(f"\n▶ Running Ole Miss ground truth sweep ({len(GROUND_TRUTH_URLS)} pages)\n")
        results = await sweep_url_list(
            urls=GROUND_TRUTH_URLS,
            tenant=args.tenant,
            deliver=args.deliver,
        )

    elif args.urls_file:
        urls = json.loads(Path(args.urls_file).read_text())
        print(f"\n▶ Sweeping {len(urls)} URLs from {args.urls_file}\n")
        results = await sweep_url_list(
            urls=urls,
            tenant=args.tenant,
            deliver=args.deliver,
        )

    else:
        parser.print_help()
        return

    print("\n" + "="*60)
    print("SWEEP SUMMARY")
    print("="*60)

    for r in results:
        if r.get("error"):
            print(f"  ✗ FAILED   {r['url']}")
            print(f"             {r['error']}")
            continue

        score = r.get("aeo_score", 0)
        sev = r.get("severity", severity_from_score(score)).upper()
        expected = GROUND_TRUTH_EXPECTED.get(r["url"])
        expected_str = f"  (expected {expected})" if expected else ""
        challenges = len([c for c in r.get("integrity_challenges", []) if not c.get("passed")])
        challenge_str = f"  ⚠ {challenges} integrity challenges" if challenges else ""

        print(f"  {sev:<12} {score:>2}/24{expected_str:<16} "
              f"{r.get('page_title', r['url'])[:50]}{challenge_str}")

    print()

    if args.output:
        Path(args.output).write_text(json.dumps(results, indent=2, default=str))
        print(f"Results saved to {args.output}\n")


if __name__ == "__main__":
    asyncio.run(main())
