# ai_services.py
import google.generativeai as genai
import logging
import json
import re
import asyncio
import os
import requests
from PIL import Image
import io
import time
from typing import List, Dict, Any, Optional
from functools import lru_cache
from contextlib import suppress
import pytesseract
import yt_dlp
import speech_recognition as sr

import config

logger = logging.getLogger(__name__)

# --- Runtime Config Overrides ---
GEMINI_MODEL_NAME = os.getenv("GEMINI_MODEL_NAME", "gemini-1.5-flash").strip() or "gemini-1.5-flash"
GENERIC_TIMEOUT_SECONDS = int(os.getenv("GENERIC_TIMEOUT_SECONDS", "45"))
GENERIC_MAX_TEXT = int(getattr(config, "MAX_TEXT_CHARS", 120_000))

# --- تهيئة نماذج الذكاء الاصطناعي ---
gemini_model = None
if config.GEMINI_API_KEY:
    try:
        genai.configure(api_key=config.GEMINI_API_KEY)
        gemini_model = genai.GenerativeModel(GEMINI_MODEL_NAME)
        logger.info("Gemini model configured successfully.")
    except Exception as e:
        logger.error(f"Failed to configure Gemini: {e}")
else:
    logger.warning("GEMINI_API_KEY is not set. Gemini features will be disabled.")


def extract_json(s: str) -> str:
    """يستخرج أول كائن JSON صالح من النص (يتجاهل Markdown fences وأي حشو بعده)."""
    s = (s or "").strip()
    # Remove common fences
    s = re.sub(r"^```(?:json)?\s*|\s*```$", "", s, flags=re.IGNORECASE | re.MULTILINE)
    # Try to locate first JSON array/object by bracket balance
    start_obj = s.find('{')
    start_arr = s.find('[')
    if start_obj == -1 and start_arr == -1:
        return ""
    if start_obj != -1 and (start_arr == -1 or start_obj < start_arr):
        start, op, cl = start_obj, '{', '}'
    else:
        start, op, cl = start_arr, '[', ']'
    depth = 0
    for i, ch in enumerate(s[start:], start=start):
        if ch == op:
            depth += 1
        elif ch == cl:
            depth -= 1
            if depth == 0:
                return s[start:i+1]
    return ""


# ==================================
# ===== Gemini API Calls ===========
# ==================================

def get_gemini_model():
    global gemini_model
    if gemini_model is not None:
        return gemini_model
    if not config.GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY is not set. Gemini features will be disabled.")
        return None
    try:
        genai.configure(api_key=config.GEMINI_API_KEY)
        gemini_model = genai.GenerativeModel(GEMINI_MODEL_NAME)
        logger.info("Gemini model configured successfully.")
        return gemini_model
    except Exception as e:
        logger.error(f"Failed to configure Gemini: {e}")
        return None


async def ai_call(prompt: str, images: Optional[List[Image.Image]] = None, *, tries: int = 3, backoff: float = 1.6) -> str:
    model = get_gemini_model()
    if not model:
        return "⚠️ AI service (Gemini) is not available. Please check the API key."

    # Truncate very long prompts proactively (keeps latency in check)
    prompt = (prompt or "").strip()
    if len(prompt) > GENERIC_MAX_TEXT:
        prompt = prompt[:GENERIC_MAX_TEXT]

    # Build content list (images first, then prompt)
    content: List[Any] = []
    if images:
        for img in images:
            b = io.BytesIO()
            img.save(b, format="PNG")
            b.seek(0)
            content.append(b.getvalue())  # PTB passes raw bytes fine to Gemini SDK
    content.append(prompt)

    last_err = None
    for attempt in range(1, tries + 1):
        try:
            # Gemini Python SDK supports async call
            resp = await asyncio.wait_for(model.generate_content_async(content), timeout=GENERIC_TIMEOUT_SECONDS)
            text = (getattr(resp, "text", None) or "").strip()
            if text:
                return text
            return "⚠️ لم يتمكن الذكاء الاصطناعي من توليد إجابة ذات معنى."
        except asyncio.TimeoutError as e:
            last_err = e
            logger.warning("Gemini timeout on attempt %d/%d", attempt, tries)
        except Exception as e:
            last_err = e
            # Retry only on transient issues
            if "rate" in str(e).lower() or "quota" in str(e).lower() or "temporar" in str(e).lower():
                logger.warning("Gemini transient error on attempt %d/%d: %s", attempt, tries, e)
            else:
                logger.exception("Gemini API error (non-transient): %s", e)
                break
        # Exponential backoff before next try
        if attempt < tries:
            await asyncio.sleep(backoff ** attempt)
    return f"⚠️ حدث خطأ أثناء الاتصال بخدمة الذكاء الاصطناعي: {last_err}"


# Utility for callers that require structured output (expects valid JSON)
async def ai_call_json(prompt: str) -> Optional[Any]:
    raw = await ai_call(prompt)
    j = extract_json(raw)
    if not j:
        return None
    with suppress(Exception):
        return json.loads(j)
    return None

