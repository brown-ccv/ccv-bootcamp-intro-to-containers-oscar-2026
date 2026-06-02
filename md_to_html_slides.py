#!/usr/bin/env python3
"""
md_to_html.py — convert a Markdown deck into a single, self-contained HTML slideshow.

Slides are separated by a line containing only `---`.

Key property: the output HTML is FULLY self-contained.
  * every <img> is read from disk and inlined as a base64 data URI
  * all CSS and JS are inlined (no CDN / no web fonts / no network)
So the resulting .html file can be opened or emailed and it just works offline.

Usage:
    python3 md_to_html.py slides.md                 # -> slides.html
    python3 md_to_html.py slides.md talk.html       # explicit output
    python3 md_to_html.py slides.md --title "My Talk"

Dependency: the `markdown` package (pip install markdown).
"""

import argparse
import base64
import mimetypes
import os
import re
import sys

try:
    import markdown  # type: ignore
except ImportError:
    sys.exit(
        "This script needs the 'markdown' package.\n"
        "Install it with:  pip install markdown"
    )


# --------------------------------------------------------------------------- #
# Image embedding — this is the core "self-contained" modification.
# --------------------------------------------------------------------------- #
IMG_TAG_RE = re.compile(r'(<img\b[^>]*?\bsrc=)(["\'])(.*?)\2([^>]*>)', re.IGNORECASE)


