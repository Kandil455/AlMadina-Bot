"""Medical glossary utilities: loading, caching, and term detection.

This module is designed to work offline with a small seed list and optionally
augment itself from online sources when the network is available.

Public API:
  - load_glossary_cache()
  - find_terms_in_text(text) -> List[dict]
  - merge_glossaries(*lists) -> List[dict]

Notes:
  - If you choose to hydrate with online sources, set env GLOSSARY_SOURCES to a
    comma‑separated list of raw JSON URLs containing objects with
    fields: {"term": str, "arabic": str, "definition": str}
"""
from __future__ import annotations

import os
import io
import json
import re
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple

DATA_DIR = os.path.join(os.getcwd(), "data")
CACHE_PATH = os.path.join(DATA_DIR, "medical_glossary_cache.json")

_ENTRIES_CACHE: Optional[List[Dict[str, str]]] = None
_INDEX_CACHE: Optional[Dict[str, Dict[str, str]]] = None


def _ensure_data_dir() -> None:
    with contextlib.suppress(Exception):
        os.makedirs(DATA_DIR, exist_ok=True)


def _normalize_term(s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r"\s+", " ", s)
    return s.lower()


def _seed_entries() -> List[Dict[str, str]]:
    # A compact seed to bootstrap behavior; extend via cache/network
    return [
        {"term": "Cross-Sectional Study", "arabic": "دراسة مقطعية عرضية", "definition": "دراسة تُقَيِّم حالة عيّنة من السكان في نقطة زمنية واحدة."},
        {"term": "Cohort Study", "arabic": "دراسة أترابية", "definition": "تتبّع مجموعة مشتركة في تعرّض ما مع مقارنة نِتاجات صحية بمرور الوقت."},
        {"term": "Case-Control Study", "arabic": "دراسة حالة‑شاهد", "definition": "مقارنة بين ذوي الحالة ومجموعة شاهد لتقييم العلاقة مع عوامل خطورة سابقة."},
        {"term": "Randomized Clinical Trial", "arabic": "تجربة سريرية عشوائية", "definition": "تقسيم المشاركين عشوائيًا لتقييم فاعلية تدخل طبي تحت ضبط."},
        {"term": "Quasi-Experimental", "arabic": "شبه تجريبية", "definition": "تصميمات تدخلية بلا عشوائية كاملة، تستخدم موازنة أو ضوابط بديلة."},
        {"term": "Odds Ratio", "arabic": "نسبة الأرجحية", "definition": "قياس لارتباط التعرّض بالحدث في الدراسات الحالة‑شاهد."},
        {"term": "Relative Risk", "arabic": "الخطر النسبي", "definition": "نسبة مخاطر الحدث بين مجموعتين (تعرّض مقابل عدم تعرّض)."},
        {"term": "Incidence", "arabic": "الحدوث", "definition": "عدد الحالات الجديدة خلال فترة محددة بين معرّضين للخطر."},
        {"term": "Prevalence", "arabic": "الانتشار", "definition": "عدد كل الحالات الحالية (قديمة/جديدة) في لحظة زمنية محددة."},
        {"term": "Confidence Interval", "arabic": "فاصل الثقة", "definition": "مجال يُرجَّح أن يحتوي القيمة الحقيقية للمعلمة بنسبة معيّنة."},
        {"term": "P-Value", "arabic": "قيمة P", "definition": "احتمال الحصول على نتيجة مثل المرصودة أو أشد إذا كانت الفرضية الصفرية صحيحة."},
        {"term": "Bias", "arabic": "انحياز", "definition": "خطأ منهجي يؤدي لتقدير غير دقيق للارتباط أو الأثر."},
        {"term": "Confounding", "arabic": "إرباك (التباس)", "definition": "تداخل عامل خارجي مرتبط بالتعرّض والنتيجة يشوّه الارتباط."},
        {"term": "Validity", "arabic": "الصِدق", "definition": "مدى قياس الأداة لما يفترض قياسه."},
        {"term": "Reliability", "arabic": "الثبات", "definition": "قابلية القياس لإعطاء نتائج متّسقة عند التكرار."},
    ]


