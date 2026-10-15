import argparse
import html
import json
import re
import sys
from pathlib import Path

COMMENT_RE = re.compile(
    r"^(?P<indent>[ \t]*)(?P<code>.*?)#\.\s*(?P<level>\d+)?\s?(?P<comment>.*)$"
)


def extract_comments(source: str) -> list[dict]:
    """Iterate lines and collect special `#.` comments."""
    items: list[dict] = []
    for lineno, line in enumerate(source.splitlines(), start=1):
        m = COMMENT_RE.match(line)
        if not m:
            continue
        indent_raw = m.group("indent")
        indent_width = len(indent_raw.replace("\t", "    "))
        level_raw = m.group("level")
        level = int(level_raw) if level_raw is not None else 0
        items.append(
            {
                "line": lineno,
                "indent": indent_width,
                "level": level,
                "raw_line": line.rstrip("\n"),
                "comment": m.group("comment").strip(),
            }
        )
    return items


def build_tree(items: list[dict]) -> list[dict]:
    """
    Nest items by indent, then compute effective levels bottom-up.

    effective(node) = max(own_level, max(effective(child) for child in children))
    """
    roots: list[dict] = []
    stack: list[dict] = []

    for item in items:
        item["children"] = []
        while stack and stack[-1]["indent"] >= item["indent"]:
            stack.pop()
        if stack:
            stack[-1]["children"].append(item)
        else:
            roots.append(item)
        stack.append(item)

    def compute(node: dict) -> int:
        child_levels = [compute(c) for c in node["children"]]
        eff = max([node["level"]] + child_levels)
        node["effective_level"] = eff
        return eff

    for r in roots:
        compute(r)

    return roots


def max_level(nodes: list[dict]) -> int:
    """Highest declared (raw) level present in the source."""
    best = 0
    stack = list(nodes)
    while stack:
        n = stack.pop()
        best = max(best, n["level"])
        stack.extend(n["children"])
    return best


def dump_tree(nodes: list[dict], depth: int = 0) -> None:
    for n in nodes:
        print(
            "  " * depth
            + f"L{n['line']:>4}  indent={n['indent']:<3} "
            + f"raw={n['level']}  eff={n['effective_level']}  "
            + f"| {n['comment'][:70]}"
        )
        dump_tree(n["children"], depth + 1)


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>__TITLE__</title>
<link rel="stylesheet"
      href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css">