# --- NEW PROMPT SET ---
async def ai_summarize_bilingual(text: str) -> str:
    # Bilingual Study Summary — comprehensive, study-ready coverage
    prompt = (
        "You are a master bilingual (EN/AR) study-note builder. Create a comprehensive, study-ready summary that preserves ALL substantive ideas — do NOT omit any meaningful information. Clarity over brevity; expand as needed to cover everything.\n"
        "For every bullet, add a concise elaboration sentence that explains why it matters.\n\n"
        "NON‑NEGOTIABLE RULES:\n"
        "- Use `<h1>` for the main title.\n"
        "- Organize content into the following sections with `<h2>`: `Quick Snapshot`, `Complete Outline`, `Concepts & Definitions`, `Key Facts & Numbers`, `Symbols & Notation`, `Formulas & Calculations`, `Processes & Steps`, `Examples & Analogies`, `Common Pitfalls`, `Q&A Checkpoints`.\n"
        "- Under each section, write multiple bilingual paired blocks using EXACTLY this form so our renderer can place them side‑by‑side:\n"
        "  [ENG]English content with <b>highlighted key terms</b>[/ENG]\n"
        "  [ARB]**✅ الخلاصة:** [جملة عربية مركزة]\n"
        "      **🔍 التفاصيل:** [شرح مبسط مع إبراز <b>المصطلحات</b>] [/ARB]\n"
        "- Do NOT drop important items, numbers, names, conditions, exceptions, examples, or edge cases. If the source includes them, include them.\n"
        "- One idea per line. If a sentence contains multiple semicolon‑separated ideas, split them into separate lines. Convert tables/lists to explicit bullets.\n"
        "- Avoid redundancy: each bilingual pair must add a distinct idea.\n"
        "- For Q&A, put the question on a single line `❓` and the answer on the next single line `✅`.\n\n"
        "COVERAGE TARGETS:\n"
        "- Aim to preserve near-full content coverage; minor compression for wording only.\n"
        "- Prefer completeness over shortness; do not skip sections to save space.\n\n"
        "END WITH A FINAL CONCLUSION BLOCK using this exact tag set:\n"
        "[CONCLUSION]\n"
        "**Thesis Statement / The Big Idea 🎯:** <1 sentence>\n"
        "**Why It Matters 🚀:** <1 sentence>\n"
        "[/CONCLUSION]\n\n"
        f"Now build the study summary for the following text:\n---\n{text}"
    )
    out = await ai_call(prompt)
    return normalize_emoji_headings(out)


async def ai_summarize_bilingual_chunked(text: str, *, max_chunk: int = 8000) -> str:
    """Split long text and summarize per chunk, then synthesize a final consolidated summary."""
    s = preclean_text_for_ai(text)
    if len(s) <= max_chunk:
        return await ai_summarize_bilingual(s)
    # Split by headings or paragraphs
    parts = re.split(r"\n\s*\n+", s)
    chunks: List[str] = []
    buf = ""
    for p in parts:
        if len(buf) + len(p) + 2 <= max_chunk:
            buf += ("\n\n" if buf else "") + p
        else:
            if buf:
                chunks.append(buf)
            buf = p
    if buf:
        chunks.append(buf)
    # Summarize each chunk sequentially
    summaries: List[str] = []
    for i, c in enumerate(chunks, 1):
        partial = await ai_summarize_bilingual(c)
        summaries.append(f"<h2>Chunk {i}</h2>\n" + partial)
    # Consolidate into a final synthesis
    synthesis_prompt = (
        "You are a study-note synthesizer. Merge the following chunk summaries into ONE cohesive, non-redundant bilingual study summary, keeping the same structure rules as before. Maintain full coverage, eliminate repetition, and ensure smooth flow.\n\n"
        + "\n\n".join(summaries)
    )
    out = await ai_call(synthesis_prompt)
    return normalize_emoji_headings(_dedupe_lines_preserve_order(out))


async def ai_summarize_en(text: str) -> str:
    prompt = (
        "You are a world‑class study summarizer. Create an English‑only, study‑ready summary that preserves ALL content — do NOT omit any meaningful detail. Prefer completeness over brevity; expand as needed to cover everything.\n"
        "For each bullet include a short explanation sentence or example so the student instantly understands the point.\n\n"
        "STRICT OUTPUT RULES:\n"
        "- Output ONLY the structured content. No prefaces or closers.\n"
        "- Use `<h1>` for the main title.\n"
        "- Use `<h2>` for these sections in order: `Executive Snapshot`, `Complete Outline`, `Concepts & Definitions`, `Key Facts & Numbers`, `Symbols & Notation`, `Formulas & Calculations`, `Processes & Steps`, `Examples & Analogies`, `Common Pitfalls`, `Q&A Checkpoints`, `Final Takeaway`.\n"
        "- Use `-` bullets and start each bullet with a relevant emoji. Keep text left‑aligned.\n"
        "- Use `<b>` to highlight crucial terms, names, and numbers inside sentences.\n"
        "- NO omissions: include all points, names, conditions, exceptions, numeric details, examples, and edge cases. If in doubt, include it succinctly.\n"
        "- One idea per line; if a bullet includes multiple semicolon‑separated ideas, split them into separate bullets. Convert tables/lists to explicit bullets.\n"
        "- For Q&A, use a single line for the question `❓` and the next line for the answer `✅`. Keep answers concise.\n"
        "- NO redundancy: each bullet must be unique (no rephrasing the same point).\n\n"
        "TEMPLATE (follow this shape, adapt counts to content size):\n"
        "<h1>[Concise Study Title]</h1>\n"
        "<h2>Executive Snapshot</h2>\n"
        "- 🧠 [Core thesis with <b>key terms</b>]\n"
        "- ✅ Useful for: [each use case as its own bullet]\n"
        "- 🚫 Not suitable for: [each limitation as its own bullet]\n"
        "<h2>Complete Outline</h2>\n"
        "- 🗂️ [Top‑level section]\n"
        "- └─ [Important sub‑section]\n"
        "<h2>Concepts & Definitions</h2>\n"
        "- 📚 <b>[Term]</b>: [Definition]\n"
        "<h2>Key Facts & Numbers</h2>\n"
        "- #️⃣ [Fact/metric with <b>values</b>]\n"
        "<h2>Symbols & Notation</h2>\n"
        "- 🔣 <b>[Symbol]</b>: [Meaning/units]\n"
        "<h2>Formulas & Calculations</h2>\n"
        "- 🧮 <b>[Formula]</b>: [Variables + when to use]\n"
        "<h2>Processes & Steps</h2>\n"
        "- 🔄 [Step 1 → Step 2 → Step 3]\n"
        "<h2>Examples & Analogies</h2>\n"
        "- 🧩 [Short example/analogy]\n"
        "<h2>Common Pitfalls</h2>\n"
        "- ⚠️ [Common mistake/edge]\n"
        "<h2>Q&A Checkpoints</h2>\n"
        "- ❓ [Question] — ✅ [Answer]\n"
        "<h2>Final Takeaway</h2>\n"
        "<blockquote>🎯 [One‑sentence summary capturing the whole text]</blockquote>\n\n"
        f"Text to summarize:\n---\n{text}"
    )
    out = await ai_call(prompt)
    out = _dedupe_lines_preserve_order(out)
    return normalize_emoji_headings(out)


