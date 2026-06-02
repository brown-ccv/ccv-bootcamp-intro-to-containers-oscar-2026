#!/usr/bin/env python3
"""Convert a Markdown file to an accessible, CCV/Brown-branded HTML file."""

from __future__ import annotations

import argparse
import base64
import html
import mimetypes
import re
import subprocess
import sys
from pathlib import Path

# ── CCV / Brown brand CSS ─────────────────────────────────────────────────────

CSS = """
  /* ── Brown University / CCV brand tokens ── */
  :root {
    --brown-red:       #C5002E;
    --brown-red-dark:  #8B001F;
    --brown-black:     #1A1A1A;
    --brown-header-a:  #2A0510;
    --brown-header-b:  #5A0015;
    --content-bg:      #FFFFFF;
    --content-text:    #1A1A1A;
    --muted-text:      #4A4A4A;
    --rule-color:      #D9D9D9;
    --tint-bg:         #FBF5F6;
    --tint-border:     #EBBCC6;
    --code-bg:         #1E1E2E;
    --code-text:       #CDD6F4;
    --inline-code-bg:  #F3E8EB;
    --inline-code-fg:  #8B001F;
    --link:            #B31B1B;
    --link-visited:    #6B2D8B;
    --focus-ring:      #C5002E;
  }

  *, *::before, *::after { box-sizing: border-box; }

  body {
    margin: 0;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto,
                 'Helvetica Neue', Arial, sans-serif;
    font-size: 1.05rem;
    line-height: 1.8;
    color: var(--content-text);
    background: var(--content-bg);
  }

  /* ── Skip link ── */
  .skip-link {
    position: absolute;
    left: -999px;
    width: 1px;
    height: 1px;
    overflow: hidden;
  }
  .skip-link:focus {
    position: fixed;
    top: 0.5rem;
    left: 0.5rem;
    width: auto;
    height: auto;
    padding: 0.5rem 1rem;
    background: var(--brown-red);
    color: #fff;
    font-weight: 700;
    text-decoration: none;
    border-radius: 4px;
    z-index: 9999;
    outline: 3px solid #fff;
  }

  /* ── University top bar ── */
  .university-bar {
    background: var(--brown-black);
    color: #fff;
    font-size: 0.92rem;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    padding: 0.85rem 2rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 1rem;
  }
  .university-bar a {
    color: #fff;
    text-decoration: none;
    opacity: 0.85;
  }
  .university-bar a:hover { opacity: 1; text-decoration: underline; }
  .university-bar a:focus {
    outline: 2px solid var(--brown-red);
    outline-offset: 2px;
    opacity: 1;
  }
  .university-bar .divider { opacity: 0.35; margin: 0 0.4rem; }

  /* ── Page header ── */
  .page-header {
    background: linear-gradient(
      135deg,
      var(--brown-header-a) 0%,
      var(--brown-header-b) 60%,
      #3D0010 100%
    );
    color: #fff;
    padding: 1.25rem 2rem 1rem;
    position: relative;
    overflow: hidden;
  }
  .page-header::before {
    content: '';
    position: absolute;
    inset: 0;
    background-image:
      linear-gradient(rgba(255,255,255,0.03) 1px, transparent 1px),
      linear-gradient(90deg, rgba(255,255,255,0.03) 1px, transparent 1px);
    background-size: 40px 40px;
    pointer-events: none;
  }
  .page-header-inner {
    max-width: 920px;
    margin: 0 auto;
    position: relative;
    display: flex;
    align-items: center;
    gap: 1.5rem;
  }
  .page-header-text { flex: 1; }
  .page-header .eyebrow {
    display: inline-block;
    font-size: 0.75rem;
    font-weight: 700;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: rgba(255,255,255,0.6);
    margin-bottom: 0.75rem;
  }
  .page-header h1 {
    font-size: clamp(1.6rem, 4vw, 2.4rem);
    font-weight: 700;
    line-height: 1.2;
    margin: 0 0 0.75rem;
    color: #fff;
    border: none;
    padding: 0;
  }
  .page-header .subtitle {
    font-size: 0.95rem;
    color: rgba(255,255,255,0.7);
    margin: 0;
  }
  .red-accent-bar {
    width: 56px;
    height: 4px;
    background: var(--brown-red);
    border-radius: 2px;
    margin: 1rem 0 0;
  }

  /* ── Logos ── */
  .logo-oit-wrap {
    background: #fff;
    border-radius: 4px;
    padding: 3px 8px;
    display: inline-flex;
    align-items: center;
  }
  .logo-oit {
    height: 26px;
    width: auto;
    display: block;
  }
  .logo-ccv {
    height: 56px;
    width: auto;
    display: block;
    flex-shrink: 0;
    filter: drop-shadow(0 1px 3px rgba(0,0,0,0.4));
  }

  /* ── Content wrapper ── */
  .content-wrap {
    max-width: 920px;
    margin: 0 auto;
    padding: 2rem 2rem 3rem;
  }

  /* ── Links ── */
  a { color: var(--link); }
  a:visited { color: var(--link-visited); }
  a:hover { color: var(--brown-red-dark); }
  a:focus {
    outline: 3px solid var(--focus-ring);
    outline-offset: 2px;
    border-radius: 2px;
  }

  /* ── Headings ── */
  h2, h3, h4 {
    color: var(--brown-black);
    line-height: 1.3;
    margin-top: 2.5rem;
    margin-bottom: 0.5rem;
  }
  h2 {
    font-size: 1.55rem;
    font-weight: 700;
    padding-bottom: 0.4rem;
    border-bottom: 2px solid var(--brown-red);
  }
  h3 {
    font-size: 1.2rem;
    font-weight: 600;
    border-left: 4px solid var(--brown-red);
    padding-left: 0.75rem;
    margin-left: -0.75rem;
  }
  h4 {
    font-size: 1.05rem;
    font-weight: 600;
    color: var(--brown-red-dark);
  }

  /* ── Images ── */
  figure { margin: 1.75rem 0; }
  img {
    max-width: 100%;
    height: auto;
    display: block;
    margin: 0 auto;
    border: 1px solid var(--rule-color);
    border-radius: 6px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.08);
  }
  figcaption {
    text-align: center;
    font-size: 0.88rem;
    color: var(--muted-text);
    margin-top: 0.5rem;
    font-style: italic;
  }

  /* ── Code ── */
  code {
    font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
    font-size: 0.88em;
    background: var(--inline-code-bg);
    color: var(--inline-code-fg);
    padding: 0.15em 0.4em;
    border-radius: 3px;
    border: 1px solid var(--tint-border);
  }
  pre {
    background: var(--code-bg);
    color: var(--code-text);
    border-radius: 6px;
    border-left: 4px solid var(--brown-red);
    padding: 1rem 1.25rem;
    overflow-x: auto;
    margin: 1rem 0;
    box-shadow: 0 2px 8px rgba(0,0,0,0.15);
  }
  pre code {
    background: none;
    color: inherit;
    padding: 0;
    border: none;
    font-size: 0.93rem;
  }

  /* ── Lists ── */
  ul, ol { padding-left: 1.6rem; }
  li { margin-bottom: 0.4rem; }

  /* ── Table ── */
  .table-wrapper {
    overflow-x: auto;
    margin: 1.25rem 0;
    border-radius: 6px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.08);
  }
  table { width: 100%; border-collapse: collapse; font-size: 0.97rem; }
  caption {
    font-weight: 600;
    font-style: italic;
    margin-bottom: 0.5rem;
    text-align: left;
    color: var(--muted-text);
    font-size: 0.9rem;
  }
  th, td {
    padding: 0.6rem 1rem;
    border: 1px solid var(--rule-color);
    text-align: left;
    vertical-align: top;
  }
  th {
    background: var(--brown-header-b);
    color: #fff;
    font-weight: 600;
    letter-spacing: 0.02em;
  }
  tr:nth-child(even) td { background: var(--tint-bg); }

  /* ── Section spacing ── */
  section { margin-bottom: 1rem; }

  /* ── Footer ── */
  footer {
    background: var(--brown-black);
    color: rgba(255,255,255,0.65);
    font-size: 0.85rem;
    padding: 1.5rem 2rem;
    text-align: center;
  }
  footer a { color: rgba(255,255,255,0.85); }
  footer a:hover { color: #fff; }
  footer a:focus {
    outline: 2px solid var(--brown-red);
    outline-offset: 2px;
  }
  .footer-inner {
    max-width: 920px;
    margin: 0 auto;
    display: flex;
    flex-wrap: wrap;
    justify-content: space-between;
    align-items: center;
    gap: 0.5rem;
  }
  .footer-brand { font-weight: 600; color: #fff; font-size: 0.9rem; }

  /* ── Responsive ── */
  @media (max-width: 600px) {
    .university-bar {
      flex-direction: column;
      align-items: flex-start;
      gap: 0.2rem;
      padding: 0.5rem 1rem;
    }
    .content-wrap       { padding: 1.25rem 1rem 2rem; }
    .page-header        { padding: 1rem; }
    .page-header-inner  { flex-direction: column; align-items: flex-start; }
    .logo-ccv           { height: 36px; align-self: flex-end; }
  }
"""


