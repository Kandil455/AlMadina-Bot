import json
import logging
from typing import List, Tuple, Optional, Dict, Union

import config

logger = logging.getLogger(__name__)


def _normalize_seg(seg: Union[Tuple, Dict, str]) -> Tuple[str, str, str, str, List[str]]:
    if isinstance(seg, (list, tuple)):
        if len(seg) >= 5:
            return str(seg[0] or ''), str(seg[1] or ''), str(seg[2] or ''), str(seg[3] or ''), list(seg[4] or [])
        if len(seg) >= 4:
            return str(seg[0] or ''), str(seg[1] or ''), str(seg[2] or ''), str(seg[3] or ''), []
        if len(seg) >= 2:
            return str(seg[0] or ''), str(seg[1] or ''), '', '', []
    if isinstance(seg, dict):
        return (
            str(seg.get('eng','') or ''), str(seg.get('arb','') or ''),
            str(seg.get('head_en','') or ''), str(seg.get('head_ar','') or ''),
            list(seg.get('takeaways', []) or [])
        )
    return str(seg or ''), '', '', '', []

def _segments_to_nodes(segments: List[Union[Tuple, Dict, str]]) -> list:
    nodes = []
    for idx, seg in enumerate(segments, 1):
        eng, arb, head_en, head_ar, takeaways = _normalize_seg(seg)
        # Heading (if any)
        if head_en or head_ar:
            title = (head_en or '').strip()
            if title:
                nodes.append({"tag": "h3", "children": [f"{idx}. {title}"]})
            if head_ar:
                nodes.append({"tag": "p", "children": [{"tag": "em", "children": [head_ar]}]})
        # English then Arabic (no EN/AR labels visible)
        if eng:
            nodes.append({"tag": "p", "children": [eng]})
        if arb:
            nodes.append({"tag": "p", "children": [arb]})
        # Takeaways
        if takeaways:
            nodes.append({"tag": "p", "children": [{"tag": "strong", "children": ["نقاط مفتاحية:"]}]})
            nodes.append({"tag": "ul", "children": [{"tag": "li", "children": [tk]} for tk in takeaways]})
    return nodes


async def publish_bilingual_to_telegraph(title: str, segments: List[Union[Tuple, Dict, str]], glossary: Optional[List[Dict[str, str]]] = None) -> Optional[str]:
    """Publish segments to Telegra.ph. Returns the URL on success or None on failure.
    Requires TELEGRAPH_ACCESS_TOKEN in config.
    """
    token = getattr(config, 'TELEGRAPH_ACCESS_TOKEN', None)
    if not token:
        logger.info("TELEGRAPH_ACCESS_TOKEN not set; skipping Telegraph publish.")
        return None

    try:
        import httpx
    except Exception:
        logger.warning("httpx not available; skipping Telegraph publish.")
        return None


async def publish_lines_to_telegraph(title: str, lines: List[str]) -> Optional[str]:
    token = getattr(config, 'TELEGRAPH_ACCESS_TOKEN', None)
    if not token:
        logger.info("TELEGRAPH_ACCESS_TOKEN not set; skipping Telegraph publish.")
        return None
    try:
        import httpx, re
    except Exception:
        logger.warning("httpx not available; skipping Telegraph publish.")
        return None
    # Minimal HTML stripping to plain paragraphs
    def strip_tags(s: str) -> str:
        return re.sub(r"<[^>]+>", "", s or "").strip()
    nodes = [{"tag": "p", "children": [strip_tags(ln)]} for ln in lines if strip_tags(ln)]
    API = "https://api.telegra.ph/createPage"
    payload = {
        "access_token": token,
        "title": title or "Al Madina Study Page",
        "author_name": "Al Madina Bot",
        "content": json.dumps(nodes, ensure_ascii=False),
        "return_content": False,
    }
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.post(API, data=payload)
            r.raise_for_status()
            data = r.json()
            if not data.get('ok'):
                logger.error("Telegraph error: %s", data)
                return None
            return data['result']['url']
    except Exception as e:
        logger.error("Failed to publish to Telegraph: %s", e)
        return None

    nodes = _segments_to_nodes(segments)
    if glossary:
        nodes.append({"tag": "h3", "children": ["📚 المصطلحات الطبية"]})
        for item in glossary:
            term = str(item.get('term', ''))
            arabic = str(item.get('arabic', ''))
            definition = str(item.get('definition', ''))
            nodes.append({"tag": "p", "children": [f"• {term} — {arabic}: {definition}"]})
    API = "https://api.telegra.ph/createPage"
    payload = {
        "access_token": token,
        "title": title or "Al Madina Study Page",
        "author_name": "Al Madina Bot",
        "content": json.dumps(nodes, ensure_ascii=False),
        "return_content": False,
    }
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.post(API, data=payload)
            r.raise_for_status()
            data = r.json()
            if not data.get('ok'):
                logger.error("Telegraph error: %s", data)
                return None
            return data['result']['url']
    except Exception as e:
        logger.error("Failed to publish to Telegraph: %s", e)
        return None