async def ai_explain_bilingual(text: str) -> str:
    prompt = (
        "You are 'Nour', a gifted bilingual educator serving medical and public-health students. Transform the raw material into a guided deep-dive that keeps every critical detail while making it unforgettable.\n\n"
        "**OUTPUT OBJECTIVE:** deliver thorough, memorable explanations that remain student-friendly and action-ready.\n\n"
        "**STRICT FORMAT — FOLLOW EXACTLY, NO EXTRA TEXT:**\n"
        "<h1>[Deep Dive Title]</h1>\n"
        "<h2>Quick Orientation</h2>\n"
        "[ENG]\n"
        "- **Big Picture:** [One-sentence macro summary with <b>highlighted</b> keywords].\n"
        "- **Learning Goal:** [What the student will master].\n"
        "[/ENG]\n"
        "[ARB]\n"
        "- **الفكرة العامة:** [جملة تمهيدية مع إبراز <b>المصطلحات</b>].\n"
        "- **ليه يهمني؟:** [أهمية عملية مباشرة].\n"
        "[/ARB]\n"
        "<h2>Concept Pillars</h2>\n"
        "Identify the 3–6 strongest concepts. For each concept output EXACTLY this block (no bullet list wrapper):\n"
        "<h3>[Concept Name]</h3>\n"
        "[ENG]\n"
        "- **Core Idea:** [Precise definition/claim].\n"
        "- **How it Works:** [Mechanism or sequence].\n"
        "- **Clinical / Real Use:** [Scenario or decision point].\n"
        "[/ENG]\n"
        "[ARB]\n"
        "- **شرح مبسط:** [جملة واضحة تقرب المعنى].\n"
        "- **الخطوات الأساسية:** [ترتيب أو مراحل مختصرة].\n"
        "- **مثال تطبيقي:** [مثال سردي قصير].\n"
        "- **غلط شائع يجب تجنبه:** [تحذير محدد].\n"
        "[/ARB]\n"
        "<h2>Cause → Effect Chains</h2>\n"
        "[ENG]\n"
        "- [Trigger] → [Response] explanation with <b>highlighted</b> keywords.\n"
        "- Provide at least three distinct chains covering risks, physiology, and outcomes.\n"
        "[/ENG]\n"
        "[ARB]\n"
        "- [السبب] → [النتيجة] مع إبراز <b>العناصر</b> الأساسية.\n"
        "- نفس عدد السلاسل وبمستوى عمق مماثل.\n"
        "[/ARB]\n"
        "<h2>Memory Boosters</h2>\n"
        "[ENG]\n"
        "- **Analogy:** [Vivid comparison].\n"
        "- **Mnemonic / Tip:** [Short hook].\n"
        "- **Watch Out:** [High-yield warning].\n"
        "[/ENG]\n"
        "[ARB]\n"
        "- **تشبيه ذكي:** [تشبيه يومي].\n"
        "- **قاعدة للمراجعة:** [قاعدة أو جملة يسهل حفظها].\n"
        "- **حاجة لازم تاخد بالك منها:** [تنبيه سريع].\n"
        "[/ARB]\n"
        "<h2>Check Yourself</h2>\n"
        "[ENG]\n"
        "- ❓ [Question] — ✅ [Model answer].\n"
        "- Include three distinct Q&A pairs (definition, mechanism, application).\n"
        "[/ENG]\n"
        "[ARB]\n"
        "- ❓ [سؤال] — ✅ [إجابة مختصرة].\n"
        "- نفس الأسئلة الثلاثة باللغة العربية بإجابات متوازنة.\n"
        "[/ARB]\n"
        "<h2>Final Takeaway</h2>\n"
        "<blockquote>🎯 [One-sentence synthesis in both languages highlighting the ultimate message].</blockquote>\n\n"
        "**QUALITY RULES:**\n"
        "- Preserve every crucial fact, number, condition, and exception from the source; expand briefly when clarity demands it.\n"
        "- Use `<b>` to spotlight mission-critical terminology and values in both languages.\n"
        "- Never merge multiple ideas into one bullet; split into separate bullets instead.\n"
        "- Output must match the template exactly with no preface or closing remarks beyond what is specified.\n\n"
        f"Source text:\n---\n{text}"
    )
    out = await ai_call(prompt)
    return normalize_emoji_headings(out)