# ── HTML template ─────────────────────────────────────────────────────────────

def build_html(body: str, title: str, subtitle: str,
               oit_logo: str, ccv_logo: str, year: str = "") -> str:
    safe_title    = html.escape(title)
    safe_subtitle = html.escape(subtitle)
    eyebrow_text  = html.escape(f"CCV BootCamp {year}".strip())

    oit_img = (
        f'<a href="https://it.brown.edu" class="logo-oit-wrap">'
        f'<img src="{html.escape(oit_logo)}" '
        f'alt="Brown University Office of Information Technology" class="logo-oit">'
        f'</a>'
        if oit_logo else ""
    )
    ccv_img = (
        f'<img src="{html.escape(ccv_logo)}" '
        f'alt="Center for Computation and Visualization" class="logo-ccv">'
        if ccv_logo else ""
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{safe_title}</title>
  <style>{CSS}  </style>
</head>
<body>

  <a href="#main-content" class="skip-link">Skip to main content</a>

  <div class="university-bar" role="banner">
    {oit_img}
    <span>
      <a href="https://docs.ccv.brown.edu">Docs</a>
      <span class="divider">|</span>
      <a href="mailto:support@ccv.brown.edu">Support</a>
    </span>
  </div>

  <header class="page-header">
    <div class="page-header-inner">
      <div class="page-header-text">
        <span class="eyebrow">{eyebrow_text}</span>
        <h1>{safe_title}</h1>
        <p class="subtitle">{safe_subtitle}</p>
        <div class="red-accent-bar" aria-hidden="true"></div>
      </div>
      {ccv_img}
    </div>
  </header>

  <div class="content-wrap">
    <main id="main-content">
{body}
    </main>
  </div>

  <footer>
    <div class="footer-inner">
      <span class="footer-brand">Center for Computation and Visualization</span>
      <span>
        <a href="https://www.brown.edu">Brown University</a>
        &nbsp;&middot;&nbsp;
        <a href="https://ccv.brown.edu">ccv.brown.edu</a>
        &nbsp;&middot;&nbsp;
        <a href="mailto:support@ccv.brown.edu">support@ccv.brown.edu</a>
      </span>
    </div>
  </footer>

</body>
</html>"""


# ── Preprocessing ─────────────────────────────────────────────────────────────

def preprocess_markdown(text: str) -> tuple[str, dict]:
    """Strip the leading title/author/resources block and extract metadata.

    The convention in these CCV markdown files is:
      ## Page Title
      ### CCV BootCamp YYYY Author Name
      ### Resources for help ...
      #### ...resource items...
      ## First real content section
    """
    lines = text.splitlines()
    meta: dict = {"title": None, "year": None, "author": None}
    i, n = 0, len(lines)

    # Skip leading blank lines
    while i < n and not lines[i].strip():
        i += 1

    # First heading → page title
    if i < n and re.match(r"^#{1,3}\s+", lines[i]):
        meta["title"] = re.sub(r"^#+\s+", "", lines[i]).strip().title()
        i += 1

    # Consume everything until the next `##` real content heading.
    # Along the way, try to extract year and author from the sub-headings.
    while i < n and not re.match(r"^##\s+", lines[i]):
        line = lines[i]
        if re.match(r"^#{1,4}\s+", line) and not meta["author"]:
            text_part = re.sub(r"^#+\s+", "", line).strip()
            year_m = re.search(r"\b(20\d\d)\b", text_part)
            if year_m:
                meta["year"] = year_m.group(1)
                meta["author"] = text_part
        i += 1

    return "\n".join(lines[i:]), meta


# ── Conversion ────────────────────────────────────────────────────────────────

def convert_with_pandoc(text: str) -> str | None:
    try:
        result = subprocess.run(
            ["pandoc", "--from=markdown", "--to=html", "--no-highlight"],
            input=text, check=True, capture_output=True, text=True,
        )
        return result.stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def convert_with_python_markdown(text: str) -> str:
    try:
        import markdown
    except ImportError:
        print("Neither pandoc nor the 'markdown' package is available.")
        print("Install one:  brew install pandoc   or   pip install markdown")
        sys.exit(1)

    # Wrap bare URLs so python-markdown linkifies them
    text = re.sub(
        r'(?<![(\[<"])((https?://)[^\s<>")\]]+)',
        r'<\1>',
        text,
    )
    return markdown.markdown(text, extensions=["extra", "toc"])


_MIME_FALLBACKS = {
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}


def _data_uri(path: Path) -> str:
    mime = (mimetypes.guess_type(path.name)[0]
            or _MIME_FALLBACKS.get(path.suffix.lower(), "application/octet-stream"))
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{data}"


def embed_images(html_text: str, base_dir: Path) -> str:
    """Replace local img src paths with base64 data URIs."""
    def replacer(m: re.Match) -> str:
        src = m.group(1)
        if src.startswith(("data:", "http://", "https://")):
            return m.group(0)
        img_path = (base_dir / src).resolve()
        if not img_path.exists():
            print(f"  Warning: image not found, skipping embed: {img_path}")
            return m.group(0)
        return f'src="{_data_uri(img_path)}"'

    return re.sub(r'src="([^"]*)"', replacer, html_text)


def convert(input_path: str, output_path: str | None,
            title: str | None, subtitle: str,
            oit_logo: str, ccv_logo: str) -> None:
    input_file = Path(input_path)
    if not input_file.exists():
        print(f"Error: {input_file} not found.")
        sys.exit(1)

    output_file = Path(output_path) if output_path else input_file.with_suffix(".html")

    raw = input_file.read_text(encoding="utf-8")
    body_md, meta = preprocess_markdown(raw)

    derived_title = title or meta["title"] or input_file.stem.replace("_", " ").title()
    derived_year  = meta["year"] or ""
    derived_author = meta["author"] or ""

    body = convert_with_pandoc(body_md)
    method = "pandoc"
    if body is None:
        body = convert_with_python_markdown(body_md)
        method = "python-markdown"

    full_html = build_html(body, derived_title, subtitle or derived_author,
                           oit_logo, ccv_logo, derived_year)
    full_html = embed_images(full_html, input_file.parent)
    output_file.write_text(full_html, encoding="utf-8")
    print(f"[{method}] {input_file} -> {output_file}")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert Markdown to CCV/Brown-branded accessible HTML."
    )
    parser.add_argument("input", help="Input .md file")
    parser.add_argument("output", nargs="?", help="Output .html file (default: same name)")
    parser.add_argument("--title", help="Page title (default: derived from filename)")
    parser.add_argument("--subtitle", default="Center for Computation and Visualization, Brown University",
                        help="Subtitle shown in the page header")
    parser.add_argument("--oit-logo", default="oit-logo.png",
                        help="Path to OIT logo PNG (default: oit-logo.png)")
    parser.add_argument("--ccv-logo", default="ccv-logo.svg",
                        help="Path to CCV logo SVG (default: ccv-logo.svg)")
    parser.add_argument("--no-logos", action="store_true",
                        help="Omit both logos")
    args = parser.parse_args()

    oit = "" if args.no_logos else args.oit_logo
    ccv = "" if args.no_logos else args.ccv_logo

    convert(args.input, args.output, args.title, args.subtitle, oit, ccv)


if __name__ == "__main__":
    main()