def _data_uri(path):
    """Read an image file and return a base64 data URI, or None if unreadable."""
    mime, _ = mimetypes.guess_type(path)
    if mime is None:
        # Fall back based on a few common extensions.
        ext = os.path.splitext(path)[1].lower().lstrip(".")
        mime = {
            "png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
            "gif": "image/gif", "svg": "image/svg+xml", "webp": "image/webp",
        }.get(ext, "application/octet-stream")
    with open(path, "rb") as fh:
        encoded = base64.b64encode(fh.read()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def embed_images(html, base_dir):
    """Replace every local <img src=...> with an inlined base64 data URI.

    Remote images (http/https/data:) are left untouched. Missing local files
    are replaced with a labelled placeholder so the deck still renders.
    """

    def repl(match):
        prefix, quote, src, suffix = match.groups()
        # Leave already-embedded or remote images alone.
        if src.startswith(("data:", "http://", "https://", "//")):
            return match.group(0)

        candidate = src if os.path.isabs(src) else os.path.join(base_dir, src)
        if os.path.isfile(candidate):
            try:
                uri = _data_uri(candidate)
                return f"{prefix}{quote}{uri}{quote}{suffix}"
            except OSError as exc:  # pragma: no cover
                sys.stderr.write(f"  ! could not read {candidate}: {exc}\n")
        else:
            sys.stderr.write(f"  ! image not found, using placeholder: {src}\n")

        # Build a visible placeholder that keeps any alt text.
        alt_match = re.search(r'alt=(["\'])(.*?)\1', suffix + prefix, re.IGNORECASE)
        alt = alt_match.group(2) if alt_match else os.path.basename(src)
        return (
            '<span class="img-missing">'
            f'<strong>Image:</strong> {alt}'
            f'<br><code>{os.path.basename(src)}</code>'
            "<br><em>drop this file next to the .md and re-run to embed it</em>"
            "</span>"
        )

    return IMG_TAG_RE.sub(repl, html)


# --------------------------------------------------------------------------- #
# Markdown -> slides
# --------------------------------------------------------------------------- #
def split_slides(text):
    """Split the document on lines that contain only `---`."""
    slides, current = [], []
    for line in text.splitlines():
        if line.strip() == "---":
            slides.append("\n".join(current))
            current = []
        else:
            current.append(line)
    slides.append("\n".join(current))
    return [s for s in (s.strip() for s in slides) if s]


def render_slide(md_text, converter, base_dir):
    converter.reset()
    body = converter.convert(md_text)
    body = embed_images(body, base_dir)
    # The very first heading level determines the slide's flavour for styling.
    flavour = "title" if re.match(r"\s*<h1", body) else "content"
    return f'<section class="slide slide-{flavour}"><div class="slide-inner">{body}</div></section>'


# --------------------------------------------------------------------------- #
# The self-contained HTML shell (inline CSS + JS, no external requests)
# --------------------------------------------------------------------------- #
PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
:root {{
  --bg:        #0c1016;
  --bg-2:      #11161f;
  --ink:       #e9eef5;
  --muted:     #93a1b3;
  --line:      #232c3a;
  --accent:    #e2231a;   /* Brown red */
  --accent-2:  #ffb454;   /* warm amber */
  --code-bg:   #0a0e14;
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

/* faint engineering grid + glow */
.backdrop {{
  position: fixed; inset: 0; z-index: 0; pointer-events: none;
  background:
    radial-gradient(1100px 600px at 78% -10%, rgba(226,35,26,0.16), transparent 60%),
    radial-gradient(900px 600px at 10% 110%, rgba(255,180,84,0.10), transparent 60%),
    linear-gradient(var(--line) 1px, transparent 1px) 0 0 / 100% 46px,
    linear-gradient(90deg, var(--line) 1px, transparent 1px) 0 0 / 46px 100%;
  opacity: .5;
}}

.deck {{ position: relative; z-index: 1; height: 100%; }}

.slide {{
  position: absolute; inset: 0;
  display: none;
  padding: 6vh 8vw 9vh;
  animation: fade .45s ease both;
}}
.slide.active {{ display: flex; }}
@keyframes fade {{ from {{ opacity: 0; transform: translateY(14px); }} to {{ opacity: 1; transform: none; }} }}

.slide-inner {{ margin: auto 0; width: 100%; max-width: 1100px; }}

/* ---------- typography ---------- */
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
  background: linear-gradient(var(--accent), var(--accent-2));
}}
.slide-title h2 {{ padding-left: 0; color: var(--accent-2); }}
.slide-title h2::before {{ display: none; }}
.slide-title .slide-inner > p {{ color: var(--muted); }}
h3 {{ font-family: var(--mono); font-size: 1.15rem; color: var(--accent-2); margin: 1.2em 0 .4em; }}

p {{ font-size: clamp(1.05rem, 1.7vw, 1.5rem); line-height: 1.5; margin: .5em 0; max-width: 60ch; }}

ul, ol {{ font-size: clamp(1.05rem, 1.7vw, 1.5rem); line-height: 1.5; padding-left: 1.1em; margin: .4em 0; }}
li {{ margin: .42em 0; }}
li::marker {{ color: var(--accent); }}
ul ul, ol ol, ul ol, ol ul {{ font-size: .92em; margin: .25em 0; }}

strong {{ color: #fff; }}
em {{ color: var(--muted); }}
a {{ color: var(--accent-2); text-decoration: none; border-bottom: 1px solid rgba(255,180,84,.35); }}

/* inline + block code */
code {{ font-family: var(--mono); font-size: .92em; }}
:not(pre) > code {{
  background: var(--code-bg); border: 1px solid var(--line);
  padding: .08em .4em; border-radius: 5px; color: var(--accent-2);
}}
pre {{
  background: var(--code-bg);
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 2.4rem 1.3rem 1.2rem;
  overflow: auto; position: relative;
  margin: .8em 0;
  box-shadow: 0 18px 40px -24px rgba(0,0,0,.8);
}}
pre::before {{  /* terminal traffic-lights */
  content: ""; position: absolute; top: .95rem; left: 1.2rem;
  width: 11px; height: 11px; border-radius: 50%;
  background: #ff5f56;
  box-shadow: 19px 0 #ffbd2e, 38px 0 #27c93f;
}}
pre code {{
  display: block; color: #d7e2f0; font-size: clamp(.8rem, 1.15vw, 1.05rem);
  line-height: 1.55; background: none; border: 0; padding: 0;
}}

/* tables */
table {{ width: 100%; border-collapse: collapse; margin: .7em 0; font-size: clamp(.85rem, 1.35vw, 1.2rem); }}
th, td {{ text-align: left; padding: .55em .7em; border-bottom: 1px solid var(--line); }}
thead th {{ color: var(--accent-2); font-family: var(--mono); font-weight: 700; border-bottom: 2px solid var(--accent); }}
tbody tr:hover {{ background: rgba(255,255,255,.02); }}
td code, th code {{ white-space: nowrap; }}

/* blockquote = callout */
blockquote {{
  margin: .9em 0; padding: .7em 1.1em;
  border-left: 3px solid var(--accent-2);
  background: linear-gradient(90deg, rgba(255,180,84,.10), transparent);
  border-radius: 0 10px 10px 0;
  font-size: clamp(.95rem, 1.45vw, 1.25rem); color: var(--ink);
}}
blockquote p {{ margin: .2em 0; }}

/* images */
img {{ max-width: 100%; max-height: 52vh; border-radius: 12px; border: 1px solid var(--line); display: block; margin: .6em auto; }}
.img-missing {{
  display: block; margin: .8em 0; padding: 1.4em; text-align: center;
  border: 1.5px dashed var(--line); border-radius: 12px;
  background: rgba(255,255,255,.02); color: var(--muted);
  font-size: clamp(.9rem, 1.4vw, 1.15rem);
}}
.img-missing code {{ color: var(--accent-2); }}

/* task-list checkboxes */
input[type=checkbox] {{ accent-color: var(--accent); transform: scale(1.15); margin-right: .4em; }}

/* ---------- chrome ---------- */
.progress {{
  position: fixed; top: 0; left: 0; height: 3px; z-index: 5;
  background: linear-gradient(90deg, var(--accent), var(--accent-2));
  transition: width .35s ease;
}}
.footer {{
  position: fixed; bottom: 1.6vh; left: 8vw; right: 8vw; z-index: 5;
  display: flex; justify-content: space-between; align-items: center;
  font-family: var(--mono); font-size: .8rem; color: var(--muted);
  letter-spacing: .04em;
}}
.footer .brand strong {{ color: var(--accent); }}
kbd {{
  font-family: var(--mono); font-size: .72rem; color: var(--muted);
  border: 1px solid var(--line); border-radius: 5px; padding: .1em .45em;
}}
@media (max-width: 700px) {{
  .slide {{ padding: 5vh 6vw 11vh; }}
  .footer {{ left: 6vw; right: 6vw; }}
  .footer .hint {{ display: none; }}
}}
</style>
</head>
<body>
<div class="backdrop"></div>
<div class="progress" id="progress"></div>
<div class="deck" id="deck">
{slides}
</div>
<div class="footer">
  <span class="brand"><strong>CCV</strong> · Reproducible Research with Containers</span>
  <span class="hint"><kbd>&larr;</kbd> <kbd>&rarr;</kbd> navigate · <kbd>F</kbd> fullscreen</span>
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
  function next() {{ show(i + 1); }}
  function prev() {{ show(i - 1); }}

  document.addEventListener("keydown", function (e) {{
    if (["ArrowRight", "PageDown", " ", "Enter"].indexOf(e.key) > -1) {{ e.preventDefault(); next(); }}
    else if (["ArrowLeft", "PageUp", "Backspace"].indexOf(e.key) > -1) {{ e.preventDefault(); prev(); }}
    else if (e.key === "Home") {{ show(0); }}
    else if (e.key === "End")  {{ show(slides.length - 1); }}
    else if (e.key === "f" || e.key === "F") {{
      if (!document.fullscreenElement) document.documentElement.requestFullscreen();
      else document.exitFullscreen();
    }}
  }});

  // click / tap right half -> next, left half -> prev
  document.getElementById("deck").addEventListener("click", function (e) {{
    if (e.target.closest("a, pre, code, table")) return;
    (e.clientX > window.innerWidth / 2 ? next : prev)();
  }});

  var start = parseInt((location.hash || "#1").slice(1), 10);
  show(isNaN(start) ? 0 : start - 1);
}})();
</script>
</body>
</html>
"""


def convert(md_path, out_path=None, title=None):
    base_dir = os.path.dirname(os.path.abspath(md_path))
    with open(md_path, "r", encoding="utf-8") as fh:
        text = fh.read()

    converter = markdown.Markdown(
        extensions=["fenced_code", "tables", "sane_lists", "attr_list", "nl2br"],
        output_format="html5",
    )

    chunks = split_slides(text)
    slides_html = "\n".join(render_slide(c, converter, base_dir) for c in chunks)

    if title is None:
        m = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
        title = m.group(1).strip() if m else "Slides"

    page = PAGE_TEMPLATE.format(title=title, slides=slides_html)

    if out_path is None:
        out_path = os.path.splitext(md_path)[0] + ".html"
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(page)

    print(f"  {len(chunks)} slides -> {out_path}")
    return out_path


def main():
    ap = argparse.ArgumentParser(description="Markdown -> self-contained HTML slideshow.")
    ap.add_argument("input", help="input Markdown file")
    ap.add_argument("output", nargs="?", help="output HTML file (default: <input>.html)")
    ap.add_argument("--title", help="page title (default: first H1 in the document)")
    args = ap.parse_args()
    convert(args.input, args.output, args.title)


if __name__ == "__main__":
    main()