async def ai_explain_en(text: str) -> str:
    prompt = (
        "You are an expert educator. Create a comprehensive explanation of the text, **entirely in English**, for a student.\n\n"
        "**Formatting Rules:**\n"
        "- Use `<h1>` for the main title and `<h2>` for section headings.\n"
        "- Use standard `-` for bullet points.\n"
        # ✨ --- تعديل هنا: إضافة تعليمات الـ Highlight --- ✨
        "- **Crucially, use `<b>` tags to highlight the most important keywords and phrases within your sentences for emphasis.**\n"
        "- Use `<blockquote>` for key insights or examples.\n\n"
        f"Now, create a high-quality English explanation for the following text:\n---\n{text}"
    )
    out = await ai_call(prompt)
    out = _dedupe_lines_preserve_order(out)
    return normalize_emoji_headings(out)


async def ai_explain_bilingual_chunked(text: str, *, max_chunk: int = 8000) -> str:
    s = preclean_text_for_ai(text)
    if len(s) <= max_chunk:
        return await ai_explain_bilingual(s)
    parts = re.split(r"\n\s*\n+", s)
    chunks: List[str] = []
    buf = ""
    for p in parts:
        if len(buf) + len(p) + 2 <= max_chunk:
            buf += ("\n\n" if buf else "") + p
        else:
            if buf:
                chunks.append(buf)
            buf = p
    if buf:
        chunks.append(buf)
    explanations: List[str] = []
    for i, c in enumerate(chunks, 1):
        partial = await ai_explain_bilingual(c)
        explanations.append(f"<h2>Section {i}</h2>\n" + partial)
    synthesis_prompt = (
        "You are a study-explainer. Combine the partial blocks below into ONE cohesive bilingual explanation."
        " Rebuild the answer using the exact template from the single-pass instruction (Quick Orientation, Concept Pillars, Cause → Effect Chains, Memory Boosters, Check Yourself, Final Takeaway)."
        " Ensure smooth flow, remove redundancy, and keep all critical facts.\n\n"
        + "\n\n".join(explanations)
    )
    out = await ai_call(synthesis_prompt)
    return normalize_emoji_headings(_dedupe_lines_preserve_order(out))
async def ai_mindmap(text: str) -> str:
    # The "Clean & Simple" Mind Map Prompt
    prompt = (
    "You are an expert in structuring information. Your task is to convert the provided text into a clean, text-based mind map. The mind map should clearly show the hierarchy of ideas using indentation and tree characters (like ├─ and └─).\n\n"
    "**Formatting Rules - VERY IMPORTANT:**\n"
    "1. The main topic should be the root of the tree.\n"
    "2. Use indentation and tree characters (├─, └─, │) to show the relationship between points.\n"
    "3. **DO NOT** add any prefixes, labels, or categories like `[Detail]:`, `[Concept]:`, or any emojis before the text on each line. The output must be pure text.\n"
    "4. The output should be ONLY the mind map itself, with no extra explanations or text before or after it.\n\n"
    "**Example of a PERFECT Output:**\n"
    "Photosynthesis\n"
    "├─ Core Definition\n"
    "│  └─ Process by which plants use sunlight, water, and CO2 to create food.\n"
    "├─ Key Stages\n"
    "│  ├─ Light-Dependent Reactions\n"
    "│  └─ Calvin Cycle (Light-Independent)\n"
    "└─ Key Components\n"
    "   ├─ Chlorophyll\n"
    "   └─ Chloroplasts\n\n"
    f"Now, apply this exact clean structure to the following text:\n---\n{text}"
    )
    return await ai_call(prompt)


async def ai_generate_flashcards(text: str, *, count: int = 12) -> str:
    prompt = f"""
You are an elite bilingual study coach. From the source material, build compact flashcards that capture the most examinable knowledge.

STRICT FORMAT RULES (no deviations):
- Produce exactly {count} cards unless the source is too small; in that case, cover everything that matters.
- Separate cards with a blank line and use this exact structure for each card:
#️⃣ بطاقة {{n}}
❓ EN Question: <one sharp test question in English>
❓ AR Question: <Arabic mirror of the question>
✅ EN Answer: <concise answer in English with <b>highlighted</b> keywords>
✅ AR Answer: <concise Arabic answer with <b>المصطلحات البارزة</b>>
- Keep answers short (<= 2 lines) and factual.
- Cover definitions, processes, numbers, and tricky exceptions.

Source text (trimmed):
---
{clamp_text(text)}
"""
    out = await ai_call(prompt)
    out = _dedupe_lines_preserve_order(out)
    return normalize_emoji_headings(out)


