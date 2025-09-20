# file_generator.py
from asyncio.log import logger
import io
import re
import uuid
from typing import List, Tuple, Optional, Dict
import weasyprint
from datetime import datetime

import config

def _escape_html(s: str) -> str:
    """A minimal HTML escaper for content that will be placed inside tags."""
    s = str(s or "")
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _allow_basic_html(s: str) -> str:
    """Escape all HTML then re-allow a safe subset of tags."""
    if not s:
        return ""
    esc = _escape_html(s)
    # Allow handful of inline/block tags
    esc = re.sub(r"&lt;(/?(?:b|strong|i|em|ul|ol|li|br|sup|sub|h3|h4|blockquote|span))&gt;", r"<\1>", esc)
    return esc

def build_pdf_from_lines_weasy(
    title: str,
    author_username: str,
    lines: list[str],
    lang: str = 'ar'
) -> tuple[io.BytesIO, str]:
    """
    Generates a premium, feature-rich PDF document with a cover page, advanced styling,
    and intelligent content parsing for bilingual and structured text.
    """
    
    # --- CSS: The heart of the new design. It's much larger and more sophisticated. ---
    css = """
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;800&family=Roboto:wght@400;500;700&display=swap');
    
    :root {
        --font-main: 'Cairo', 'Roboto', sans-serif;
        --font-en: 'Roboto', sans-serif;
        --font-ar: 'Cairo', sans-serif;
        --primary-color: #005A9C;
        --secondary-color: #333333;
        --text-color: #4a4a4a;
        --light-bg-color: #f7f9fc;
        --border-color: #e0e5ec;
        --meta-text-color: #888888;
        --highlight-bg: #fff176;
        --highlight-text: #333;
        --heading-icon-color: #00838F;
    }

    /* --- Page Layout & Numbering --- */
    @page {
        size: A4;
        margin: 2.5cm;
    }
    @page main-content {
        /* Keep header clean to avoid visual repetition of the title on every page */
        @top-center { content: normal; }
        @bottom-center { content: 'تم إنشاؤه بواسطة @Al_Madina_Bot  |  صفحة ' counter(page); font-family: var(--font-main); font-size: 9pt; color: var(--meta-text-color); }
    }
    @page :first {
        @top-center { content: normal; }
        @bottom-center { content: normal; }
    }

    body { font-family: var(--font-main); color: var(--text-color); line-height: 1.8; }
    
    /* --- Cover Page Styling --- */
    .cover-page {
        page: cover;
        display: flex; flex-direction: column; justify-content: center; align-items: center;
        height: 100%; text-align: center; background-color: var(--primary-color); color: white;
    }
    .cover-title {
        font-family: var(--font-ar); font-size: 36pt; font-weight: 800;
        margin: 0; border-bottom: 3px solid white; padding-bottom: 20px;
    }
    .cover-meta {
        font-family: var(--font-en); margin-top: 30px; font-size: 12pt; opacity: 0.8;
    }
    .main-content { page: main-content; direction: rtl; }
    .main-content.ltr { direction: ltr; }

    /* --- General Typography --- */
    h1.main-title, h2 {
        font-family: var(--font-ar); border-bottom: 2px solid var(--primary-color);
        padding-bottom: 15px;
    }
    h1.main-title {
        color: var(--secondary-color); font-size: 30pt; font-weight: 800;
        text-align: right; margin: 0 0 30px 0;
    }
    h2 {
        color: var(--primary-color); font-size: 19pt; font-weight: 800;
        margin-top: 42px; margin-bottom: 18px;
        background: #eef5ff; padding: 10px 14px; border-radius: 10px;
        border: 1px solid #d7e6ff;
    }
    .main-content.ltr h1.main-title, .main-content.ltr h2 { text-align: left; }

    /* --- ✨ NEW: Bilingual Grid System --- */
    .bilingual-grid {
        display: flex;
        justify-content: space-between;
        margin: 25px 0;
        padding: 15px;
        border: 1px solid var(--border-color);
        border-radius: 10px;
        background-color: var(--light-bg-color);
    }
    .bilingual-col {
        flex: 1 1 48%; /* Each column takes up roughly half the space */
    }
    .bilingual-col-eng {
        direction: ltr;
        text-align: left;
        font-family: var(--font-en);
        padding-right: 15px;
    }
    .bilingual-col-arb {
        direction: rtl;
        text-align: right;
        font-family: var(--font-ar);
        padding-left: 15px;
        border-left: 1px solid var(--border-color); /* Vertical separator */
    }
    .bilingual-col p { margin-bottom: 0; }
    
    /* Styling for the structured summary in Arabic column */
    .summary-title, .details-title {
        font-weight: bold;
        color: var(--heading-icon-color);
        margin-bottom: 5px;
        font-size: 1.1em;
    }
    .details-title {
        margin-top: 15px;
    }


    /* --- Dynamic Icon Headings --- */
    .icon-heading {
        font-family: var(--font-ar); font-weight: 800; font-size: 14pt;
        color: var(--heading-icon-color);
        margin-top: 20px; margin-bottom: 8px;
        padding-right: 35px; position: relative;
        text-align: right;
    }
    .icon-heading::before {
        content: attr(data-icon);
        position: absolute; right: 0; top: 0;
        font-size: 1.5em; width: 30px; text-align: center;
    }
    .icon-content {
        padding-right: 35px; text-align: justify;
        color: var(--text-color); margin-bottom: 1em;
    }
    .main-content.ltr .icon-heading { text-align: left; padding-right: 0; padding-left: 35px; }
    .main-content.ltr .icon-heading::before { right: auto; left: 0; }
    .main-content.ltr .icon-content { padding-right: 0; padding-left: 35px; text-align: left; }

    /* --- Standard bullet lists --- */
    ul.standard { list-style: disc inside; padding-right: 6px; margin: 0 0 1em 0; }
    ul.standard li { margin-bottom: 0.5em; }
    .main-content.ltr ul.standard { padding-left: 6px; }

    /* Emoji lists: keep emoji as the bullet, hide decorative dot */
    .emoji-list li::before { content: ''; }

    /* Ordered (numbered) lists */
    ol { list-style: decimal inside; padding-right: 6px; margin: 0 0 1em 0; }
    .main-content.ltr ol { padding-left: 6px; }
    
    /* --- Other Styling --- */
    strong { font-weight: 800; color: var(--primary-color); }
    b { font-weight: 600; background-color: var(--highlight-bg); color: var(--highlight-text); padding: 2px 6px; border-radius: 4px; }
    blockquote { margin: 20px 0; padding: 15px; background-color: var(--light-bg-color); border-right: 4px solid var(--primary-color); }
    .main-content.ltr blockquote { border-right: none; border-left: 4px solid var(--primary-color); }
    """
    
    def _format_text_to_html(text_chunk: str, is_bilingual_col: bool = False) -> str:
        """
        A universal text formatter that handles icon headings, lists, bold text, and paragraphs.
        """
        processed = text_chunk
        # Hard split: if a paragraph holds multiple "- " bullets inline, force them onto new lines
        processed = re.sub(r"\s-\s(?=[^\n]*-\s)", "\n- ", processed)

        # Helper: split semicolon‑separated ideas into multiple items
        def _split_semicolon_items(s: str) -> list[str]:
            parts = re.split(r"\s*[;؛]\s+", s.strip())
            return [p for p in (part.strip() for part in parts) if p]
        
        # Universal Icon Heading Processor
        def icon_heading_replacer(match):
            icon = match.group(1).strip()
            heading = match.group(2).strip()
            content = match.group(3).strip()
            return f'<p class="icon-heading" data-icon="{icon}">{heading}</p><div class="icon-content">{content}</div>'
        
        processed = re.sub(
            r'^\s*[-•]?\s*([^\w\s"\'<>&])\s*\*\*(.*?)\*\*[:\s]?(.*)',
            icon_heading_replacer,
            processed,
            flags=re.MULTILINE
        )

        # Q&A one‑liner splitter: "❓ question — ✅ answer" → two separate lines
        def qa_splitter(match):
            q = match.group(1).strip()
            a = match.group(2).strip()
            return f'<p><strong>❓ {q}</strong></p>\n<p>✅ {a}</p>'
        processed = re.sub(r'^\s*❓\s*(.*?)\s*[—–-]\s*✅?\s*(.*?)\s*$', qa_splitter, processed, flags=re.MULTILINE)

        # Standard List Processor (hyphen / dot)
        def list_replacer(match):
            items = match.group(0).strip().split('\n')
            li_items_parts = []
            for raw in items:
                txt = raw.strip()[2:].strip()
                if not txt:
                    continue
                segments = _split_semicolon_items(txt)
                if len(segments) <= 1:
                    li_items_parts.append(f'<li>{txt}</li>')
                else:
                    # expand into multiple sibling items (one idea per line)
                    for seg in segments:
                        li_items_parts.append(f'<li>{seg}</li>')
            return f'<ul class="standard">{"".join(li_items_parts)}</ul>'

        processed = re.sub(r'((?:^\s*[-•]\s+.*\s*)+)', list_replacer, processed, flags=re.MULTILINE)

        # Numbered List Processor: lines like "1. ..." or "1) ..."
        def num_list_replacer(match):
            items = match.group(0).strip().split('\n')
            li_items = []
            for it in items:
                it = it.strip()
                it = re.sub(r'^\s*\d+[\.)]\s*', '', it)
                if it:
                    segments = _split_semicolon_items(it)
                    if len(segments) <= 1:
                        li_items.append(f'<li>{it}</li>')
                    else:
                        li_items.extend([f'<li>{seg}</li>' for seg in segments])
            return f'<ol>{"".join(li_items)}</ol>'

        processed = re.sub(r'((?:^\s*\d+[\.)]\s+.*\s*)+)', num_list_replacer, processed, flags=re.MULTILINE)

        # Emoji List Processor: consecutive lines starting with an emoji
        EMOJI_RE = r'(?:✅|⚠️|💡|📌|🧠|🔍|🔎|📈|📚|🧩|🎯|🚀|📖|🏥|🔬|📝|📊|🔄|❓|#️⃣|🗂️)'
        def emoji_list_replacer(match):
            items = match.group(0).split('\n')
            li_items = []
            for it in items:
                t = it.strip()
                if not t:
                    continue
                m = re.match(rf'^\s*{EMOJI_RE}\s*', t)
                emoji_prefix = m.group(0).strip() if m else ''
                body = t[len(m.group(0)):] if m else t
                segments = _split_semicolon_items(body)
                if len(segments) <= 1:
                    li_items.append(f'<li>{t}</li>')
                else:
                    # replicate emoji for each split segment
                    for seg in segments:
                        li_items.append(f'<li>{emoji_prefix} {seg}</li>')
            return f'<ul class="emoji-list">{"".join(li_items)}</ul>'

        processed = re.sub(rf'((?:^\s*{EMOJI_RE}\s+.*\s*)+)', emoji_list_replacer, processed, flags=re.MULTILINE)
        
        # Process any remaining Markdown bold
        processed = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', processed)

        # Wrap remaining text blocks in <p> tags
        # Exclude lines that have already been converted to HTML
        if not is_bilingual_col:
            lines = processed.split('\n')
            final_lines = []
            for line in lines:
                if line.strip() and not line.strip().startswith('<'):
                    final_lines.append(f'<p>{line.strip()}</p>')
                else:
                    final_lines.append(line)
            processed = "\n".join(final_lines)

        return processed.replace("<p><ul>", "<ul>").replace("</ul></p>", "</ul>")


    def process_content_to_html(raw_content: str) -> str:
        # Pre-normalization helpers for English-only summaries
        def _explode_inline_bullets_text(s: str) -> str:
            if not s:
                return s
            BULLET_START = "📚📖🧠💡📌📝📊✅⚠️🔎🔍🚀🎯🧩🔣🧮🔄#"
            s = re.sub(rf"\s-\s(?=(?:[{BULLET_START}]|[A-Z0-9]))", "\n- ", s)
            s = re.sub(rf"\s-([{BULLET_START}])", r"\n- \1", s)
            s = re.sub(r"([\.!?،؛])\s-\s+", r"\1\n- ", s)
            return s

        def _remove_exec_snapshot(s: str) -> str:
            # Remove <h2>Executive Snapshot</h2> ... until next <h2> or end
            s = re.sub(r"<h2>\s*Executive Snapshot\s*</h2>.*?(?=<h2>|\Z)", "", s, flags=re.DOTALL | re.IGNORECASE)
            # Also plain text heading
            s = re.sub(r"(?:^|\n)\s*Executive Snapshot\s*\n.*?(?=(?:\n\s*<h2>)|\Z)", "\n", s, flags=re.DOTALL | re.IGNORECASE)
            return s

        def _collapse_contents_block(s: str) -> str:
            # Match Contents/Document Contents/Arabic and capture following non-heading lines
            def repl(m):
                block = m.group(0)
                header = m.group('hdr')
                body = m.group('body')
                # take non-empty lines that are not h2
                items = []
                for ln in body.splitlines():
                    t = ln.strip().strip('-•')
                    if not t:
                        continue
                    if t.lower().startswith('executive snapshot'):
                        continue
                    if t.startswith('<h2>'):
                        break
                    items.append(t)
                if not items:
                    return ''
                enum = ' · '.join(f"{i+1}) {it}" for i, it in enumerate(items))
                return enum + "\n"

            pat = re.compile(r"(?P<hdr>^(?:Contents|Document Contents|محتويات المستند|محتويات)\s*$)\n(?P<body>(?:.(?!^<h2>))*?)", re.MULTILINE | re.DOTALL | re.IGNORECASE)
            return pat.sub(repl, s)

        # Apply pre-normalization for messy paragraphs
        base_content = raw_content.replace('└─', '').replace('├─', '').replace('│', '')
        base_content = _explode_inline_bullets_text(base_content)
        base_content = _remove_exec_snapshot(base_content)
        base_content = _collapse_contents_block(base_content)
        # Process paired bilingual blocks using the new grid system
        def process_bilingual_block(match):
            eng_text = match.group(1).strip()
            arb_text = match.group(2).strip()

            # ✨ Improved: Robustly detect and style Arabic section labels even with emojis/bold
            # Matches forms like: "**✅ الخلاصة:**", "✅ الخلاصة:", "**التفاصيل:**", etc.
            def style_arb_sections(s: str) -> str:
                s = s or ""
                # Add an opening <p> if not already HTML
                if not re.match(r"\s*<", s):
                    s = "<p>" + s
                # Summary
                s = re.sub(r"\*{0,2}\s*(?:✅\s*)?الخلاصة\s*:\s*", '<p class="summary-title">✅ الخلاصة:</p><p>', s, flags=re.IGNORECASE)
                # Details
                s = re.sub(r"\*{0,2}\s*(?:🔍\s*)?التفاصيل\s*:\s*", '</p><p class="details-title">🔍 التفاصيل:</p><p>', s, flags=re.IGNORECASE)
                # Ensure a closing paragraph
                if not s.strip().endswith("</p>"):
                    s += "</p>"
                # Clean empty paragraphs
                s = re.sub(r"<p>\s*</p>", "", s)
                return s

            arb_html = style_arb_sections(arb_text)

            # Format the English text simply, wrapping in paragraphs
            eng_html = "\n".join([f'<p>{line.strip()}</p>' for line in eng_text.split('\n') if line.strip()])

            return (f'<div class="bilingual-grid">'
                    f'<div class="bilingual-col bilingual-col-arb">{arb_html}</div>' # Arabic on the right
                    f'<div class="bilingual-col bilingual-col-eng">{eng_html}</div>' # English on the left
                    f'</div>')
        
        # --- Avoid duplication: build output from parts rather than replacing in-place ---
        pattern = re.compile(r'\[ENG\](.*?)\[/ENG\]\s*\[ARB\](.*?)\[/ARB\]', flags=re.DOTALL | re.IGNORECASE)

        # Extract optional conclusion first and remove it from the base content
        # Start from normalized content
        base_content = base_content
        conc_match = re.search(r'\[CONCLUSION\](.*?)\[/CONCLUSION\]', base_content, flags=re.DOTALL | re.IGNORECASE)
        conclusion_html = ""
        if conc_match:
            conc_raw = conc_match.group(1).strip()
            # Light restructuring for common labels
            conc = conc_raw
            conc = re.sub(r'\*\*Thesis Statement\s*/\s*The Big Idea[^:]*:\s*', '🎯 الخلاصة الكبرى: ', conc, flags=re.IGNORECASE)
            conc = re.sub(r'\*\*Why It Matters[^:]*:\s*', '🚀 لماذا يهم: ', conc, flags=re.IGNORECASE)
            conclusion_html = '<h2>الخلاصة النهائية</h2>' + _format_text_to_html(conc)
            # Remove conclusion block from the base content to prevent duplication
            base_content = re.sub(r'\[CONCLUSION\].*?\[/CONCLUSION\]', '', base_content, flags=re.DOTALL | re.IGNORECASE)

        # Build bilingual blocks HTML (if any)
        matches = list(pattern.finditer(base_content))
        blocks_html = ''.join(process_bilingual_block(m) for m in matches)
        # Remaining content outside bilingual blocks
        remaining_content = pattern.sub('', base_content).strip()

        processed = ""
        if remaining_content:
            processed += _format_text_to_html(remaining_content)
        # Append the converted bilingual blocks after the remaining content
        if blocks_html:
            processed += ("\n" + blocks_html if processed else blocks_html)

        # Append conclusion (if any) at the end
        if conclusion_html:
            processed = processed + "\n" + conclusion_html
        
        return processed

    # --- PDF Generation Logic ---
    full_text_content = "\n".join(lines)
    
    main_title = title
    h1_match = re.search(r'<h1>(.*?)</h1>', full_text_content, re.IGNORECASE | re.DOTALL)
    if h1_match:
        main_title = h1_match.group(1).strip()
        # Remove the H1 tag from the content to avoid duplication
        full_text_content = full_text_content.replace(h1_match.group(0), "", 1)
    
    final_css = css.replace('{escaped_title}', main_title.replace("'", "\\'"))
    
    html_body = process_content_to_html(full_text_content)
    lang_class = "ltr" if lang == 'en' else ""
    
    final_html = f"""
    <!doctype html>
    <html>
        <head>
            <meta charset="utf-8"><title>{_escape_html(main_title)}</title><style>{final_css}</style>
        </head>
        <body>
            <div class="cover-page">
                <h1 class="cover-title">{_escape_html(main_title)}</h1>
                <p class="cover-meta">Generated by @{author_username}<br/>{datetime.now().strftime('%Y-%m-%d')}</p>
            </div>
            <div class="main-content {lang_class}">
                {html_body}
            </div>
        </body>
    </html>"""
    
    try:
        pdf_bytes = weasyprint.HTML(string=final_html).write_pdf()
        return io.BytesIO(pdf_bytes), f"premium_document_{uuid.uuid4().hex[:8]}.pdf"
    except Exception as e:
        logger.error(f"PREMIUM PDF FAILED: {e}", exc_info=True)
        escaped_text = _escape_html(full_text_content)
        minimal_html = f"<html><body><h1>{_escape_html(main_title)}</h1><pre>{escaped_text}</pre></body></html>"
        pdf_bytes = weasyprint.HTML(string=minimal_html).write_pdf()
    return io.BytesIO(pdf_bytes), f"fallback_document.pdf"