def load_glossary_cache() -> List[Dict[str, str]]:
    global _ENTRIES_CACHE
    if _ENTRIES_CACHE is not None:
        return _ENTRIES_CACHE
    _ensure_data_dir()
    if os.path.isfile(CACHE_PATH):
        try:
            with open(CACHE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    _ENTRIES_CACHE = data
                    return _ENTRIES_CACHE
        except Exception:
            pass
    _ENTRIES_CACHE = _seed_entries()
    return _ENTRIES_CACHE


def save_glossary_cache(entries: List[Dict[str, str]]) -> None:
    _ensure_data_dir()
    try:
        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(entries, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    finally:
        # Invalidate in-memory caches
        global _ENTRIES_CACHE, _INDEX_CACHE
        _ENTRIES_CACHE = entries
        _INDEX_CACHE = None


async def hydrate_from_network(sources: Optional[List[str]] = None) -> List[Dict[str, str]]:
    """Try fetching glossary entries from network sources. Non-fatal on failure."""
    try:
        import httpx
    except Exception:
        return []
    urls = sources or [u.strip() for u in (os.getenv("GLOSSARY_SOURCES") or "").split(",") if u.strip()]
    results: List[Dict[str, str]] = []
    for url in urls:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.get(url)
                r.raise_for_status()
                data = r.json()
                if isinstance(data, list):
                    for item in data:
                        if not isinstance(item, dict):
                            continue
                        term = item.get("term") or item.get("english")
                        arabic = item.get("arabic") or item.get("ar")
                        definition = item.get("definition") or item.get("def") or ""
                        if term and arabic:
                            results.append({"term": str(term), "arabic": str(arabic), "definition": str(definition)})
        except Exception:
            continue
    return results


def _build_index(entries: List[Dict[str, str]]) -> Dict[str, Dict[str, str]]:
    global _INDEX_CACHE
    if _INDEX_CACHE is not None:
        return _INDEX_CACHE
    idx: Dict[str, Dict[str, str]] = {}
    for it in entries:
        term = _normalize_term(it.get("term", ""))
        if term and term not in idx:
            idx[term] = it
    _INDEX_CACHE = idx
    return _INDEX_CACHE


def _generate_ngrams(words: List[str], max_n: int = 4) -> List[str]:
    grams: List[str] = []
    n = len(words)
    for k in range(1, min(max_n, n) + 1):
        for i in range(0, n - k + 1):
            grams.append(" ".join(words[i:i + k]))
    return grams


def find_terms_in_text(text: str, *, limit: int = 64) -> List[Dict[str, str]]:
    """Detect likely medical terms in English text and return glossary entries."""
    base = load_glossary_cache()
    idx = _build_index(base)
    # Lightweight preprocess: strip punctuation except hyphen
    cleaned = re.sub(r"[^A-Za-z0-9\-\s]", " ", text or " ")
    words = [w for w in cleaned.split() if w]
    candidates = _generate_ngrams(words, max_n=4)
    found: List[Dict[str, str]] = []
    seen = set()
    for cand in candidates:
        key = _normalize_term(cand)
        if key in idx and key not in seen:
            seen.add(key)
            found.append(idx[key])
        if len(found) >= limit:
            break
    return found


def merge_glossaries(*lists: List[Dict[str, str]]) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    seen = set()
    for lst in lists:
        for it in lst or []:
            term = _normalize_term(it.get("term", ""))
            if term and term not in seen:
                seen.add(term)
                out.append({
                    "term": it.get("term", ""),
                    "arabic": it.get("arabic", ""),
                    "definition": it.get("definition", "")
                })
    return out


# Late import to avoid hard dependency when running in limited environments
import contextlib  # noqa: E402