async def ai_generate_study_plan(text: str, *, days: int = 7) -> str:
    prompt = f"""
You are a high-performance study strategist. Craft a laser-focused revision plan that turns this material into a day-by-day roadmap.

MANDATORY FORMAT (no introductions or endings):
- For each day (Day 1 .. Day {days}), output the following exact block:
📅 Day {{n}} — <Theme>/<Module>
- 🎯 Objective: <one sentence outcome>
- 📚 Study Blocks: <2-3 bullet-style tasks separated by `; `>
- 🧠 Active Recall: <question prompt or drill>
- 🔁 Spaced Review: <how to revisit or connect to previous days>
- ⚡ Pro Tip: <short motivation or efficiency hack>
- Leave one blank line between days.
- Tailor tasks directly to the supplied content; reference real subtopics and numbers when present.

Source text (trimmed):
---
{clamp_text(text)}
"""
    out = await ai_call(prompt)
    out = _dedupe_lines_preserve_order(out)
    return normalize_emoji_headings(out)


async def ai_generate_focus_notes(text: str) -> str:
    prompt = (
        "You are a premium revision assistant. Transform the material into a high-yield focus sheet the student can skim before an exam.\n\n"
        "OUTPUT TEMPLATE (keep headings and emojis exactly as shown):\n"
        "🔥 High-Yield Insights\n"
        "- ... (bilingual paired bullets: English sentence then Arabic mirror on the next line).\n"
        "⚠️ Tricky Pitfalls\n"
        "- ... (highlight common mistakes or misconceptions).\n"
        "🧪 Must-Know Examples\n"
        "- ... (show concrete examples/formulas with <b>highlighted</b> values).\n"
        "🧩 Fast Recall Prompts\n"
        "- ❓ Question ...\n"
        "  ✅ Answer ...\n"
        "🚀 30-Second Recap\n"
        "- ... (three bullet takeaways).\n"
        "Always bold the leading trigger phrase (both languages) using `<b>` so the eye catches it instantly.\n"
        "Ensure every bullet pair covers a unique idea; no fluff. Keep the sheet <= 40 lines.\n\n"
        f"Source text (trimmed):\n---\n{clamp_text(text)}"
    )
    out = await ai_call(prompt)
    out = _dedupe_lines_preserve_order(out)
    return normalize_emoji_headings(out)


async def ai_generate_exam_drill(text: str, *, count: int = 5) -> str:
    prompt = f"""
You are a ruthless exam coach. Build a mini drill of multiple-choice questions that immediately test mastery of the content.

STRICT OUTPUT RULES:
- Produce {count} questions maximum.
- For each question, follow this exact layout:
📝 سؤال {{n}}
❓ Prompt: <English question>
❓ بالعربي: <Arabic translation>
🅰️ الخيارات:
A) ...
B) ...
C) ...
D) ...
✅ الإجابة الصحيحة: <Letter> — <short justification>
🧠 لماذا هذا صحيح؟ <2-line explanation mixing EN + AR>
- Keep options concise, mutually exclusive, and grounded in the source.
- Include calculations or numeric details whenever available.
- Separate questions with a blank line. No intro/outro text.

Source text (trimmed):
---
{clamp_text(text)}
"""
    out = await ai_call(prompt)
    out = _dedupe_lines_preserve_order(out)
    return normalize_emoji_headings(out)


async def ai_translate_dual(text: str) -> str:
    prompt = f"""
You are a senior MEDICAL translator/editor (Public Health & Clinical Research). First, reconstruct clean English from noisy OCR (fix cross-line hyphenation like "Cross\n-\nSectional" → "Cross-Sectional"; remove stray symbols like ™). Then produce a meaning‑preserving Modern Standard Arabic EXPLANATION (شرح مبسط) suitable for Egyptian medical students. Prefer medical sense over literal word-by-word; expand briefly to clarify intent where helpful.

ABSOLUTE OUTPUT SHAPE (no extra chatter):
- Split input into logical segments (≤ 2 sentences or ~200 chars).
- If a segment begins with a natural heading (e.g., "Disadvantages of Cross-Sectional Study:"), add two heading lines BEFORE the content:
[HEAD_EN]English heading only[/HEAD_EN]
[HEAD_AR]عنوان عربي موجز متوافق طبيًا[/HEAD_AR]
- Then output EXACTLY these two content lines:
[ENG]cleaned English segment (turn inline enumerations like "1) ... 2) ..." into clean lines)[/ENG]
[ARB]Arabic medical explanation (not literal). For enumerations, use an ordered style (١، ٢، ٣) with clear phrasing. Use <b>…</b> only to highlight key medical terms.[/ARB]
- Optionally append key takeaways in Arabic for this segment:
[TAKEAWAYS_AR]
- نقطة مختصرة عالية الفائدة
- نقطة مختصرة ثانية
[/TAKEAWAYS_AR]
- Keep bullets/numbering markers but translate their texts.
- Maintain strict 1:1 order with the source; never merge unrelated segments.

MEDICAL CONSISTENCY:
- Use standard terms: Cross‑Sectional = "<b>دراسة مقطعية عرضية</b>", Case‑Control = "<b>دراسة حالة‑شاهد</b>", Cohort = "<b>دراسة أترابية</b>", Randomized Clinical Trial = "<b>تجربة سريرية عشوائية</b>", Quasi‑Experimental = "<b>شبه تجريبية</b>".
- Expand ambiguous shorthand into clear phrases when needed.

ADD A FINAL GLOSSARY:
- After all segments, append this exact block:
<GLOSSARY_JSON>
[{{"term":"English term","arabic":"المصطلح بالعربية","definition":"short medical definition in Arabic"}}, …]
</GLOSSARY_JSON>

Source text:
---
{clamp_text(text)}
"""
    out = await ai_call(prompt)
    return _dedupe_lines_preserve_order(out)


