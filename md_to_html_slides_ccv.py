#!/usr/bin/env python3
"""
md_to_html_slides_ccv.py — Markdown deck → self-contained CCV/Brown-branded HTML slideshow.

Slides are separated by a line containing only `---`.

The output HTML is FULLY self-contained:
  * every <img> is inlined as a base64 data URI
  * OIT and CCV logos are inlined as data URIs
  * all CSS and JS are inline — no CDN, no web fonts, no network

Usage:
    python3 md_to_html_slides_ccv.py slides.md
    python3 md_to_html_slides_ccv.py slides.md talk.html
    python3 md_to_html_slides_ccv.py slides.md --title "My Talk"
    python3 md_to_html_slides_ccv.py slides.md --no-logos

Dependency: the `markdown` package (pip install markdown).
"""

from __future__ import annotations

import argparse
import base64
import mimetypes
import os
import re
import sys
from pathlib import Path

try:
    import markdown  # type: ignore
except ImportError:
    sys.exit(
        "This script needs the 'markdown' package.\n"
        "Install it with:  pip install markdown"
    )


# ── Image embedding ───────────────────────────────────────────────────────────

_MIME_FALLBACKS = {
    "png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
    "gif": "image/gif", "svg": "image/svg+xml", "webp": "image/webp",
}
IMG_TAG_RE = re.compile(r'(<img\b[^>]*?\bsrc=)(["\'])(.*?)\2([^>]*>)', re.IGNORECASE)