def build_text_to_pdf(
    title: str,
    author_username: str,
    *,
    lines: List[str],
    theme: str = 'midnight'
) -> tuple[io.BytesIO, str]:
    """Premium single-document template for the Text→PDF feature."""

    safe_title = _escape_html(title or 'Study Notes')
    clean_lines = [str(ln or '').rstrip() for ln in (lines or [])]
    if not any(ln.strip() for ln in clean_lines):
        clean_lines = ["No content provided."]

    word_count = sum(len(re.findall(r"[\w\u0600-\u06FF']+", ln)) for ln in clean_lines)
    bullet_count = sum(1 for ln in clean_lines if ln.strip().startswith(('- ', '•', '▪', '–', '—', '*', '❓', '✅', '⚠️', '🔥', '🎯', '🧠', '🧪', '🚀', '📌')))
    paragraph_count = max(1, sum(1 for ln in clean_lines if ln.strip() and not ln.strip().startswith(('- ', '•', '▪', '–', '—', '*', '❓', '✅', '⚠️', '🔥', '🎯', '🧠', '🧪', '🚀', '📌'))))

    def _seg_type(line: str) -> str:
        stripped = line.strip()
        if not stripped:
            return 'blank'
        if stripped.startswith(('# ', '## ')):
            return 'heading'
        if stripped.startswith(('### ', '#### ')):
            return 'subheading'
        if stripped.startswith(('- ', '•', '▪', '–', '—', '*', '❓', '✅', '⚠️', '🔥', '🎯', '🧠', '🧪', '🚀', '📌')):
            return 'bullet'
        if stripped.endswith(':') and len(stripped) <= 60:
            return 'heading'
        if len(stripped) <= 52 and stripped.isupper():
            return 'heading'
        return 'paragraph'

    blocks: List[dict] = []
    current_list: List[str] | None = None
    for raw in clean_lines:
        kind = _seg_type(raw)
        text = raw.strip()
        if kind == 'blank':
            if current_list:
                blocks.append({'type': 'list', 'items': current_list})
                current_list = None
            continue
        if kind == 'bullet':
            if current_list is None:
                current_list = []
            marker_removed = re.sub(r"^[-•▪–—*\s]+", '', text, count=1).strip()
            current_list.append(marker_removed)
            continue
        if current_list:
            blocks.append({'type': 'list', 'items': current_list})
            current_list = None
        if kind == 'heading':
            heading_text = text.lstrip('#').strip(' :')
            blocks.append({'type': 'heading', 'text': heading_text})
        elif kind == 'subheading':
            heading_text = text.lstrip('#').strip()
            blocks.append({'type': 'subheading', 'text': heading_text})
        else:
            blocks.append({'type': 'paragraph', 'text': text})
    if current_list:
        blocks.append({'type': 'list', 'items': current_list})

    heading_chips = [blk['text'] for blk in blocks if blk['type'] in {'heading', 'subheading'}][:5]
    if not heading_chips:
        heading_chips = ["Study Essentials", "Quick Review", "Action Points"]

    def _auto_style_text(text: str) -> str:
        html = _allow_basic_html(text)
        match = re.match(r"([^:：]+)([:：])(.*)", html)
        if match and len(match.group(1).strip()) <= 56:
            lead = match.group(1).strip()
            rest = match.group(3).strip()
            html = f"<b>{lead}</b>{match.group(2)}{(' ' + rest) if rest else ''}"
        html = re.sub(r"(?<![\w>])(\d+(?:[\.,]\d+)?)", r"<span class='num'>\1</span>", html)
        return html

    sections_html: List[str] = []
    for blk in blocks:
        if blk['type'] == 'heading':
            sections_html.append(f"<h2>{_escape_html(blk['text'])}</h2>")
        elif blk['type'] == 'subheading':
            sections_html.append(f"<h3>{_escape_html(blk['text'])}</h3>")
        elif blk['type'] == 'list':
            items_html = ''.join(f"<li>{_auto_style_text(item)}</li>" for item in blk['items'] if item)
            sections_html.append(f"<ul class='modern-list'>{items_html}</ul>")
        else:
            sections_html.append(f"<p class='body-text'>{_auto_style_text(blk['text'])}</p>")

    chip_html = ''.join(f"<span class='chip'>{_escape_html(chip)}</span>" for chip in heading_chips)
    meta_html = (
        f"<div class='meta-item'><span class='meta-label'>Words</span><span class='meta-value'>{word_count}</span></div>"
        f"<div class='meta-item'><span class='meta-label'>Highlights</span><span class='meta-value'>{bullet_count}</span></div>"
        f"<div class='meta-item'><span class='meta-label'>Paragraphs</span><span class='meta-value'>{paragraph_count}</span></div>"
    )

    css = """
    @page { size: A4; margin: 1.6cm; }
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&family=Tajawal:wght@400;500;700&display=swap');
    body {
        margin: 0;
        font-family: 'Poppins','Tajawal',sans-serif;
        background: linear-gradient(135deg,#0f172a,#1e293b);
        color: #0f172a;
    }
    .page {
        background: #ffffff;
        border-radius: 24px;
        padding: 48px 58px;
        box-shadow: 0 22px 60px rgba(15,23,42,0.22);
    }
    .hero {
        background: linear-gradient(120deg,#3b82f6,#7c3aed);
        color: #ffffff;
        border-radius: 22px;
        padding: 32px 36px;
        box-shadow: 0 16px 40px rgba(59,130,246,0.28);
    }
    .hero-title {
        font-size: 32pt;
        font-weight: 700;
        margin: 0;
        letter-spacing: -0.01em;
    }
    .hero-sub {
        margin-top: 10px;
        font-size: 12pt;
        font-weight: 500;
        opacity: 0.9;
    }
    .hero-meta {
        margin-top: 18px;
        display: flex;
        flex-wrap: wrap;
        gap: 14px;
        font-size: 11pt;
    }
    .hero-meta .tag {
        background: rgba(255,255,255,0.18);
        padding: 6px 14px;
        border-radius: 999px;
        font-weight: 600;
        border: 1px solid rgba(255,255,255,0.28);
    }
    .chips {
        margin: 26px 0 14px;
        display: flex;
        flex-wrap: wrap;
        gap: 12px;
    }
    .chip {
        background: linear-gradient(135deg,#eef2ff,#e0e7ff);
        color: #1d4ed8;
        border-radius: 16px;
        padding: 8px 16px;
        font-weight: 600;
        font-size: 11pt;
        border: 1px solid rgba(59,130,246,0.22);
    }
    .metrics {
        margin: 24px 0 32px;
        display: grid;
        grid-template-columns: repeat(auto-fit,minmax(140px,1fr));
        gap: 18px;
    }
    .meta-item {
        background: #f8fafc;
        border: 1px solid rgba(148,163,184,0.35);
        border-radius: 18px;
        padding: 14px 18px;
        text-align: center;
    }
    .meta-label {
        display: block;
        font-size: 10pt;
        letter-spacing: 0.12em;
        color: #64748b;
        text-transform: uppercase;
    }
    .meta-value {
        display: block;
        font-size: 20pt;
        font-weight: 700;
        color: #0f172a;
        margin-top: 6px;
    }
    h2 {
        margin: 36px 0 18px;
        font-size: 18pt;
        font-weight: 700;
        letter-spacing: 0.02em;
        color: #1e1b4b;
        position: relative;
        padding-left: 22px;
    }
    h2::before {
        content: '';
        position: absolute;
        left: 0;
        top: 50%;
        transform: translateY(-50%);
        width: 8px;
        height: 32px;
        border-radius: 6px;
        background: linear-gradient(180deg,#6366f1,#22d3ee);
    }
    h3 {
        margin: 28px 0 12px;
        font-size: 15pt;
        font-weight: 600;
        color: #312e81;
    }
    .body-text {
        font-size: 12.4pt;
        line-height: 1.95;
        color: #1f2937;
        margin: 0 0 16px 0;
    }
    .body-text b { color: #111827; }
    .body-text .num {
        background: linear-gradient(135deg,#fde68a,#f59e0b);
        color: #92400e;
        padding: 2px 6px;
        border-radius: 8px;
        font-weight: 700;
    }
    .modern-list {
        margin: 0 0 22px 0;
        padding-inline-start: 24px;
    }
    .modern-list li {
        margin: 10px 0;
        font-size: 12.2pt;
        line-height: 1.9;
        padding: 6px 12px;
        background: linear-gradient(135deg,#f8fafc,#e0f2fe);
        border-radius: 14px;
        border: 1px solid rgba(59,130,246,0.18);
    }
    .modern-list li b { color: #0f172a; }
    .modern-list li .num {
        background: linear-gradient(135deg,#fee2e2,#fecaca);
        color: #991b1b;
    }
    footer {
        margin-top: 40px;
        font-size: 10pt;
        color: #64748b;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    footer .brand {
        font-weight: 600;
        color: #475569;
    }
    """

    generated_on = datetime.now().strftime('%B %d, %Y • %H:%M')
    hero_meta_html = (
        f"<div class='hero-meta'>"
        f"<span class='tag'>@{_escape_html(author_username or 'Al_Madina_Bot')}</span>"
        f"<span class='tag'>{generated_on}</span>"
        f"<span class='tag'>Auto-generated sheet</span>"
        f"</div>"
    )

    html = f"""
    <!doctype html>
    <html>
    <head>
        <meta charset='utf-8'>
        <title>{safe_title}</title>
        <style>{css}</style>
    </head>
    <body>
        <div class='page'>
            <section class='hero'>
                <h1 class='hero-title'>{safe_title}</h1>
                <div class='hero-sub'>Sculpted by Al Madina Intelligent Study Engine</div>
                {hero_meta_html}
            </section>
            <div class='chips'>{chip_html}</div>
            <div class='metrics'>{meta_html}</div>
            {''.join(sections_html)}
            <footer>
                <span class='brand'>Al Madina Al Taalimia • Smart Study Tools</span>
                <span>Generated on {generated_on}</span>
            </footer>
        </div>
    </body>
    </html>
    """

    pdf_bytes = weasyprint.HTML(string=html).write_pdf()
    bio = io.BytesIO(pdf_bytes)
    bio.name = f"text_sheet_{uuid.uuid4().hex[:8]}.pdf"
    bio.seek(0)
    return bio, bio.name


