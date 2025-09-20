#!/usr/bin/env python3
import os
import json
import argparse
from pathlib import Path

import asyncio

# Local imports
import sys
sys.path.append(str(Path(__file__).resolve().parents[1]))
from medical_glossary import load_glossary_cache, save_glossary_cache, merge_glossaries


RAW_SOURCES = [
    # English wordlist of medical terms (public domain list). Used only for detection; no AR/defs.
    "https://raw.githubusercontent.com/glutanimate/wordlist-medicalterms-en/master/wordlist.txt",
]


async def fetch_text(url: str) -> str:
    import httpx
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(url)
        r.raise_for_status()
        return r.text


def to_entries_from_wordlist(text: str):
    out = []
    for line in text.splitlines():
        term = line.strip()
        if not term or term.startswith('#'):
            continue
        out.append({"term": term, "arabic": "", "definition": ""})
    return out


async def main():
    ap = argparse.ArgumentParser(description="Hydrate medical glossary cache from online sources")
    ap.add_argument("--append", action="store_true", help="Append to existing cache instead of replacing")
    args = ap.parse_args()

    base = load_glossary_cache() if args.append else []

    entries = []
    for url in RAW_SOURCES:
        try:
            text = await fetch_text(url)
            entries.extend(to_entries_from_wordlist(text))
        except Exception as e:
            print("Failed to fetch", url, e)

    merged = merge_glossaries(base, entries)
    save_glossary_cache(merged)
    print(f"Hydrated glossary with {len(merged)} entries at data/medical_glossary_cache.json")


if __name__ == "__main__":
    asyncio.run(main())