def _data_uri(path: str) -> str:
    mime, _ = mimetypes.guess_type(path)
    if mime is None:
        ext = os.path.splitext(path)[1].lower().lstrip(".")
        mime = _MIME_FALLBACKS.get(ext, "application/octet-stream")
    with open(path, "rb") as fh:
        encoded = base64.b64encode(fh.read()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def embed_images(html: str, base_dir: str) -> str:
    """Replace local <img src=...> paths with base64 data URIs."""
    def repl(m: re.Match) -> str:
        prefix, quote, src, suffix = m.groups()
        if src.startswith(("data:", "http://", "https://", "//")):
            return m.group(0)
        candidate = src if os.path.isabs(src) else os.path.join(base_dir, src)
        if os.path.isfile(candidate):
            try:
                return f"{prefix}{quote}{_data_uri(candidate)}{quote}{suffix}"
            except OSError as exc:
                sys.stderr.write(f"  ! could not read {candidate}: {exc}\n")
        else:
            sys.stderr.write(f"  ! image not found, using placeholder: {src}\n")
        alt_m = re.search(r'alt=(["\'])(.*?)\1', suffix + prefix, re.IGNORECASE)
        alt = alt_m.group(2) if alt_m else os.path.basename(src)
        return (
            '<span class="img-missing">'
            f'<strong>Image:</strong> {alt}'
            f'<br><code>{os.path.basename(src)}</code>'
            "<br><em>drop this file next to the .md and re-run to embed it</em>"
            "</span>"
        )
    return IMG_TAG_RE.sub(repl, html)


def logo_data_uri(path: str, base_dir: str) -> str | None:
    """Return a data URI for a logo file, or None if the file doesn't exist."""
    candidate = path if os.path.isabs(path) else os.path.join(base_dir, path)
    if os.path.isfile(candidate):
        return _data_uri(candidate)
    sys.stderr.write(f"  ! logo not found, omitting: {candidate}\n")
    return None


# ── Markdown pre-processing ───────────────────────────────────────────────────

def preprocess_markdown(text: str) -> tuple[str, dict]:
    """Strip the leading title/author/resources block and extract metadata.

    Expects the CCV convention:
      ## Slide Deck Title
      ### CCV BootCamp YYYY  Author Name
      ### Resources for help ...
      #### ...items...
      ## First real content slide
    """
    lines = text.splitlines()
    meta: dict = {"title": None, "year": None, "author": None}
    i, n = 0, len(lines)

    while i < n and not lines[i].strip():
        i += 1

    if i < n and re.match(r"^#{1,3}\s+", lines[i]):
        meta["title"] = re.sub(r"^#+\s+", "", lines[i]).strip().title()
        i += 1

    # Skip until next ## content heading, extracting year/author along the way.
    while i < n and not re.match(r"^(##\s+|---)", lines[i]):
        line = lines[i]
        if re.match(r"^#{1,4}\s+", line) and not meta["author"]:
            text_part = re.sub(r"^#+\s+", "", line).strip()
            year_m = re.search(r"\b(20\d\d)\b", text_part)
            if year_m:
                meta["year"] = year_m.group(1)
                meta["author"] = text_part
        i += 1

    return "\n".join(lines[i:]), meta


# ── Slide splitting & rendering ───────────────────────────────────────────────

def split_slides(text: str) -> list[str]:
    slides, current = [], []
    for line in text.splitlines():
        if line.strip() == "---":
            slides.append("\n".join(current))
            current = []
        else:
            current.append(line)
    slides.append("\n".join(current))
    return [s for s in (s.strip() for s in slides) if s]


def render_slide(md_text: str, converter: markdown.Markdown, base_dir: str) -> str:
    converter.reset()
    body = converter.convert(md_text)
    body = embed_images(body, base_dir)
    flavour = "title" if re.match(r"\s*<h1", body) else "content"
    return f'<section class="slide slide-{flavour}"><div class="slide-inner">{body}</div></section>'


# ── HTML page template ────────────────────────────────────────────────────────

PAGE_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
/* ── Brown University / CCV brand tokens ── */
:root {{
  /* brand */
  --brown-red:      #C5002E;
  --brown-red-dark: #8B001F;
  --brown-black:    #1A1A1A;
  --amber:          #FFC72C;   /* CCV logo yellow */
  --teal:           #00B398;   /* CCV logo teal */

  /* slide surface */
  --bg:        #0c1016;
  --bg-2:      #11161f;
  --ink:       #e9eef5;
  --muted:     #93a1b3;
  --line:      #232c3a;
  --code-bg:   #0a0e14;

  /* aliases used in slide content */
  --accent:    var(--brown-red);
  --accent-2:  var(--amber);

  --mono: "SF Mono", "JetBrains Mono", "Fira Code", ui-monospace, Menlo, Consolas, monospace;
  --sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
}}

* {{ box-sizing: border-box; }}
html, body {{ margin: 0; height: 100%; }}
body {{
  background: var(--bg);
  color: var(--ink);
  font-family: var(--sans);
  overflow: hidden;
}}

/* ── University top bar ── */
.university-bar {{
  position: fixed;
  top: 0; left: 0; right: 0;
  height: 114px;
  z-index: 20;
  background: var(--brown-black);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 3rem;
  font-size: 1.4rem;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}}
.university-bar a {{
  color: rgba(255,255,255,0.75);
  text-decoration: none;
}}
.university-bar a:hover {{ color: #fff; text-decoration: underline; }}
.university-bar a:focus {{
  outline: 2px solid var(--brown-red);
  outline-offset: 2px;
}}
.university-bar .divider {{ opacity: 0.3; margin: 0 0.5rem; }}
.logo-oit-wrap {{
  background: #fff;
  border-radius: 8px;
  padding: 6px 16px;
  display: inline-flex;
  align-items: center;
  line-height: 0;
}}
.logo-oit {{ height: 66px; width: auto; display: block; }}
.logo-ccv {{ height: 66px; width: auto; display: block; }}

/* ── Background grid + glow ── */
.backdrop {{
  position: fixed; inset: 0; z-index: 0; pointer-events: none;
  background:
    radial-gradient(1100px 600px at 78% -10%, rgba(197,0,46,0.18), transparent 60%),
    radial-gradient(900px 600px at 10% 110%,  rgba(255,199,44,0.10), transparent 60%),
    linear-gradient(var(--line) 1px, transparent 1px) 0 0 / 100% 46px,
    linear-gradient(90deg, var(--line) 1px, transparent 1px) 0 0 / 46px 100%;
  opacity: .5;
}}

/* ── Slide deck ── */
.deck {{
  position: relative;
  z-index: 1;
  height: 100%;
  padding-top: 114px;   /* clear the university bar */
}}

.slide {{
  position: absolute;
  inset: 114px 0 0 0;   /* start below university bar */
  display: none;
  padding: 5vh 8vw 14vh;
  animation: fade .45s ease both;
}}
.slide.active {{ display: flex; }}
@keyframes fade {{ from {{ opacity: 0; transform: translateY(14px); }} to {{ opacity: 1; transform: none; }} }}

.slide-inner {{ margin: auto 0; width: 100%; max-width: 1100px; }}

/* ── Typography ── */
h1 {{
  font-family: var(--mono);
  font-size: clamp(2.4rem, 6vw, 4.6rem);
  line-height: 1.04; letter-spacing: -.02em;
  margin: 0 0 .4em; font-weight: 700;
}}
h2 {{
  font-family: var(--mono);
  font-size: clamp(1.7rem, 3.7vw, 3rem);
  line-height: 1.08; letter-spacing: -.015em;
  margin: 0 0 .7em; font-weight: 700;
  position: relative; padding-left: .7em;
}}
h2::before {{
  content: ""; position: absolute; left: 0; top: .12em; bottom: .12em;
  width: 5px; border-radius: 3px;
  background: linear-gradient(var(--brown-red), var(--amber));
}}
.slide-title h2 {{ padding-left: 0; color: var(--amber); }}
.slide-title h2::before {{ display: none; }}
.slide-title .slide-inner > p {{ color: var(--muted); }}
h3 {{ font-family: var(--mono); font-size: 1.15rem; color: var(--amber); margin: 1.2em 0 .4em; }}

p {{ font-size: clamp(1.05rem, 1.7vw, 1.5rem); line-height: 1.5; margin: .5em 0; max-width: 60ch; }}

ul, ol {{ font-size: clamp(1.05rem, 1.7vw, 1.5rem); line-height: 1.5; padding-left: 1.1em; margin: .4em 0; }}
li {{ margin: .42em 0; }}
li::marker {{ color: var(--brown-red); }}
ul ul, ol ol, ul ol, ol ul {{ font-size: .92em; margin: .25em 0; }}

strong {{ color: #fff; }}
em {{ color: var(--muted); }}
a {{ color: var(--amber); text-decoration: none; border-bottom: 1px solid rgba(255,199,44,.35); }}
a:focus {{ outline: 2px solid var(--brown-red); outline-offset: 2px; border-radius: 2px; }}

/* ── Code ── */
code {{ font-family: var(--mono); font-size: .92em; }}
:not(pre) > code {{
  background: var(--code-bg); border: 1px solid var(--line);
  padding: .08em .4em; border-radius: 5px; color: var(--amber);
}}
pre {{
  background: var(--code-bg);
  border: 1px solid var(--line);
  border-left: 4px solid var(--brown-red);
  border-radius: 12px;
  padding: 2.4rem 1.3rem 1.2rem;
  overflow: auto; position: relative;
  margin: .8em 0;
  box-shadow: 0 18px 40px -24px rgba(0,0,0,.8);
}}
pre::before {{
  content: ""; position: absolute; top: .95rem; left: 1.2rem;
  width: 11px; height: 11px; border-radius: 50%;
  background: #ff5f56;
  box-shadow: 19px 0 #ffbd2e, 38px 0 #27c93f;
}}
pre code {{
  display: block; color: #d7e2f0;
  font-size: clamp(.8rem, 1.15vw, 1.05rem);
  line-height: 1.55; background: none; border: 0; padding: 0;
}}

/* ── Tables ── */
table {{ width: 100%; border-collapse: collapse; margin: .7em 0; font-size: clamp(.85rem, 1.35vw, 1.2rem); }}
th, td {{ text-align: left; padding: .55em .7em; border-bottom: 1px solid var(--line); }}
thead th {{
  color: var(--amber); font-family: var(--mono); font-weight: 700;
  border-bottom: 2px solid var(--brown-red);
}}
tbody tr:hover {{ background: rgba(255,255,255,.02); }}
td code, th code {{ white-space: nowrap; }}

/* ── Blockquote callout ── */
blockquote {{
  margin: .9em 0; padding: .7em 1.1em;
  border-left: 3px solid var(--amber);
  background: linear-gradient(90deg, rgba(255,199,44,.10), transparent);
  border-radius: 0 10px 10px 0;
  font-size: clamp(.95rem, 1.45vw, 1.25rem); color: var(--ink);
}}
blockquote p {{ margin: .2em 0; }}

/* ── Images ── */
img {{
  max-width: 100%; max-height: 52vh;
  border-radius: 12px; border: 1px solid var(--line);
  display: block; margin: .6em auto;
}}
.img-missing {{
  display: block; margin: .8em 0; padding: 1.4em; text-align: center;
  border: 1.5px dashed var(--line); border-radius: 12px;
  background: rgba(255,255,255,.02); color: var(--muted);
  font-size: clamp(.9rem, 1.4vw, 1.15rem);
}}
.img-missing code {{ color: var(--amber); }}

/* ── Task-list checkboxes ── */
input[type=checkbox] {{ accent-color: var(--brown-red); transform: scale(1.15); margin-right: .4em; }}

/* ── Progress bar ── */
.progress {{
  position: fixed; top: 114px; left: 0; height: 4px; z-index: 15;
  background: linear-gradient(90deg, var(--brown-red), var(--amber));
  transition: width .35s ease;
}}

/* ── Footer ── */
.slide-footer {{
  position: fixed; bottom: 2.4vh; left: 8vw; right: 8vw; z-index: 10;
  display: flex; justify-content: space-between; align-items: center;
  font-family: var(--mono); font-size: 1.35rem; color: var(--muted);
  letter-spacing: .04em;
}}
.slide-footer .brand {{ display: flex; align-items: center; gap: 1rem; }}
.slide-footer .brand strong {{ color: var(--brown-red); }}
kbd {{
  font-family: var(--mono); font-size: 1.1rem; color: var(--muted);
  border: 1px solid var(--line); border-radius: 5px; padding: .1em .45em;
}}

@media (max-width: 700px) {{
  .slide {{ padding: 5vh 6vw 11vh; }}
  .slide-footer {{ left: 6vw; right: 6vw; }}
  .slide-footer .hint {{ display: none; }}
  .university-bar .nav-links {{ display: none; }}
}}
</style>
</head>
<body>

<!-- University top bar -->
<div class="university-bar" role="banner">
  {oit_logo_html}
  <span class="nav-links">
    <a href="https://docs.ccv.brown.edu">Docs</a>
    <span class="divider">|</span>
    <a href="mailto:support@ccv.brown.edu">Support</a>
  </span>
</div>

<div class="backdrop"></div>
<div class="progress" id="progress"></div>

<div class="deck" id="deck">
{slides}
</div>

<div class="slide-footer">
  <span class="brand">
    {ccv_logo_html}
    <span><strong>CCV</strong> &middot; Brown University</span>
  </span>
  <span class="hint"><kbd>&larr;</kbd> <kbd>&rarr;</kbd> navigate &middot; <kbd>F</kbd> fullscreen</span>
  <span class="counter" id="counter"></span>
</div>

<script>
(function () {{
  var slides = Array.prototype.slice.call(document.querySelectorAll(".slide"));
  var i = 0;
  var progress = document.getElementById("progress");
  var counter  = document.getElementById("counter");

  function show(n) {{
    i = Math.max(0, Math.min(slides.length - 1, n));
    slides.forEach(function (s, k) {{ s.classList.toggle("active", k === i); }});
    progress.style.width = ((i + 1) / slides.length * 100) + "%";
    counter.textContent = (i + 1) + " / " + slides.length;
    if (location.hash !== "#" + (i + 1)) {{
      history.replaceState(null, "", "#" + (i + 1));
    }}
  }}

  document.addEventListener("keydown", function (e) {{
    if (["ArrowRight", "PageDown", " ", "Enter"].indexOf(e.key) > -1) {{ e.preventDefault(); show(i + 1); }}
    else if (["ArrowLeft", "PageUp", "Backspace"].indexOf(e.key) > -1) {{ e.preventDefault(); show(i - 1); }}
    else if (e.key === "Home") {{ show(0); }}
    else if (e.key === "End")  {{ show(slides.length - 1); }}
    else if (e.key === "f" || e.key === "F") {{
      if (!document.fullscreenElement) document.documentElement.requestFullscreen();
      else document.exitFullscreen();
    }}
  }});

  document.getElementById("deck").addEventListener("click", function (e) {{
    if (e.target.closest("a, pre, code, table")) return;
    (e.clientX > window.innerWidth / 2 ? function(){{ show(i+1); }} : function(){{ show(i-1); }})();
  }});

  var start = parseInt((location.hash || "#1").slice(1), 10);
  show(isNaN(start) ? 0 : start - 1);
}})();
</script>
</body>
</html>
"""


# ── Conversion ────────────────────────────────────────────────────────────────

def convert(md_path: str, out_path: str | None = None,
            title: str | None = None,
            oit_logo: str = "oit-logo.png",
            ccv_logo: str = "ccv-logo.svg") -> str:
    base_dir = os.path.dirname(os.path.abspath(md_path))

    with open(md_path, "r", encoding="utf-8") as fh:
        raw = fh.read()

    body_md, meta = preprocess_markdown(raw)
    derived_title = title or meta["title"] or Path(md_path).stem.replace("_", " ").title()
    year = meta["year"] or ""
    eyebrow = f"CCV BootCamp {year}".strip()

    # Inject eyebrow into the first slide as a subtitle if it's a title slide
    if year:
        body_md = re.sub(
            r"^(#\s+.+)$",
            rf"\1\n\n*{eyebrow}*",
            body_md, count=1, flags=re.MULTILINE
        )

    converter = markdown.Markdown(
        extensions=["fenced_code", "tables", "sane_lists", "attr_list", "nl2br"],
        output_format="html5",
    )

    chunks = split_slides(body_md)
    slides_html = "\n".join(render_slide(c, converter, base_dir) for c in chunks)

    # Build logo HTML (embed as data URIs)
    oit_uri = logo_data_uri(oit_logo, base_dir) if oit_logo else None
    ccv_uri = logo_data_uri(ccv_logo, base_dir) if ccv_logo else None

    oit_logo_html = (
        f'<a href="https://it.brown.edu" class="logo-oit-wrap">'
        f'<img src="{oit_uri}" alt="Brown University OIT" class="logo-oit"></a>'
        if oit_uri else
        '<span style="color:rgba(255,255,255,0.6);font-size:0.8rem;">Brown University · OIT</span>'
    )
    ccv_logo_html = (
        f'<img src="{ccv_uri}" alt="CCV" class="logo-ccv">'
        if ccv_uri else ""
    )

    page = PAGE_TEMPLATE.format(
        title=derived_title,
        slides=slides_html,
        oit_logo_html=oit_logo_html,
        ccv_logo_html=ccv_logo_html,
    )

    if out_path is None:
        out_path = os.path.splitext(md_path)[0] + ".html"

    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(page)

    print(f"  {len(chunks)} slides → {out_path}")
    return out_path


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(
        description="Markdown → self-contained CCV/Brown-branded HTML slideshow."
    )
    ap.add_argument("input",  help="Input Markdown file")
    ap.add_argument("output", nargs="?", help="Output HTML file (default: <input>.html)")
    ap.add_argument("--title",    help="Page title (default: first heading in document)")
    ap.add_argument("--oit-logo", default="oit-logo.png",
                    help="Path to OIT logo PNG (default: oit-logo.png)")
    ap.add_argument("--ccv-logo", default="ccv-logo.svg",
                    help="Path to CCV logo SVG (default: ccv-logo.svg)")
    ap.add_argument("--no-logos", action="store_true", help="Omit both logos")
    args = ap.parse_args()

    oit = "" if args.no_logos else args.oit_logo
    ccv = "" if args.no_logos else args.ccv_logo

    convert(args.input, args.output, args.title, oit, ccv)


if __name__ == "__main__":
    main()