def _extract_tagged_json(s: str, tag: str = "GLOSSARY_JSON"):
    s = s or ""
    m = re.search(rf"<{tag}>(.*?)</{tag}>", s, flags=re.DOTALL | re.IGNORECASE)
    if not m:
        return None
    blob = m.group(1).strip()
    j = extract_json(blob) or blob
    try:
        return json.loads(j)
    except Exception:
        return None


def extract_glossary_json(s: str):
    return _extract_tagged_json(s, "GLOSSARY_JSON")


def preclean_text_for_ai(text: str) -> str:
    """Lightweight cleanup for OCR'ed/line-broken text before sending to AI.
    - Join mid‑word hyphenation across newlines
    - Collapse random linebreaks inside sentences
    - Remove stray symbols like ™
    - Normalize multiple blank lines
    """
    s = (text or "")
    # Remove trademark and odd symbols
    s = re.sub(r"[\u2122®©]+", "", s)
    # Join hyphenated words split across lines: word-\nNext -> word-Next
    s = re.sub(r"(\w)\-\s*\n\s*(\w)", r"\1-\2", s)
    # Join broken lines within a sentence: if previous line doesn't end with punctuation or bullet, merge
    s = re.sub(r"([^\.!?:;\-•])\n(?!\n)\s*(\w)", r"\1 \2", s)
    # Collapse sequences of very short lines (common in bad OCR: each word on separate line)
    lines = s.split('\n')
    rebuilt = []
    buf = []
    def flush_buf():
        nonlocal buf, rebuilt
        if buf:
            rebuilt.append(' '.join(buf).strip())
            buf = []
    for ln in lines:
        t = ln.strip()
        if not t:
            flush_buf()
            rebuilt.append('')
            continue
        # if line is very short (<= 3 words) and not ending with punctuation, accumulate
        if len(t.split()) <= 3 and not re.search(r"[\.!?؛:]$", t):
            buf.append(t)
            continue
        flush_buf()
        rebuilt.append(t)
    flush_buf()
    s = '\n'.join(rebuilt)
    # Normalize bullet-only lines with a single dash
    s = re.sub(r"^\s*[•·]\s*", "- ", s, flags=re.MULTILINE)
    # Collapse 3+ newlines to max 2
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


async def ai_key_concepts(text: str) -> str:
    prompt = (
        "Extract a list of the key concepts/terms from the following text. Provide a brief definition for each concept, "
        "and if possible add a short example for each.\n\n"
        f"Text:\n{text}"
    )
    return await ai_call(prompt)


async def ai_generate_quiz(text: str, n_questions: int) -> List[Dict[str, Any]]:
    prompt = (
        "Create a multiple-choice quiz from the text. "
        f"Required number of questions: {n_questions}. "
        "Output ONLY a valid JSON array of objects, with no extra text or markdown, like this:\n"
        "[{\"q\": \"...\", \"choices\": [\"A\",\"B\",\"C\",\"D\"], \"answer_index\": 2, \"explanation\": \"...\"}, ...]\n\n"
        f"Text:\n{text}"
    )
    raw = await ai_call(prompt)
    json_str = extract_json(raw)
    if not json_str: return []
    try:
        data = json.loads(json_str)
        return [q for q in data if isinstance(q, dict) and q.get('q') and isinstance(q.get('choices'), list) and len(q['choices']) >= 2][:n_questions]
    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"Quiz JSON parse error: {e} | raw: {raw[:400]}")
        return []


async def ai_presentation_slides(text: str) -> List[Dict[str, Any]]:
    prompt = (
        "Generate a professional presentation outline from the text. "
        "Output ONLY a valid JSON array of objects with the shape:\n"
        "[{\"title\": \"...\", \"bullets\": [\"...\",\"...\"]}, ...]\n\n"
        f"Text:\n{text}"
    )
    raw = await ai_call(prompt)
    json_str = extract_json(raw)
    if not json_str: return [{"title": "Error in Generation", "bullets": ["Could not parse AI output."]}]
    try:
        slides = json.loads(json_str)
        return slides[:20]
    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"Slides JSON parse error: {e} | raw: {raw[:400]}")
    return [{"title": "Error in Generation", "bullets": ["Could not parse AI output."]}]


async def ai_extract_from_image(img: Image.Image) -> str:
    prompt = (
        "Extract as much text and key concepts as you can from this educational image or document, "
        "then summarize them into essential bullet points."
    )
    return await ai_call(prompt, images=[img])


