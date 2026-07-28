#!/usr/bin/env python3
"""
Draait de blog-evaluator: beoordeelt elke gepubliceerde contentpagina op echte
Search Console-cijfers en herschrijft (optioneel) de slechtst presterende pagina
op dezelfde URL.

Gebruik:
    python3 scripts/evaluate_content.py                  # alleen rapporteren, niets wijzigen
    python3 scripts/evaluate_content.py --refresh        # herschrijf de slechtste pagina
    python3 scripts/evaluate_content.py --refresh -n 3   # herschrijf de 3 slechtste

Env: dezelfde .env als de backend (SUPABASE_*, ANTHROPIC_API_KEY, GSC_*/GOOGLE_ADS_*).
Zonder Search Console-koppeling rapporteert het script dat er geen data is en stopt.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def _arg_int(flag: str, default: int) -> int:
    if flag not in sys.argv:
        return default
    idx = sys.argv.index(flag)
    return int(sys.argv[idx + 1]) if idx + 1 < len(sys.argv) else default


async def main() -> None:
    from backend.content.evaluator import evaluate_all, refresh_candidates, run_evaluation_cycle

    do_refresh = "--refresh" in sys.argv
    limit = _arg_int("-n", 1)

    if not do_refresh:
        results = evaluate_all()
        if not results:
            print("Geen Search Console-data beschikbaar (of geen gepubliceerde pagina's).")
            return
        print(f"{len(results)} pagina's beoordeeld:\n")
        for r in results:
            print(f"[{r['verdict']:9}] {r['url_path']}")
            print(f"             pos {r['position']:5.1f} | {r['impressions']:5} impr | {r['clicks']:4} clicks | {r['reason']}")
        queue = refresh_candidates(results)
        print(f"\n{len(queue)} pagina's komen in aanmerking voor een refresh. Draai met --refresh om te herschrijven.")
        return

    summary = await run_evaluation_cycle(limit=limit)
    print(f"{summary['evaluated']} pagina's beoordeeld, {len(summary['refreshed'])} herschreven:")
    for r in summary["refreshed"]:
        print(f"  ✅ {r['url_path']} — {r['reason']}")


if __name__ == "__main__":
    asyncio.run(main())