def build_summary_pdf_v2(
    title: str,
    author_username: str,
    lines: List[str],
    *,
    lang: str = 'en'
) -> tuple[io.BytesIO, str]:
    """Brand-new summary template (PDF 2):
    - Clean cover with subtitle
    - Compact inline table of contents (single line, chips)
    - Section blocks with emoji-leading bullets and generous spacing
    - Tight paragraphs; consistent fonts; improved readability for study
    """
    content = "\n".join(lines or [])

    css = """
    @page { size: A4; margin: 1.8cm; }
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&family=Cairo:wght@400;600;800&display=swap');
    body { font-family: 'Inter','Cairo',sans-serif; background: linear-gradient(135deg,#f8fafc,#eef2ff); color:#0f172a; }
    .wrap {
        background: linear-gradient(180deg,#ffffff 0%,#f7f9ff 100%);
        border-radius:24px;
        padding:40px 44px;
        border:1px solid rgba(148,163,184,0.22);
    }
    .cover { text-align:center; margin-bottom: 28px; }
    .cover h1 { font-size: 30pt; margin: 0 0 12px 0; color:#0b1120; letter-spacing:-0.01em; text-shadow:0 6px 14px rgba(15,23,42,0.25); }
    .cover .meta { color:#64748b; font-size:11pt; text-transform:uppercase; letter-spacing:0.14em; }
    .chips { margin: 16px 0 30px; display:flex; flex-wrap:wrap; gap:12px; justify-content:center; }
    .chip {
        display:inline-flex; align-items:center; gap:8px;
        background:rgba(59,130,246,0.18);
        border:1px solid rgba(59,130,246,0.32);
        color:#1d4ed8; padding:6px 16px;
        border-radius:999px; font-weight:600;
    }
    .chip::before { content:'⬡'; font-size:10pt; color:#1d4ed8; }
    h2 { font-size: 19pt; margin: 34px 0 14px; color:#0f172a; display:flex; align-items:center; gap:12px; position:relative; padding-left:20px; text-transform:uppercase; letter-spacing:0.08em; }
    h2::before { content:'◆'; color:#3b82f6; font-size:16pt; position:absolute; left:0; text-shadow:0 4px 10px rgba(59,130,246,0.35); }
    p { margin: 0 0 14px 0; line-height:1.92; font-size:11.6pt; }
    ul { margin: 0 0 22px 0; padding-inline-start: 28px; }
    ul li { margin: 10px 0; font-size:11.5pt; line-height:1.88; }
    ul li::marker { color:#0ea5e9; font-size:0.9em; }
    .lead { color:#1f2937; font-size:11.9pt; font-weight:500; letter-spacing:0.012em; }
    .subheading { font-size:17pt; font-weight:700; color:#1d4ed8; margin:28px 0 16px; letter-spacing:0.035em; }
    .focus-line { display:block; font-weight:600; letter-spacing:0.01em; }
    .focus-line.focus-en { direction:ltr; text-align:left; font-family:'Inter','Cairo',sans-serif; }
    .focus-line.focus-ar { direction:rtl; text-align:right; font-family:'Cairo','Inter',sans-serif; }
    .qa {
        background:linear-gradient(135deg,#f8fafc,#dbeafe);
        border:1px solid rgba(59,130,246,0.28);
        border-radius:18px; padding:20px 22px; margin:20px 0;
    }
    .qa .q { font-weight:700; color:#0f172a; margin:0 0 8px; font-size:12pt; }
    .qa .a { margin:0; color:#1f2937; font-size:11.5pt; line-height:1.9; }
    .flow { display:flex; flex-wrap:wrap; gap:14px; margin:22px 0; }
    .flow span {
        background:linear-gradient(135deg,#fde68a,#f59e0b);
        color:#92400e; padding:9px 20px;
        border-radius:999px; font-weight:600; line-height:1.9;
    }
    .fact {
        background:linear-gradient(135deg,#e0f2fe,#bae6fd);
        border-left:6px solid #0369a1;
        padding:16px 18px; margin:18px 0;
        border-radius:18px;
    }
    .fact strong { color:#0e7490; letter-spacing:0.08em; }
    .divider { height:1px; background:linear-gradient(90deg,rgba(148,163,184,0),rgba(148,163,184,0.55),rgba(148,163,184,0)); margin:30px 0; }
    .em {
        background:linear-gradient(135deg,#fee2e2,#fecaca);
        padding:3px 10px; border-radius:10px;
        font-weight:700; color:#991b1b;
    }
    .hl-term {
        background:linear-gradient(135deg,#dbeafe,#bfdbfe);
        color:#1d4ed8; padding:4px 12px;
        border-radius:12px; font-weight:700;
        display:inline-block; margin-right:8px;
    }
    .hl-math {
        background:linear-gradient(135deg,#ede9fe,#ddd6fe);
        color:#5b21b6; padding:3px 10px;
        border-radius:10px; font-weight:700;
    }
    blockquote.deep-quote {
        margin: 22px 0;
        padding: 20px 24px;
        background:linear-gradient(135deg,#fef3c7,#fde68a);
        border-radius:18px;
        border:1px solid rgba(234,179,8,0.45);
        color:#7c2d12;
        font-style:italic;
        line-height:2.0;
    }
    """

    # Detect a one-line inline TOC from the first few lines if present (already normalized by upstream)
    inline_toc = None
    for ln in lines[:8]:
        t = (ln or '').strip()
        if t and re.match(r"^\d+\)\s", t):
            inline_toc = t
            break

    # Build sections: split by H2 if present, else by known headings words or leave as single section
    html_parts: List[str] = []
    html_parts.append(f"<div class='cover'><h1>{_escape_html(title)}</h1><div class='meta'>by @{_escape_html(author_username)}</div></div>")
    if inline_toc:
        # Turn inline TOC into pill chips
        items = [x.strip() for x in re.split(r"\s·\s", inline_toc) if x.strip()]
        chips = ''.join(f"<span class='chip'>{_escape_html(it)}</span>" for it in items)
        html_parts.append(f"<div class='chips'>{chips}</div>")

    SECTION_HEADINGS = {
        'Complete Outline', 'Concepts & Definitions', 'Definitions', 'Key Facts & Numbers',
        'Symbols & Notation', 'Formulas & Calculations', 'Processes & Steps',
        'Examples & Analogies', 'Common Pitfalls', 'Q&A Checkpoints', 'Final Takeaway',
        'المخطط الكامل', 'المفاهيم والتعاريف', 'التعريفات', 'حقائق وأرقام', 'الرموز والاصطلاحات',
        'معادلات وحسابات', 'العمليات والخطوات', 'أمثلة وتشبيهات', 'مزالق شائعة',
        'أسئلة ومراجعات', 'الخلاصة النهائية'
    }

    def parse_sections(lines: List[str]) -> List[Dict[str, List[str]]]:
        sections: List[Dict[str, List[str]]] = []
        current = {'title': None, 'items': []}
        SKIP_TITLES = {'complete outline', 'المخطط الكامل'}
        lower_titles = {h.lower() for h in SECTION_HEADINGS}
        skipping = False
        for ln in lines:
            s = (ln or '').strip()
            if not s:
                continue
            low = s.lower()
            is_heading = (s in SECTION_HEADINGS) or (low in lower_titles) or re.match(r"^<h2>.*</h2>$", s, flags=re.IGNORECASE)
            if is_heading:
                title_text = re.sub(r"<.?h2>", "", s, flags=re.IGNORECASE)
                title_text = title_text if title_text else s
                if current['items'] and not skipping:
                    sections.append(current)
                skipping = title_text and title_text.lower() in SKIP_TITLES
                current = {'title': title_text if not skipping else None, 'items': []}
                continue
            if skipping:
                continue
            current.setdefault('items', []).append(s)
        if current['items'] and not skipping:
            sections.append(current)
        return [sec for sec in sections if sec.get('title')]

    HIGHLIGHT_PHRASES = [
        'Prevalence Rate', 'Incidence Rate', 'Prevalence Ratio', 'Prevalence Odds Ratio',
        'Cross-sectional study', 'Case-control study', 'Cohort study',
        'Confidence Interval', 'Temporal relationship', 'Risk factor',
        'Public health planning', 'Hypothesis generation'
    ]
    HIGHLIGHT_WORDS = [
        'Prevalence', 'Incidence', 'Odds Ratio', 'Risk', 'Cross-sectional',
        'Study', 'Case-control', 'Cohort', 'Exposure', 'Outcome',
        'Rate', 'Ratio', 'Duration', 'Etiology', 'Bias', 'Sensitivity',
        'Specificity', 'Hypothesis', 'Causality', 'Temporal', 'Distribution'
    ]
    WORD_PATTERN = re.compile(r'\b(' + '|'.join(re.escape(w) for w in HIGHLIGHT_WORDS) + r')\b', flags=re.IGNORECASE)
    PHRASE_PATTERNS = [re.compile(re.escape(p), flags=re.IGNORECASE) for p in sorted(HIGHLIGHT_PHRASES, key=len, reverse=True)]
    EQUATION_PATTERN = re.compile(r'([A-Za-z][A-Za-z\s]{0,12}=\s*[^<\n]+)')

    def _highlight_terms_html(html_text: str) -> str:
        if not html_text:
            return html_text
        parts = re.split(r'(<[^>]+>)', html_text)
        for idx, part in enumerate(parts):
            if not part or part.startswith('<'):
                continue
            text = part
            placeholders = []
            token_counter = 0
            for pattern in PHRASE_PATTERNS:
                def repl(match):
                    nonlocal token_counter
                    token = f"@@PHRASE{token_counter}@@"
                    placeholders.append((token, match.group(0)))
                    token_counter += 1
                    return token
                text = pattern.sub(repl, text)
            text = WORD_PATTERN.sub(lambda m: f"<span class='em'>{m.group(0)}</span>", text)
            for token, original in placeholders:
                text = text.replace(token, f"<span class='hl-term'>{original}</span>")
            parts[idx] = text
        return ''.join(parts)

    def _highlight_equations_html(html_text: str) -> str:
        if not html_text:
            return html_text
        parts = re.split(r'(<[^>]+>)', html_text)
        for idx, part in enumerate(parts):
            if not part or part.startswith('<'):
                continue
            parts[idx] = EQUATION_PATTERN.sub(lambda m: f"<span class='hl-math'>{m.group(0).strip()}</span>", part)
        return ''.join(parts)

    def _format_segment(raw: str, *, prefix: str | None = None) -> str:
        txt = _allow_basic_html(raw or '')
        if prefix and not txt.strip().startswith(prefix):
            txt = f"{prefix} {txt.strip()}"
        txt = _highlight_terms_html(txt)
        txt = _highlight_equations_html(txt)
        return txt

    def render_items(items: List[str]) -> str:
        out: List[str] = []
        i = 0
        n = len(items)
        while i < n:
            raw = items[i]
            s = raw.strip()
            # Subheadings
            if re.match(r"^<h3>.*</h3>$", s, flags=re.IGNORECASE):
                sub = re.sub(r"</?h3>", "", s, flags=re.IGNORECASE).strip()
                out.append(f"<div class='subheading'>{_escape_html(sub)}</div>")
                i += 1
                continue
            # Blockquotes / insights
            if re.match(r"^<blockquote>.*</blockquote>$", s, flags=re.IGNORECASE):
                inner = re.sub(r"</?blockquote>", "", s, flags=re.IGNORECASE)
                out.append(f"<blockquote class='deep-quote'>{_format_segment(inner)}</blockquote>")
                i += 1
                continue
            # Lists (emoji / hyphen / numbered)
            if re.match(r"^[\d\u0660-\u0669]+[\.)\-]?\s+", s) or re.match(r"^(?:[-•–—▪︎·])\s+", s) or re.match(r"^[📚📖🧠💡📌📝📊✅⚠️🔎🔍🚀🎯🧩]", s):
                bullets = []
                while i < n:
                    cur = items[i].strip()
                    if not (re.match(r"^[\d\u0660-\u0669]+[\.)\-]?\s+", cur) or re.match(r"^(?:[-•–—▪︎·])\s+", cur) or re.match(r"^[📚📖🧠💡📌📝📊✅⚠️🔎🔍🚀🎯🧩]", cur)):
                        break
                    entry = re.sub(r"^[\d\u0660-\u0669]+[\.)\-]?\s+", '', cur)
                    entry = re.sub(r"^(?:[-•–—▪︎·])\s+", '', entry)
                    if not re.match(r"^[📚📖🧠💡📌📝📊✅⚠️🔎🔍🚀🎯🧩#]", entry):
                        entry = f"📚 {entry}"
                    bullets.append(_format_segment(entry))
                    i += 1
                out.append('<ul>' + ''.join(f"<li>{x}</li>" for x in bullets) + '</ul>')
                continue
            # Q&A blocks
            if s.startswith('❓'):
                question = s
                answer = ''
                if i + 1 < n and items[i+1].strip().startswith('✅'):
                    answer = items[i+1].strip()
                    i += 1
                out.append(
                    "<div class='qa'>"
                    f"<p class='q'>{_format_segment(question)}</p>"
                    f"<p class='a'>{_format_segment(answer)}</p>"
                    "</div>"
                )
                i += 1
                continue
            # Process flow (arrows)
            if '→' in s or '->' in s:
                steps = [seg.strip() for seg in re.split(r"→|->", s) if seg.strip()]
                out.append("<div class='flow'>" + ''.join(f"<span>{_format_segment(step)}</span>" for step in steps) + "</div>")
                i += 1
                continue
            # Fact boxes (# ...)
            if s.startswith('#'):
                fact = s.lstrip('#').strip()
                out.append(f"<div class='fact'><strong>FACT</strong> {_format_segment(fact)}</div>")
                i += 1
                continue
            out.append(f"<p class='lead'>{_format_segment(s)}</p>")
            i += 1
        return ''.join(out)

    sections = parse_sections(lines)
    for idx, section in enumerate(sections):
        title = section.get('title')
        if title:
            html_parts.append(f"<h2>{_escape_html(title)}</h2>")
        html_parts.append(render_items(section.get('items', [])))
        if idx != len(sections) - 1:
            html_parts.append("<div class='divider'></div>")

    html = f"<!doctype html><html><head><meta charset='utf-8'><style>{css}</style></head><body><div class='wrap'>{''.join(html_parts)}</div></body></html>"
    pdf = weasyprint.HTML(string=html).write_pdf()
    bio = io.BytesIO(pdf)
    bio.name = f"summary_v2_{uuid.uuid4().hex[:8]}.pdf"
    bio.seek(0)
    return bio, bio.name