async def ai_generate_arabic_glossary(terms: List[str]) -> Optional[List[Dict[str, str]]]:
    """Given a list of English medical terms, produce Arabic equivalents and short Arabic definitions.
    Returns a list of {term, arabic, definition} or None on failure.
    """
    if not terms:
        return []
    # Limit batch to keep token cost sensible
    terms = [t.strip() for t in terms if t and t.strip()][:50]
    prompt = (
        "You are a bilingual MEDICAL glossary builder for Egyptian medical students.\n"
        "For each English term, output a concise Arabic equivalent and a 1–2 line Arabic definition.\n"
        "- Prefer commonly accepted medical terminology.\n"
        "- If multiple senses exist, choose the sense most used in public health/clinical research contexts.\n"
        "- STRICTLY OUTPUT a JSON array of objects with fields: term, arabic, definition. No extra text.\n\n"
        f"TERMS:\n{json.dumps(terms, ensure_ascii=False)}\n\n"
        "JSON:"
    )
    raw = await ai_call(prompt)
    j = extract_json(raw)
    if not j:
        return None
    with suppress(Exception):
        data = json.loads(j)
        if isinstance(data, list):
            out: List[Dict[str, str]] = []
            for it in data:
                if not isinstance(it, dict):
                    continue
                term = str(it.get("term", "")).strip()
                arabic = str(it.get("arabic", "")).strip()
                definition = str(it.get("definition", "")).strip()
                if term and arabic:
                    out.append({"term": term, "arabic": arabic, "definition": definition})
            return out
    return None


async def extract_text_from_image(img: Image.Image) -> str:
    try:
        lang = os.getenv("TESSERACT_LANGS", "ara+eng")
        text = pytesseract.image_to_string(img, lang=lang)
        text = (text or "").strip()
        return text or "لم يتم العثور على نص في الصورة."
    except Exception as e:
        logger.error(f"OCR error: {e}")
        return "حدث خطأ أثناء استخراج النص من الصورة."


async def extract_audio_from_youtube(url: str) -> str:
    url = (url or "").strip()
    if not url or not (url.startswith("http://") or url.startswith("https://")):
        return "⚠️ رابط يوتيوب غير صالح."
    import glob, os
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': 'temp_audio.%(ext)s',
        # Avoid forcing ffmpeg; we'll transcode with pydub if available
        'quiet': True,
        'noprogress': True,
        'retries': 2,
    }
    try:
        loop = asyncio.get_running_loop()
        # Run blocking yt_dlp in a thread so it doesn't block the event loop
        def _download():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
        await loop.run_in_executor(None, _download)
        # Find downloaded file (any extension)
        candidates = sorted(glob.glob('temp_audio.*'))
        if not candidates:
            return '⚠️ لم أتمكن من تنزيل الملف الصوتي.'
        src = candidates[0]
        # Try to convert to WAV via pydub for better compatibility
        wav_path = 'temp_audio.wav'
        try:
            from pydub import AudioSegment
            aud = AudioSegment.from_file(src)
            aud.export(wav_path, format='wav')
            path_for_stt = wav_path
        except Exception:
            path_for_stt = src
        text = speech_to_text(path_for_stt)
        # Cleanup
        with suppress(Exception):
            if os.path.exists(wav_path): os.remove(wav_path)
        for f in candidates:
            with suppress(Exception):
                os.remove(f)
        return text or '⚠️ لم أتمكن من تفريغ الصوت.'
    except Exception as e:
        logger.error("yt_dlp error: %s", e)
        return f"⚠️ تعذر تنزيل الصوت: {e}"


def speech_to_text(audio_file_path: str) -> str:
    """Transcribe speech trying English then Arabic; fallback to chunked capture if very long.
    Returns raw text (no formatting)."""
    recognizer = sr.Recognizer()
    try:
        with sr.AudioFile(audio_file_path) as source:
            audio = recognizer.record(source)
    except Exception:
        return ""
    # Try English first then Arabic
    for lang in ("en-US", "ar-EG"):
        try:
            return recognizer.recognize_google(audio, language=lang)
        except (sr.UnknownValueError, sr.RequestError):
            continue
    # Fallback: chunking
    try:
        texts = []
        with sr.AudioFile(audio_file_path) as source:
            while True:
                try:
                    audio_chunk = recognizer.record(source, duration=30)
                except Exception:
                    break
                if not audio_chunk.frame_data:
                    break
                part = None
                for lang in ("en-US", "ar-EG"):
                    try:
                        part = recognizer.recognize_google(audio_chunk, language=lang)
                        break
                    except (sr.UnknownValueError, sr.RequestError):
                        continue
                if part:
                    texts.append(part)
                else:
                    break
        return "\n".join(texts).strip()
    except Exception:
        return ""


# ==================================
# ===== Hugging Face API Calls =====
# ==================================

