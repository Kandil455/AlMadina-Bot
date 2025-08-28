# file_generator.py
from asyncio.log import logger
import io
import re
import uuid
from typing import List
import weasyprint
from datetime import datetime

import config

def _escape_html(s: str) -> str:
    """A minimal HTML escaper for content that will be placed inside tags."""
    s = str(s or "")
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

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
        @top-center { content: '{escaped_title}'; font-family: var(--font-main); font-size: 9pt; color: var(--meta-text-color); }
        @bottom-center { content: "تم إنشاؤه بواسطة @"_study1_bot"  |  صفحة " counter(page); font-family: var(--font-main); font-size: 9pt; color: var(--meta-text-color); }
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
        color: var(--primary-color); font-size: 20pt; font-weight: 700;
        margin-top: 40px; margin-bottom: 20px;
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
    ul { list-style: none; padding-right: 20px; margin-bottom: 1em; }
    li { margin-bottom: 0.5em; position: relative; }
    li::before {
        content: '•'; position: absolute; right: -20px;
        color: var(--primary-color); font-size: 1.2em;
    }
    .main-content.ltr ul { padding-right: 0; padding-left: 20px; }
    .main-content.ltr li::before { right: auto; left: -20px; }
    
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

        # Standard List Processor
        def list_replacer(match):
            items = match.group(0).strip().split('\n')
            li_items = ''.join(f'<li>{item.strip()[2:].strip()}</li>' for item in items if item.strip())
            return f'<ul>{li_items}</ul>'

        processed = re.sub(r'((?:^\s*[-•]\s+.*\s*)+)', list_replacer, processed, flags=re.MULTILINE)
        
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
        # Process paired bilingual blocks using the new grid system
        def process_bilingual_block(match):
            eng_text = match.group(1).strip()
            arb_text = match.group(2).strip()
            
            # ✨ NEW: Structure the Arabic text for the summary/details format
            arb_text = arb_text.replace("الخلاصة:", '<p class="summary-title">✅ الخلاصة:</p><p>')
            arb_text = arb_text.replace("التفاصيل:", '</p><p class="details-title">🔍 التفاصيل:</p><p>')
            # Ensure a closing paragraph tag
            arb_text += "</p>"
            # Clean up empty paragraphs that might result from the replacement
            arb_text = re.sub(r'<p>\s*</p>', '', arb_text)

            # Format the English text simply, wrapping in paragraphs
            eng_html = "\n".join([f'<p>{line.strip()}</p>' for line in eng_text.split('\n') if line.strip()])

            return (f'<div class="bilingual-grid">'
                    f'<div class="bilingual-col bilingual-col-arb">{arb_text}</div>' # Arabic on the right
                    f'<div class="bilingual-col bilingual-col-eng">{eng_html}</div>' # English on the left
                    f'</div>')
        
        processed = re.sub(r'\[ENG\](.*?)\[/ENG\]\s*\[ARB\](.*?)\[/ARB\]', process_bilingual_block, raw_content, flags=re.DOTALL | re.IGNORECASE)

        # Process any content NOT inside a bilingual block using the universal formatter
        # We find all bilingual blocks and remove them to isolate the remaining content
        remaining_content = re.sub(r'\[ENG\].*?\[/ARB\]', '', raw_content, flags=re.DOTALL | re.IGNORECASE).strip()
        if remaining_content:
            # Prepend the formatted remaining content to the processed bilingual blocks
            processed = _format_text_to_html(remaining_content) + processed
        
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
                <h1 class="main-title">{_escape_html(main_title)}</h1>
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