<style>
  :root {
    --fg: #1f2328;
    --muted: #6a737d;
    --bg: #ffffff;
    --border: #e1e4e8;
    --code-bg: #f6f8fa;
    --accent: #0969da;
    --badge-bg: #ddf4ff;
    --badge-fg: #0969da;
  }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                 Helvetica, Arial, sans-serif;
    color: var(--fg);
    background: var(--bg);
    max-width: 900px;
    margin: 2rem auto;
    padding: 0 1.5rem;
    line-height: 1.55;
  }
  h1 { font-size: 1.5rem; margin-bottom: 0.25rem; }
  .meta { color: var(--muted); font-size: 0.9rem; margin-bottom: 0.75rem; }

  .toolbar {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    flex-wrap: wrap;
    margin-bottom: 1rem;
  }
  .toolbar button {
    font: inherit;
    font-size: 0.8rem;
    color: var(--muted);
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 0.2rem 0.6rem;
    cursor: pointer;
  }
  .toolbar button:hover { color: var(--accent); border-color: var(--accent); }

  .slider-group {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.85rem;
    color: var(--muted);
    flex: 1 1 260px;
    min-width: 220px;
  }
  .slider-group input[type=range] {
    flex: 1 1 auto;
    accent-color: var(--accent);
  }
  .slider-group .val {
    font-family: ui-monospace, monospace;
    min-width: 3.5em;
    text-align: right;
    color: var(--fg);
  }

  .hint {
    color: var(--muted);
    font-size: 0.8rem;
    margin-bottom: 1rem;
    font-style: italic;
  }

  .levelpill {
    flex: 0 0 auto;
    font-size: 0.65rem;
    font-family: ui-monospace, monospace;
    padding: 0.05em 0.4em;
    border-radius: 999px;
    background: var(--badge-bg);
    color: var(--badge-fg);
    margin-left: 0.4rem;
    user-select: none;
    vertical-align: 1px;
  }

  .row {
    display: flex;
    align-items: flex-start;
    border-left: 3px solid var(--border);
    padding: 0.4rem 0.9rem;
    margin: 0.35rem 0;
    border-radius: 0 4px 4px 0;
    cursor: pointer;
    transition: background 0.12s, border-color 0.12s;
  }
  .row:hover { background: #fafbfc; border-left-color: var(--accent); }
  .row:hover .lineno { color: var(--accent); }

  .node[data-eff="1"] > .row { background: #fbfbfc; }
  .node[data-eff="2"] > .row { background: #f8f8f9; }
  .node[data-eff="3"] > .row,
  .node[data-eff="4"] > .row,
  .node[data-eff="5"] > .row,
  .node[data-eff="6"] > .row,
  .node[data-eff="7"] > .row,
  .node[data-eff="8"] > .row,
  .node[data-eff="9"] > .row { background: #f6f6f7; }

  .caret {
    flex: 0 0 auto;
    width: 1.1rem;
    color: var(--muted);
    font-size: 0.7rem;
    line-height: 1.6;
    user-select: none;
    text-align: center;
  }
  .caret.clickable:hover { color: var(--accent); }
  .caret .badge {
    font-size: 0.65rem;
    color: var(--muted);
    margin-left: 0.1rem;
  }

  .body { flex: 1 1 auto; min-width: 0; }
  .body p { margin: 0.25rem 0; }
  .body code {
    background: var(--code-bg);
    padding: 0.1em 0.35em;
    border-radius: 3px;
    font-size: 0.9em;
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  }
  .body pre {
    background: var(--code-bg);
    padding: 0.75rem;
    border-radius: 6px;
    overflow-x: auto;
  }
  .body pre code { background: none; padding: 0; }

  .lineno {
    color: var(--muted);
    font-size: 0.75rem;
    font-family: ui-monospace, monospace;
    margin-right: 0.5rem;
    user-select: none;
  }

  .children {
    margin-left: 1.1rem;
    border-left: 1px dashed var(--border);
    padding-left: 0.4rem;
  }
  .node.collapsed > .children { display: none; }

  .footer {
    color: var(--muted);
    font-size: 0.8rem;
    margin-top: 2rem;
    padding-top: 1rem;
    border-top: 1px solid var(--border);
  }
</style>
</head>
<body>
<h1>__TITLE__</h1>
<div class="meta">__COUNT__ special comment(s) extracted</div>

<div class="toolbar">
  <div class="slider-group">
    <label for="level-slider">Min level:</label>
    <input id="level-slider" type="range" min="0" max="__MAX_LEVEL__"
           step="1" value="0">
    <span class="val" id="level-val">&ge; 0</span>
  </div>
  <button id="collapse-all">Collapse all</button>
  <button id="expand-all">Expand all</button>
</div>

<div class="hint">
  Click a comment to open it in VS Code. Click &#9654;/&#9660; to fold.
  Raise the slider to hide less-important comments.
</div>
<div id="comments"></div>
<div class="footer" id="footer"></div>

<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/contrib/auto-render.min.js"></script>
<script>
  const DATA = __DATA_JSON__;
  const FILE_PATH = __FILE_PATH_JSON__;
  const MAX_LEVEL = __MAX_LEVEL__;

  function renderMath(container) {
    renderMathInElement(container, {
      delimiters: [
        { left: "$$", right: "$$", display: true },
        { left: "$",  right: "$",  display: false },
        { left: "\\(", right: "\\)", display: false },
        { left: "\\[", right: "\\]", display: true },
      ],
      throwOnError: false,
    });
  }

  function toVscodePath(p) {
    p = p.replace(/\\\\/g, "/");
    if (/^[A-Za-z]:/.test(p)) {
      p = "/" + p[0].toLowerCase() + p.slice(1);
    }
    return p;
  }

  function openInVscode(line) {
    const url = "vscode://file" + toVscodePath(FILE_PATH) + ":" + line;
    console.log("opening:", url);
    window.location.href = url;
  }

  const FOLD_KEY = "fold:" + FILE_PATH;
  const LEVEL_KEY = "level:" + FILE_PATH;

  let foldState = {};
  try { foldState = JSON.parse(localStorage.getItem(FOLD_KEY) || "{}"); }
  catch (e) { foldState = {}; }

  function saveFoldState() {
    try { localStorage.setItem(FOLD_KEY, JSON.stringify(foldState)); }
    catch (e) {}
  }

  // Slider = MINIMUM level to show. 0 means "show everything".
  let currentMinLevel = 0;
  const savedMin = parseInt(localStorage.getItem(LEVEL_KEY) || "", 10);
  if (!Number.isNaN(savedMin) && savedMin >= 0 && savedMin <= MAX_LEVEL) {
    currentMinLevel = savedMin;
  }

  function saveLevel() {
    try { localStorage.setItem(LEVEL_KEY, String(currentMinLevel)); }
    catch (e) {}
  }

  function nodeKey(item) {
    return "L" + item.line + ":i" + item.indent;
  }

  // ---- Visibility: node visible iff effective_level >= currentMinLevel ----
  function nodeVisible(item) {
    return item.effective_level >= currentMinLevel;
  }

  function visibleChildren(item) {
    return item.children.filter(nodeVisible);
  }

  function visibleDescendants(item) {
    let n = 0;
    for (const c of item.children) {
      if (!nodeVisible(c)) continue;
      n += 1 + visibleDescendants(c);
    }
    return n;
  }

  const root = document.getElementById("comments");

  function renderNode(item) {
    const key = nodeKey(item);
    const kids = visibleChildren(item);
    const hasVisibleChildren = kids.length > 0;

    const node = document.createElement("div");
    node.className = "node";
    node.dataset.key = key;
    node.dataset.eff = String(item.effective_level);

    const row = document.createElement("div");
    row.className = "row";
    row.title = item.raw_line.split("#.")[0] + "(L" + item.line + ")";
    row.addEventListener("click", () => openInVscode(item.line));

    const caret = document.createElement("span");
    caret.className = "caret" + (hasVisibleChildren ? " clickable" : "");
    if (hasVisibleChildren) {
      caret.addEventListener("click", (e) => {
        e.stopPropagation();
        const collapsed = node.classList.toggle("collapsed");
        foldState[key] = collapsed;
        saveFoldState();
        updateCaret(caret, node, item);
      });
    }

    const body = document.createElement("div");
    body.className = "body";

    const lineno = document.createElement("span");
    lineno.className = "lineno";
    lineno.textContent = "L" + item.line;
    body.appendChild(lineno);

    const md = document.createElement("span");
    md.innerHTML = marked.parse(item.comment, { breaks: false, gfm: true });
    body.appendChild(md);

    if (item.level > 0) {
      const pill = document.createElement("span");
      pill.className = "levelpill";
      pill.textContent = "L" + item.level;
      body.appendChild(pill);
    }

    renderMath(body);

    row.appendChild(caret);
    row.appendChild(body);
    node.appendChild(row);

    if (hasVisibleChildren) {
      const kidsEl = document.createElement("div");
      kidsEl.className = "children";
      for (const child of kids) {
        kidsEl.appendChild(renderNode(child));
      }
      node.appendChild(kidsEl);

      if (foldState[key] === true) node.classList.add("collapsed");
      updateCaret(caret, node, item);
    } else {
      caret.textContent = "";
    }

    return node;
  }

  function updateCaret(caret, node, item) {
    const collapsed = node.classList.contains("collapsed");
    if (collapsed) {
      const n = visibleDescendants(item);
      caret.innerHTML = "&#9654;<span class='badge'>" + n + "</span>";
    } else {
      caret.textContent = "\u25BC";
    }
  }

  function renderAll() {
    root.innerHTML = "";
    for (const item of DATA) {
      if (!nodeVisible(item)) continue;
      root.appendChild(renderNode(item));
    }
    updateFooter();
  }

  function updateFooter() {
    let hidden = 0;
    let total = 0;
    (function walk(nodes) {
      for (const n of nodes) {
        total += 1;
        if (!nodeVisible(n)) hidden += 1;
        walk(n.children);
      }
    })(DATA);

    const footer = document.getElementById("footer");
    if (hidden === 0) {
      footer.textContent = total + " comment(s) shown.";
    } else {
      footer.textContent =
        hidden + " of " + total +
        " comment(s) hidden (below min level). Lower the slider to reveal.";
    }
  }

  const slider = document.getElementById("level-slider");
  const valLabel = document.getElementById("level-val");

  slider.value = String(currentMinLevel);
  valLabel.textContent = "\u2265 " + currentMinLevel;

  slider.addEventListener("input", () => {
    currentMinLevel = parseInt(slider.value, 10);
    valLabel.textContent = "\u2265 " + currentMinLevel;
    saveLevel();
    renderAll();
  });

  function setAllCollapsed(collapsed) {
    document.querySelectorAll("#comments .node[data-key]").forEach((node) => {
      if (!node.querySelector(":scope > .children")) return;
      node.classList.toggle("collapsed", collapsed);

      const caret = node.querySelector(":scope > .row > .caret");
      if (collapsed) {
        const kidCount =
          node.querySelectorAll(":scope > .children .node").length;
        caret.innerHTML = "&#9654;<span class='badge'>" + kidCount + "</span>";
      } else {
        caret.textContent = "\u25BC";
      }

      foldState[node.dataset.key] = collapsed;
    });
    saveFoldState();
  }

  document.getElementById("collapse-all")
    .addEventListener("click", () => setAllCollapsed(true));
  document.getElementById("expand-all")
    .addEventListener("click", () => setAllCollapsed(false));

  renderAll();
</script>
</body>
</html>
"""


def render_html(items: list[dict], title: str, file_path: str,
                max_lvl: int, count: int) -> str:
    return (
        HTML_TEMPLATE
        .replace("__TITLE__", html.escape(title))
        .replace("__COUNT__", str(count))
        .replace("__DATA_JSON__", json.dumps(items, ensure_ascii=False))
        .replace("__FILE_PATH_JSON__", json.dumps(file_path))
        .replace("__MAX_LEVEL__", str(max_lvl))
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Extract `#.` comments to HTML.")
    ap.add_argument("input", type=Path, help="Python source file")
    ap.add_argument("-o", "--output", type=Path, default=Path("index.html"))
    ap.add_argument("-t", "--title", default=None)
    ap.add_argument("--dump", action="store_true",
                    help="Print the parsed tree with raw/effective levels "
                         "and exit (no HTML).")
    args = ap.parse_args()

    if not args.input.is_file():
        print(f"error: {args.input} not found", file=sys.stderr)
        return 1

    source = args.input.read_text(encoding="utf-8")
    flat = extract_comments(source)
    tree = build_tree(flat)

    if args.dump:
        print(f"# {len(flat)} comment(s)")
        dump_tree(tree)
        return 0

    max_lvl = max_level(tree)
    title = args.title or args.input.name
    abs_path = str(args.input.resolve())

    out = render_html(tree, title, abs_path, max_lvl, len(flat))
    args.output.write_text(out, encoding="utf-8")
    print(f"wrote {len(flat)} comment(s) -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())