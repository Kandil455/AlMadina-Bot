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
    # ✨ --- تم تعديل هذا الـ Prompt بالكامل ليصبح أكثر تنظيمًا واحترافية --- ✨
    # The "Strategic Briefing" Bilingual Summarization Prompt
    prompt = (
    "You are to adopt the persona of 'Fahres', a top-tier Strategic Learning Consultant. Your expertise lies in creating high-impact 'Executive Briefings' from dense texts. Your goal is not just to shorten the text, but to extract the core thesis, the most powerful supporting points, and the ultimate conclusion, presenting them in a way that is immediately actionable and understandable.\n\n"
    "**Your Core Task:**\n"
    "Analyze the provided text to identify its central argument and key pillars. Then, construct a bilingual strategic briefing.\n\n"
    "**Strict Formatting Rules - NON-NEGOTIABLE:**\n"
    "1.  Start with a main title for the briefing using `<h1>`.\n"
    "2.  For each key point, you MUST generate a paired block with this EXACT structure:\n"
    "    `[ENG]A sharp, concise takeaway or key finding in English. Use <b>tags</b> for the most critical keywords.[/ENG]`\n"
    "    `[ARB]**✅ الخلاصة:** [Provide the core idea in a punchy Arabic sentence.]\n"
    "    **🔍 التفاصيل:** [Briefly elaborate on the point in simple Arabic, explaining its significance. Use <b>tags</b> for critical keywords.]`\n"
    "3.  After all points, you MUST include a final, separate conclusion block with this exact structure:\n"
    "    `[CONCLUSION]`\n"
    "    "    "**Thesis Statement / The Big Idea 🎯:** [State the single most important message or thesis of the entire text in one clear sentence.]\n"
    "    "    "**Why It Matters 🚀:** [Explain the overall significance of this idea in one sentence.]\n"
    "    `[/CONCLUSION]`\n\n"
    "**Example of a PERFECT Output:**\n"
    "<h1>Strategic Briefing on Cognitive Dissonance</h1>\n"
    "[ENG]<b>Cognitive Dissonance</b> occurs when a person holds two or more <b>contradictory beliefs</b>, ideas, or values, leading to psychological stress.[/ENG]\n"
    "[ARB]**✅ الخلاصة:** العقل يكره التناقض، ويشعر بالتوتر عند وجود أفكار متعارضة.\n"
    "    **🔍 التفاصيل:** عندما تتعارض أفعالك مع <b>قيمك</b> (مثلاً تدخن وأنت تعرف أنه مضر)، يحاول عقلك تقليل هذا التوتر بتغيير أفعالك أو <b>تبريرها</b>.\n"
    "[CONCLUSION]\n"
    "**Thesis Statement / The Big Idea 🎯:** Our minds are hardwired to seek consistency, and the discomfort of internal conflict is a powerful driver of human behavior and self-justification.\n"
    "**Why It Matters 🚀:** Understanding this concept explains why people rationalize poor decisions and resist information that contradicts their existing beliefs.\n"
    "[/CONCLUSION]\n\n"
    f"Now, apply this exact persona and structure to the following text:\n---\n{text}"
)
    out = await ai_call(prompt)
    return normalize_emoji_headings(out)


async def ai_summarize_en(text: str) -> str:
    prompt = (
        "You are an expert academic writer. Your task is to summarize the following text into a professional, clear, and well-structured document **entirely in English**.\n\n"
        "**Formatting Rules:**\n"
        "- Use `<h1>` for the main title and `<h2>` for section headings.\n"
        "- Use standard `-` for bullet points, starting each with a relevant emoji.\n"
        # ✨ --- تعديل هنا: إضافة تعليمات الـ Highlight --- ✨
        "- **Crucially, use `<b>` tags to highlight the most important keywords and phrases within your sentences.** This is for emphasis, not just for titles.\n"
        "- Use `<blockquote>` for important notes or takeaways.\n\n"
        f"Now, create a high-quality English summary for the following text:\n---\n{text}"
    )
    out = await ai_call(prompt)
    return normalize_emoji_headings(out)


async def ai_explain_bilingual(text: str) -> str:
    prompt = (
        "You are 'Nour', a gifted bilingual educator. Your goal is to make complex topics feel incredibly simple and memorable.\n\n"
        "**Your Core Task:** Break the text into key concepts and write bilingual blocks for each.\n\n"
        "**STRICT OUTPUT RULES — NON‑NEGOTIABLE:**\n"
        "1) Start with a main title using `<h1>`.\n"
        "2) For each concept, produce EXACTLY this block:\n"
        "[ENG]The English concept in ONE concise sentence. **Use `<b>` tags to highlight critical terms.**[/ENG]\n"
        "[ARB]\n"
        "- **الفكرة ببساطة 💡:** [Simple child‑level explanation. **Use `<b>` tags to highlight critical terms.**].\n"
        "- **مثال من الواقع 🚗:** [Story‑like analogy/example.].\n"
        "- **ليه مهم؟ 🤔:** [Practical importance.].\n"
        "- **خد بالك ⚠️:** [Common pitfall/nuance.].\n"
        "[/ARB]\n\n"
        "3) DO NOT add any extra text before/after the required blocks.\n\n"
        f"Now, apply this to the following text:\n---\n{text}"
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
    return normalize_emoji_headings(out)
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
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': 'temp_audio.%(ext)s',
        'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}],
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
        return speech_to_text("temp_audio.mp3")
    except Exception as e:
        logger.error("yt_dlp error: %s", e)
        return f"⚠️ تعذر تنزيل الصوت: {e}"


def speech_to_text(audio_file_path: str) -> str:
    recognizer = sr.Recognizer()
    with sr.AudioFile(audio_file_path) as source:
        audio = recognizer.record(source)
    try:
        return recognizer.recognize_google(audio, language="ar-EG")
    except Exception:
        return "تعذر تحويل الصوت إلى نص."


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
    EMOJIS = "🏥🔬📚🧪🧠📌📝📊🧩📖"
    # Newline before emoji if not already at start of line
    text = re.sub(rf'(?<!\n)([{EMOJIS}])', r'\n\1', text)
    # Single space after emoji when followed by non-space
    text = re.sub(rf'([{EMOJIS}])\s*(?=\S)', r'\1 ', text)
    # Collapse excessive blank lines
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text


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