def build_study_pro_pdf(
    title: str,
    author_username: str,
    lines: List[str]
) -> tuple[io.BytesIO, str]:
    """Build a study‑ready PDF with multi‑level Table of Contents (H2/H3) and back‑to‑contents links."""
    content = "\n".join(lines or [])

    # Parse H2/H3 and assign stable IDs
    h2_list: list[tuple[int, str]] = []
    h3_map: dict[int, list[tuple[int, str]]] = {}

    # Assign IDs to H2
    def _assign_h2_id(match):
        idx = len(h2_list) + 1
        text = (match.group(1) or '').strip()
        h2_list.append((idx, text))
        return f'<h2 id="sec2_{idx}">{text}</h2>'

    content = re.sub(r'<h2>(.*?)</h2>', _assign_h2_id, content, flags=re.IGNORECASE | re.DOTALL)

    # For each H3, attach under the latest H2
    current_h2_idx = 0
    parts = re.split(r'(<h2 id="sec2_\d+">.*?</h2>)', content, flags=re.IGNORECASE | re.DOTALL)
    rebuilt: list[str] = []
    for part in parts:
        if not part:
            continue
        m2 = re.search(r'<h2 id="sec2_(\d+)">', part)
        if m2:
            current_h2_idx = int(m2.group(1))
            rebuilt.append(part)
            continue

        # Replace H3 inside this block, collecting ToC entries
        def _assign_h3_id(m):
            h3_map.setdefault(current_h2_idx, [])
            sub_idx = len(h3_map[current_h2_idx]) + 1
            text = (m.group(1) or '').strip()
            h3_map[current_h2_idx].append((sub_idx, text))
            return f'<h3 id="sec3_{current_h2_idx}_{sub_idx}">{text}</h3>'

        part = re.sub(r'<h3>(.*?)</h3>', _assign_h3_id, part, flags=re.IGNORECASE | re.DOTALL)

        # Inject a back‑to‑toc link after H2/H3 headings
        part = re.sub(r'(</h2>)', r"\1\n<p class='backlink'><a href='#toc'>⬆︎ رجوع للفهرس</a></p>", part)
        part = re.sub(r'(</h3>)', r"\1\n<p class='backlink small'><a href='#toc'>⬆︎ رجوع للفهرس</a></p>", part)
        rebuilt.append(part)

    content_with_ids = ''.join(rebuilt) if rebuilt else content

    # Build nested ToC
    toc_items = []
    for idx, text in h2_list:
        sub_items = ''.join(
            f"<li><a href='#sec3_{idx}_{sub}'>· {_escape_html(txt)}</a></li>"
            for sub, txt in h3_map.get(idx, [])
        )
        sub_html = f"<ul class='sub'>{sub_items}</ul>" if sub_items else ""
        toc_items.append(f"<li><a href='#sec2_{idx}'>{_escape_html(text)}</a>{sub_html}</li>")
    toc_html_list = ''.join(toc_items) or '<li>—</li>'

    css = """
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;800&family=Roboto:wght@400;500;700&display=swap');
    @page { size: A4; margin: 2cm; }
    body { font-family: 'Cairo','Roboto',sans-serif; color:#2f3542; }
    .cover { page: cover; height: 100%; display:flex; align-items:center; justify-content:center; flex-direction:column; background:#0f3460; color:#fff; }
    .cover h1 { font-size: 34pt; margin:0 0 10px 0; }
    .cover .meta { opacity:.9; }
    .toc { page: toc; }
    .toc h2 { color:#0f3460; border-bottom:2px solid #0f3460; padding-bottom:8px; }
    .toc ul { list-style: none; padding:0; margin:0; }
    .toc li { margin:10px 0; }
    .toc ul.sub { margin:6px 0 0 14px; }
    .toc a { color:#1e90ff; text-decoration:none; }
    .toc a:hover { text-decoration:underline; }
    h1, h2, h3 { color:#0f3460; }
    .content h2 { border-bottom:1px solid #dfe6e9; padding-bottom:6px; margin-top:24px; }
    .content h3 { margin-top:18px; }
    .backlink { margin:6px 0 10px; font-size: 10pt; }
    .backlink.small { font-size: 9pt; }
    """

    cover_html = f"""
    <div class='cover'>
      <h1>{_escape_html(title)}</h1>
      <div class='meta'>by @{_escape_html(author_username)}</div>
    </div>
    """
    toc_html = f"""
    <div class='toc'>
      <a id='toc'></a>
      <h2>محتويات المستند</h2>
      <ul>{toc_html_list}</ul>
    </div>
    """
    content_html = f"<div class='content'>{content_with_ids}</div>"

    html = f"<!doctype html><html><head><meta charset='utf-8'><style>{css}</style></head><body>{cover_html}{toc_html}{content_html}</body></html>"
    pdf = weasyprint.HTML(string=html).write_pdf()
    bio = io.BytesIO(pdf)
    bio.name = f"study_pro_{uuid.uuid4().hex[:8]}.pdf"
    bio.seek(0)
    return bio, bio.name

