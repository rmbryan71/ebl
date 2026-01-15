from pathlib import Path
import html
import re

try:
    import markdown
except ImportError:
    markdown = None


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK_PATH = ROOT / "lab_notebook.md"
OUTPUT_PATH = ROOT / "templates" / "news.html"


def flush_paragraph(paragraph_lines, blocks):
    if not paragraph_lines:
        return
    blocks.append({"type": "paragraph", "text": "\n".join(paragraph_lines).strip()})
    paragraph_lines.clear()


def flush_list(list_items, list_type, blocks):
    if not list_items:
        return
    blocks.append({"type": list_type, "items": list_items[:]})
    list_items.clear()


def parse_sections(lines):
    sections = []
    current_title = None
    blocks = []
    paragraph_lines = []
    list_items = []
    list_type = None

    def flush_section():
        flush_paragraph(paragraph_lines, blocks)
        flush_list(list_items, list_type, blocks)
        if current_title or blocks:
            sections.append({"title": current_title or "Updates", "blocks": blocks[:]})
            blocks.clear()

    for line in lines:
        if line.startswith("# "):
            flush_section()
            current_title = line[2:].strip()
            continue
        if line.startswith("## "):
            flush_paragraph(paragraph_lines, blocks)
            flush_list(list_items, list_type, blocks)
            blocks.append({"type": "subheading", "text": line[3:].strip()})
            continue
        if not line.strip():
            flush_paragraph(paragraph_lines, blocks)
            flush_list(list_items, list_type, blocks)
            continue

        stripped = line.lstrip()
        ordered_match = stripped.split(". ", 1)
        is_ordered = len(ordered_match) == 2 and ordered_match[0].isdigit()
        is_unordered = stripped.startswith("- ") or stripped.startswith("* ")
        if is_ordered or is_unordered:
            flush_paragraph(paragraph_lines, blocks)
            item_text = ordered_match[1] if is_ordered else stripped[2:]
            next_type = "ol" if is_ordered else "ul"
            if list_type and list_type != next_type:
                flush_list(list_items, list_type, blocks)
            list_type = next_type
            list_items.append(item_text.strip())
            continue

        if list_items:
            flush_list(list_items, list_type, blocks)
            list_type = None

        if stripped[:1].isdigit() and ":" in stripped and " - " in stripped and paragraph_lines:
            flush_paragraph(paragraph_lines, blocks)
        paragraph_lines.append(stripped)

    flush_section()
    return sections


def render_blocks(blocks):
    html_parts = []
    for block in blocks:
        if block["type"] == "subheading":
            html_parts.append(f"<h3>{html.escape(block['text'])}</h3>")
        elif block["type"] in {"ul", "ol"}:
            items_html = "".join(f"<li>{render_markdown(item)}</li>" for item in block["items"])
            html_parts.append(f"<{block['type']} class=\"rules-list\">{items_html}</{block['type']}>")
        else:
            body = render_markdown(block["text"])
            html_parts.append(f"<div class=\"news-paragraph\">{body}</div>")
    return "\n".join(html_parts)


def build_news_page(sections):
    cards = []
    for section in sections:
        body_html = render_blocks(section["blocks"])
        cards.append(
            f"""
      <section class="rules-card">
        <h2>{section['title']}</h2>
        {body_html}
      </section>
            """.strip()
        )

    cards_html = "\n      ".join(cards) if cards else '<section class="rules-card"><p>No updates yet.</p></section>'
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>EBL News</title>
    <link rel="stylesheet" href="{{{{ url_for('static', filename='styles.css') }}}}" />
  </head>
  <body>
    <div class="backdrop"></div>
    <nav class="top-nav">
      <a href="/">Home</a>
      <a href="/week">Weekly Standings</a>
      <a href="/season">Season Standings</a>
      <a href="/available">Available Players</a>
      <a href="/audit">Audit</a>
      <a href="/rules" class="nav-rules">Rules</a>
      <a href="/news" class="nav-news">News</a>
    </nav>
    <nav class="bottom-nav">
      <a href="/">Home</a>
      <a href="/week">Week</a>
      <a href="/season">Season</a>
    </nav>
    <header class="hero rules-hero">
      <div class="hero-content">
        <h1 class="league-title league-title--small">News</h1>
      </div>
    </header>

    <main class="rules-page news-page">
      {cards_html}
    </main>
  </body>
</html>
"""


def render_markdown(text):
    if markdown:
        return markdown.markdown(text, extensions=["extra", "sane_lists"])
    parts = []
    last_idx = 0
    for match in re.finditer(r"\[([^\]]+)\]\(([^)]+)\)", text):
        parts.append(html.escape(text[last_idx : match.start()]))
        label = html.escape(match.group(1))
        href = html.escape(match.group(2), quote=True)
        parts.append(f'<a href="{href}">{label}</a>')
        last_idx = match.end()
    parts.append(html.escape(text[last_idx:]))
    linked = "".join(parts)
    return "<p>" + linked.replace("\n", "<br />") + "</p>"


def main():
    if not NOTEBOOK_PATH.exists():
        raise SystemExit("lab_notebook.md not found.")
    lines = NOTEBOOK_PATH.read_text(encoding="utf-8").splitlines()
    sections = parse_sections(lines)
    html = build_news_page(sections)
    OUTPUT_PATH.write_text(html, encoding="utf-8")


if __name__ == "__main__":
    main()