async def hf_api_call(model_id: str, payload: dict) -> dict:
    if not config.HUGGINGFACE_API_KEY:
        return {"error": "Hugging Face API key is not set."}
    API_URL = f"https://api-inference.huggingface.co/models/{model_id}"
    headers = {"Authorization": f"Bearer {config.HUGGINGFACE_API_KEY}"}
    try:
        import httpx
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(API_URL, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()
    except httpx.ReadTimeout:
        return {"error": f"Request timed out for model {model_id}."}
    except httpx.HTTPStatusError as e:
        if "is currently loading" in str(e.response.text):
            return {"error": "model_loading"}
        logger.error(f"Hugging Face API request failed: {e.response.status_code} - {e.response.text}")
        return {"error": str(e.response.text)}
    except Exception as e:
        logger.error(f"Hugging Face API request failed: {e}")
        return {"error": str(e)}


async def _retry_hf_on_load(model_id: str, payload: dict) -> dict:
    response = await hf_api_call(model_id, payload)
    if response.get("error") == "model_loading":
        logger.info(f"Model {model_id} is loading, waiting 20 seconds...")
        await asyncio.sleep(20)
        response = await hf_api_call(model_id, payload)
    return response


async def ai_summarize_free(text: str) -> str:
    truncated_text = " ".join(text.split()[:800])
    response = await _retry_hf_on_load("facebook/bart-large-cnn", {"inputs": truncated_text, "parameters": {"min_length": 30, "max_length": 150}})
    if "error" in response:
        return f"⚠️ تعذر إنشاء الملخص المجاني: {response['error']}"
    return response[0].get("summary_text", "لم يتمكن النموذج المجاني من إنشاء ملخص.")


async def ai_explain_free(text: str) -> str:
    summary = await ai_summarize_free(text)
    if summary.startswith("⚠️"):
        return summary
    prompt = f"Rewrite the following summary in a simple, explanatory tone...\n\nSummary:\n{summary}"
    out = await ai_call(prompt)
    return normalize_emoji_headings(out)


async def ai_qa_free(context_text: str, question: str) -> str:
    truncated_context = " ".join(context_text.split()[:1500])
    response = await _retry_hf_on_load("deepset/roberta-base-squad2", {"inputs": {"question": question, "context": truncated_context}})
    if "error" in response:
        return f"⚠️ تعذر العثور على إجابة: {response['error']}"
    answer = response.get("answer", "لم أتمكن من إيجاد إجابة واضحة في النص.")
    score = response.get("score", 0)
    if score < 0.1:
        return "لم أتمكن من إيجاد إجابة واضحة في النص."
    return f"**الإجابة المستخرجة:**\n_{answer}_\n\n(بنسبة ثقة {score:.1%})"


# ==================================
# ===== Claude Sonnet 3.5 (Free) ===
# ==================================

async def claude_sonnet_qa(prompt: str) -> str:
    API_URL = "https://api-inference.huggingface.co/models/Anthropic/claude-3-sonnet-20240229"
    headers = {"Authorization": f"Bearer {getattr(config, 'HUGGINGFACE_API_KEY', '')}"}
    payload = {"inputs": prompt}
    try:
        import httpx
        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post(API_URL, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            if isinstance(data, dict) and "error" in data:
                return f"⚠️ Claude API Error: {data['error']}"
            if isinstance(data, list) and data and "generated_text" in data[0]:
                return data[0]["generated_text"]
            return str(data)
    except Exception as e:
        logger.error(f"Claude Sonnet API error: {e}")
        return f"⚠️ Claude Sonnet API error: {e}"
    

    # --- ✨✨ هنا الدالة المفقودة التي سببت الخطأ ✨✨ ---
def clamp_text(s: str, max_chars: int = GENERIC_MAX_TEXT) -> str:
    """Clamps a string to a maximum number of characters."""
    s = s or ""
    return s if len(s) <= max_chars else s[:max_chars]

def normalize_emoji_headings(text: str) -> str:
    """Ensure emoji-based headings start on a new line and read cleanly.
    Helps the PDF generator detect headings like 🏥 Community health care, 🔬 Providing new knowledge, etc.
    """
    if not text:
        return ""
    EMOJIS = "🏥🔬📚🧪🧠📌📝📊🧩📖✅⚠️🔎🔍"
    # Keep bullets intact; just normalize spacing after emoji
    # Single space after emoji when followed by non-space
    text = re.sub(rf'([{EMOJIS}])\s*(?=\S)', r'\1 ', text)
    # Collapse excessive blank lines
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text


def _dedupe_lines_preserve_order(text: str) -> str:
    """Remove duplicate lines while preserving order. Comparison is done on a
    normalized version of the line (stripped, collapse spaces, lowercase, strip HTML tags).
    Keeps formatting of the first occurrence as-is. Useful to mitigate LLM repetition.
    """
    if not text:
        return text
    # Quick HTML tag stripper for comparison only
    def _strip_tags(s: str) -> str:
        return re.sub(r"<[^>]+>", "", s)

    seen = set()
    kept = []
    for raw in text.splitlines():
        cmp_key = _strip_tags(raw).strip()
        # collapse inner whitespace and lowercase for comparison
        cmp_key = re.sub(r"\s+", " ", cmp_key).lower()
        if not cmp_key:
            # Preserve blank lines sparsely: avoid long runs
            if kept and kept[-1].strip() == "":
                continue
            kept.append("")
            continue
        if cmp_key in seen:
            continue
        seen.add(cmp_key)
        kept.append(raw)
    # Collapse 3+ blank lines to max 2
    deduped = "\n".join(kept)
    deduped = re.sub(r"\n{3,}", "\n\n", deduped)
    return deduped


# Fallback: استخدم Claude تلقائياً إذا فشل Gemini
async def ai_call_with_fallback(prompt: str, images: Optional[List[Image.Image]] = None) -> str:
    result = await ai_call(prompt, images)
    if result.startswith("⚠️") or "حدث خطأ" in result:
        logger.warning(f"Gemini failed. Falling back to Claude Sonnet. Original error: {result}")
        if images:
            return "⚠️ Gemini failed, and the fallback model (Claude) doesn't support images."
        claude_prompt = f"Human: {prompt}\n\nAssistant:"
        result2 = await claude_sonnet_qa(claude_prompt)
        if result2 and not result2.startswith("⚠️"):
            return result2