def build_mindmap_text_pdf(
    title: str,
    author_username: str,
    mindmap_content: str
) -> tuple[io.BytesIO, str]:
    css = """
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;700&display=swap');
    @page { size: A4; margin: 1.5cm; }
    body { font-family: 'Cairo', sans-serif; color: #34495E; }
    h1 { color: #2C3E50; font-size: 26pt; text-align: center; border-bottom: 2px solid #005A9C; padding-bottom: 10px; margin-bottom: 25px; }
    pre {
        font-family: 'Cairo', 'Segoe UI', monospace;
        white-space: pre-wrap; word-wrap: break-word;
        background-color: #f7f9fc; border-radius: 8px;
        padding: 20px; font-size: 12pt; line-height: 1.9;
        border: 1px solid #e0e5ec; direction: ltr; text-align: left;
    }
    """
    html_body = f"""
    <h1>🧠 خريطة ذهنية: {_escape_html(title)}</h1>
    <pre>{_escape_html(mindmap_content)}</pre>
    """
    final_html = f"<!doctype html><html><head><meta charset=\"utf-8\"><style>{css}</style></head><body>{html_body}</body></html>"
    bio = io.BytesIO(weasyprint.HTML(string=final_html).write_pdf())
    return bio, f"mindmap_{uuid.uuid4().hex[:8]}.pdf"


