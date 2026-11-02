import shutil
import argparse
import html
import json
import re
import sys
import os
from pathlib import Path
from dataclasses import dataclass

import latex2mathml.converter


current_file = Path(__file__).resolve()
PATT = r"^(?P<indent>[ \t]*)(?P<code>.*?)#\.\s*(?P<level>\d+)?\s?(?P<comment>.*)$"
COMMENT_RE = re.compile(PATT)
HTML_TEMPLATE = Path(current_file.parent.parent / "browser" / 'template.html').read_text(encoding="utf-8")


def linear_md_parser(src):
    @dataclass
    class Rule:
        start: str
        re: "re.Pattern"
        type: str
        raw: bool = False

    rules = [
        Rule("`", re.compile(r"`([^`]+)`"), "code", True),
        Rule("$",  re.compile(r"\$([^$]+)\$"), "math", True),
        Rule("**", re.compile(r"\*\*(.+?)\*\*"), "bold"),
        Rule("==", re.compile(r"==(.+?)=="), "highlight"),
        Rule("_",  re.compile(r"_([^_]+)_"), "italic"),
    ]
    unescape = re.compile(r"\\(.)")

    out, text, i, n = [], [], 0, len(src)

    def flush():
        if text:
            out.append({"type": "text", "value": "".join(text)})
            text.clear()

    while i < n:
        ch = src[i]

        if ch == "\\":
            text.append(src[i + 1] if i + 1 < n else "\\")
            i += 2 if i + 1 < n else 1
            continue

        rule = next((r for r in rules if src.startswith(r.start, i)), None)
        if rule:
            m = rule.re.match(src, i)
            if m:
                flush()
                v = m.group(1) if rule.raw else unescape.sub(r"\1", m.group(1))
                out.append({"type": rule.type, "value": v})
                i = m.end()
                continue

        text.append(ch)
        i += 1

    flush()

    def esc(s):
        return html.escape(s, quote=True)

    def mathml(v):
        try:
            return latex2mathml.converter.convert(v)
        except Exception:
            return f"<code>{esc(v)}</code>"

    R = {
        "text": lambda v: f"<span>{esc(v)}</span>",
        "code": lambda v: f"<code>{esc(v)}</code>",
        "bold": lambda v: f"<strong>{esc(v)}</strong>",
        "italic": lambda v: f"<em>{esc(v)}</em>",
        "highlight": lambda v: f"<mark>{esc(v)}</mark>",
        "math": mathml,
    }
    return "".join(R[t["type"]](t["value"]) for t in out)

def extract_comments(source: str) -> list[dict]:
    """Iterate lines and collect special `#.` comments."""
    items: list[dict] = []
    for lineno, line in enumerate(source.splitlines(), start=1):
        if m := COMMENT_RE.match(line):
            indent_raw = m.group("indent")
            indent_width = len(indent_raw.replace("\t", "    "))
            level_raw = m.group("level")
            level = int(level_raw) if level_raw is not None else 0
            items.append({
                    "line": lineno,
                    "indent": indent_width,
                    "level": level,
                    "raw_line": line.strip(),
                    "html": linear_md_parser(m.group("comment").strip()),
                })
    return items

def build_tree(items: list[dict]) -> list[dict]:
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

def render_html(files: list[dict], items: list[dict], title: str, file_path: str, max_lvl: int, count: int) -> str:
    return (
        HTML_TEMPLATE
        .replace("__TITLE__", html.escape(title))
        .replace("__COUNT__", str(count))
        .replace("__DATA_JSON__", json.dumps(items, ensure_ascii=False))
        .replace("__FILE_PATH_JSON__", json.dumps(file_path))
        .replace("__MAX_LEVEL__", str(max_lvl))
        .replace("__LIB_ALPINE__", files['alpine.min.js'])
        .replace("__SCRIPT__", files['script.js'])
        .replace("__STYLES__", files['style.css'])
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Extract `#.` comments to HTML.")
    ap.add_argument("input", type=Path, help="Python source file")
    ap.add_argument("-o", "--output", type=Path, default=Path("./dist"), help="output dir")
    ap.add_argument("-t", "--title", default=None)
    ap.add_argument("--dump", action="store_true", help="Print the parsed tree with raw/effective levels and exit (no HTML).")
    args = ap.parse_args()

    if not args.input.is_file():
        print(f"error: {args.input} not found", file=sys.stderr)

    else:
        source = args.input.read_text(encoding="utf-8")
        flat = extract_comments(source)
        tree = build_tree(flat)

        if args.dump:
            print(f"# {len(flat)} comment(s)")
            dump_tree(tree)

        else:
            max_lvl = max_level(tree)
            title = args.title or args.input.name
            abs_path = str(args.input.resolve())
            files = {}

            os.makedirs(args.output, exist_ok=True)
            for p in (current_file.parent.parent / "browser").iterdir():
                if p.is_file():
                    # shutil.copy(p, args.output)
                    with open(p) as f:
                        content = f.read()
                    files[p.name] = content

            print(files.keys())
            out = render_html(files, tree, title, abs_path, max_lvl, len(flat))
            (args.output / "index.html").write_text(out, encoding="utf-8")
            print(f"wrote {len(flat)} comment(s) -> {args.output}")


if __name__ == "__main__":
    raise SystemExit(main())