def build_dual_language_pdf(
    title: str,
    author_username: str,
    segments: List[Tuple[str, str]],
    glossary: Optional[List[Dict[str, str]]] = None,
    layout: str = 'columns'  # 'columns' or 'stacked'
) -> tuple[io.BytesIO, str]:
    """Generate a polished bilingual PDF.
    layout='columns' → table with EN/AR side by side
    layout='stacked' → per‑segment card with EN on top, AR below (requested)
    """

    css = """
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;800&family=Roboto:wght@400;500;700&display=swap');

    @page { size: A4; margin: 2.2cm; }
    body { font-family: 'Cairo', 'Roboto', sans-serif; color: #2F3542; background-color: #f5f7fb; }
    .wrapper { background: #ffffff; border-radius: 20px; padding: 30px 34px; box-shadow: 0 30px 60px rgba(15, 52, 96, 0.09); }
    .badge { display: inline-block; padding: 6px 14px; border-radius: 999px; background: rgba(71, 181, 255, 0.18); color: #0f3460; font-size: 10pt; margin-bottom: 18px; letter-spacing: 0.5px; }
    .title { font-size: 30pt; font-weight: 800; color: #0f3460; margin: 0 0 8px 0; text-align: right; }
    .meta { font-size: 11pt; color: #57606f; text-align: right; margin-bottom: 28px; }

    /* Stacked cards */
    .segment-card { border: 1px solid #e8eef6; border-radius: 14px; padding: 14px 16px; margin: 12px 0; box-shadow: 0 10px 24px rgba(15,52,96,0.06); background: linear-gradient(180deg,#ffffff, #fbfdff); }
    .seg-idx { font-weight: 700; color: #0f3460; margin-bottom: 8px; }
    .seg-eng { direction: ltr; text-align: left; font-family: 'Roboto', sans-serif; font-size: 11.4pt; }
    .seg-arb { direction: rtl; text-align: right; font-family: 'Cairo', sans-serif; font-size: 12.2pt; margin-top: 8px; border-top: 1px dashed #dfe6e9; padding-top: 8px; }
    .seg-eng p, .seg-arb p { margin: 0 0 8px 0; line-height: 1.65; }

    table { width: 100%; border-collapse: separate; border-spacing: 0 16px; }
    thead th { font-size: 12pt; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; padding: 12px 14px; color: #0f3460; border-bottom: 2px solid rgba(15, 52, 96, 0.18); }
    th.idx { width: 42px; text-align: center; }
    th.eng { text-align: left; direction: ltr; font-family: 'Roboto', sans-serif; }
    th.arb { text-align: right; direction: rtl; font-family: 'Cairo', sans-serif; }

    tr.segment-row { background: linear-gradient(135deg, rgba(71, 181, 255, 0.10), rgba(255, 255, 255, 0.95)); box-shadow: 0 18px 40px rgba(15, 52, 96, 0.08); }
    td { padding: 18px 20px; vertical-align: top; }
    td.idx { font-weight: 700; font-size: 12pt; color: #0f3460; text-align: center; }
    td.eng { direction: ltr; text-align: left; font-family: 'Roboto', sans-serif; font-size: 11.4pt; }
    td.arb { direction: rtl; text-align: right; font-family: 'Cairo', sans-serif; font-size: 12.2pt; border-right: 1px dashed rgba(15, 52, 96, 0.12); }

    td.eng p, td.arb p { margin: 0 0 12px 0; line-height: 1.65; }
    td.eng p:last-child, td.arb p:last-child { margin-bottom: 0; }
    """

    def _convert_lists(text: str) -> str:
        # Convert lines like "1) ..." into ordered lists; lines starting with "- " or "•" to unordered lists
        raw = text or ''
        lines = [ln.rstrip() for ln in raw.split('\n')]
        # Heuristic: convert category lines "X: a, b; Y: c (d, e)" into nested lists
        def as_category_block(line: str) -> Optional[str]:
            # Accept English colon ":" or Arabic verbs like "تشمل/تضم/تشتمل على/تتضمن" and Arabic colon-like usage
            # Normalize Arabic punctuation
            l = line.strip()
            if not l:
                return None
            # Try English-style categories by ';' or '؛'
            # Also split a single line into multiple pseudo-categories by ';' or '؛'
            sep_split = re.split(r'[;؛]', l)
            cats = [c.strip() for c in sep_split if c.strip()]
            if not cats:
                return None
            li_parts = []
            for c in cats:
                # English form: Key: items
                if ':' in c:
                    k, v = c.split(':', 1)
                else:
                    # Arabic verb form: "أنواع الدراسات تشمل/تضم/تشتمل على/تتضمن ..."
                    m = re.search(r'^(?P<k>[^:：]+?)\s*(?:[:：]|(?:تشمل|تضم|تشتمل\s+على|تتضمن)\s*)(?P<v>.+)$', c)
                    if not m:
                        continue
                    k, v = m.group('k'), m.group('v')
                k = _allow_basic_html(k.strip())
                v = v.strip()
                # Replace parentheses lists with commas
                v_norm = re.sub(r'\(([^)]*)\)', r', \1', v)
                # Split by English or Arabic comma
                items = [it.strip() for it in re.split(r'[،,]', v_norm) if it.strip()]
                sub = ''.join(f"<li>{_allow_basic_html(it)}</li>" for it in items)
                li_parts.append(f"<li><strong>{k}</strong><ul>{sub}</ul></li>")
            if not li_parts:
                return None
            return '<ul>' + ''.join(li_parts) + '</ul>'
            li_parts = []
            for c in cats:
                if ':' in c:
                    k, v = c.split(':', 1)
                    k = _allow_basic_html(k.strip())
                    # Split items by commas; also expand parentheses lists
                    v = v.strip()
                    # Replace parentheses groups with commas
                    v_norm = re.sub(r'\(([^)]*)\)', r', \1', v)
                    items = [it.strip() for it in v_norm.split(',') if it.strip()]
                    sub = ''.join(f"<li>{_allow_basic_html(it)}</li>" for it in items)
                    li_parts.append(f"<li><strong>{k}</strong><ul>{sub}</ul></li>")
                else:
                    # Fallback: treat as simple item
                    li_parts.append(f"<li>{_allow_basic_html(c)}</li>")
            return '<ul>' + ''.join(li_parts) + '</ul>' if li_parts else None

        out: List[str] = []
        i = 0
        while i < len(lines):
            ln = lines[i].strip()
            # Category-Style line
            cat_html = as_category_block(ln)
            if cat_html:
                out.append(cat_html)
                i += 1
                continue
            # Numbered (Arabic/Latin numerals) like "1) ...", "١) ...", "1. ...", "١. ..."
            if re.match(r"^[\d\u0660-\u0669]+[\.)\-]?\s+", ln):
                items = []
                while i < len(lines) and re.match(r"^[\d\u0660-\u0669]+[\.)\-]?\s+", lines[i].strip()):
                    items.append(re.sub(r"^[\d\u0660-\u0669]+[\.)\-]?\s+", '', lines[i].strip()))
                    i += 1
                out.append('<ol>' + ''.join(f'<li>{_allow_basic_html(it)}</li>' for it in items) + '</ol>')
                continue
            if re.match(r"^(?:[-•–—▪︎·])\s+", ln):
                items = []
                while i < len(lines) and re.match(r"^(?:[-•–—▪︎·])\s+", lines[i].strip()):
                    items.append(re.sub(r"^(?:[-•–—▪︎·])\s+", '', lines[i].strip()))
                    i += 1
                out.append('<ul>' + ''.join(f'<li>{_allow_basic_html(it)}</li>' for it in items) + '</ul>')
                continue
            # Regular paragraph
            if ln:
                out.append(f'<p>{_allow_basic_html(ln)}</p>')
            i += 1
        return ''.join(out)

    def _column_html(text: str) -> str:
        text = text or ""
        # Keep basic tags and convert simple list patterns
        return _convert_lists(text)

    rows_html = []
    # Support extended segment tuples (eng,arb,head_en,head_ar)
    def _normalize_seg_tuple(seg):
        if isinstance(seg, (list, tuple)):
            if len(seg) >= 5:
                return seg[0], seg[1], seg[2], seg[3], seg[4]
            if len(seg) >= 4:
                return seg[0], seg[1], seg[2], seg[3], []
            elif len(seg) >= 2:
                return seg[0], seg[1], '', '', []
        if isinstance(seg, dict):
            return seg.get('eng',''), seg.get('arb',''), seg.get('head_en',''), seg.get('head_ar',''), seg.get('takeaways', [])
        return str(seg), '', '', '', []

    def _make_adv_table(eng_text: str, arb_text: str) -> Optional[str]:
        # Detect simple numbered/bulleted lists and zip them into EN/AR rows
        def parse_items(s: str) -> List[str]:
            arr = []
            for ln in (s or '').split('\n'):
                t = ln.strip()
                if not t:
                    continue
                m = re.match(r'^(?:\d+[\.)]|[-•])\s*(.*)', t)
                if m:
                    arr.append(m.group(1).strip())
            return arr
        en_items = parse_items(eng_text)
        ar_items = parse_items(arb_text)
        n = min(len(en_items), len(ar_items))
        if n == 0:
            return None
        rows = []
        for i in range(n):
            rows.append(f"<tr><td class='en'>{_allow_basic_html(en_items[i])}</td><td class='ar'>{_allow_basic_html(ar_items[i])}</td></tr>")
        table_css = """
        table.adv { width:100%; border-collapse:collapse; margin-top:8px; }
        table.adv td { border:1px solid #e8eef6; padding:8px 10px; vertical-align:top; }
        table.adv td.en { direction:ltr; text-align:left; }
        table.adv td.ar { direction:rtl; text-align:right; }
        """
        return f"<style>{table_css}</style><table class='adv'>{''.join(rows)}</table>"

    if layout == 'columns':
        for idx, seg in enumerate(segments, 1):
            eng, arb, head_en, head_ar = _normalize_seg_tuple(seg)
            rows_html.append(
                f"<tr class='segment-row'>"
                f"<td class='idx'>{idx}</td>"
                f"<td class='eng'>{('<p><strong>' + _allow_basic_html(head_en) + '</strong></p>' if head_en else '') + _column_html(eng)}</td>"
                f"<td class='arb'>{('<p><strong>' + _allow_basic_html(head_ar) + '</strong></p>' if head_ar else '') + _column_html(arb)}</td>"
                f"</tr>"
            )
        segments_html = (
            "<table>\n<thead><tr><th class='idx'>#</th><th class='eng'>English Source</th><th class='arb'>الترجمة العربية</th></tr></thead>\n"
            + f"<tbody>{''.join(rows_html)}</tbody></table>"
        )
    else:
        # stacked layout
        cards = []
        for idx, seg in enumerate(segments, 1):
            eng, arb, head_en, head_ar, takeaways = _normalize_seg_tuple(seg)
            cards.append(
                "<div class='segment-card'>"
                + f"<div class='seg-idx'>Segment {idx}</div>"
                + (f"<div class='seg-eng'><p><strong>{_allow_basic_html(head_en)}</strong></p>" if head_en else "<div class='seg-eng'>")
                + _column_html(eng)
                + "</div>"
                + (f"<div class='seg-arb'><p><strong>{_allow_basic_html(head_ar)}</strong></p>" if head_ar else "<div class='seg-arb'>")
                + _column_html(arb)
                + "</div>"
                # Advantages/Disadvantages compact table (no EN/AR labels visible)
                + ( (_make_adv_table(eng, arb) or '') if re.match(r'\s*(advantages|disadvantages|pros|cons)\b', (head_en or ''), flags=re.IGNORECASE) else '' )
                # Key takeaways bullets (Arabic)
                + ("<ul>" + ''.join(f"<li>{_allow_basic_html(tk)}</li>" for tk in takeaways) + "</ul>" if takeaways else '')
                + "<p class='backlink'><a href='#top'>⬆︎ رجوع للأعلى</a></p>"
                + "</div>"
            )
        segments_html = ''.join(cards)

    generated = datetime.utcnow().strftime('%d %B %Y %H:%M UTC')
    # Optional glossary section
    glossary_section = ""
    if glossary:
        rows = []
        for item in glossary:
            term = _escape_html(str(item.get('term', '')))
            ar = _escape_html(str(item.get('arabic', '')))
            definition = _escape_html(str(item.get('definition', '')))
            rows.append(f"<tr><td class='t'>{term}</td><td class='a'>{ar}</td><td class='d'>{definition}</td></tr>")
        glossary_table = """
        <h2 style="margin-top:28px">📚 المصطلحات الطبية</h2>
        <table class="glossary">
          <thead><tr><th>Term</th><th>المصطلح</th><th>التعريف</th></tr></thead>
          <tbody>{rows}</tbody>
        </table>
        """.replace("{rows}", ''.join(rows))
        glossary_section = glossary_table

    css_extra = """
    table.glossary { width:100%; border-collapse:collapse; margin-top:10px; }
    table.glossary th, table.glossary td { border:1px solid #dfe6e9; padding:8px 10px; vertical-align:top; }
    table.glossary th { background:#f1f6ff; color:#0f3460; }
    table.glossary td.t { width: 22%; }
    table.glossary td.a { width: 22%; direction: rtl; text-align:right; }
    table.glossary td.d { width: 56%; }
    """

    html = f"""
    <html>
    <head><meta charset='utf-8'></head>
    <body>
        <a id='top'></a>
        <div class='wrapper'>
            <div class='badge'>Al Madina Translation Suite</div>
            <h1 class='title'>{_escape_html(title)}</h1>
            <div class='meta'>إعداد: @{_escape_html(author_username)} · التاريخ: {generated}</div>
            {segments_html}
            {glossary_section}
        </div>
    </body>
    </html>
    """

    html = html.replace("\xa0", " ")
    pdf_bytes = weasyprint.HTML(string=html).write_pdf(stylesheets=[weasyprint.CSS(string=css + css_extra)])
    bio = io.BytesIO(pdf_bytes)
    bio.name = f"translation_{uuid.uuid4().hex[:8]}.pdf"
    bio.seek(0)
    return bio, bio.name
