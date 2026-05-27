"""
Scrape technical documentation from project GitHub repos.

Clones each repo shallowly, walks its docs folder, and writes every `.md` /
`.rst` file into ../markdown_files/ with frontmatter that preprocess.py already
understands (title, original_url, downloaded_at). reStructuredText is lightly
converted to readable text — good enough for embedding.

Add a new source by appending an entry to REPOS.
"""

import os
import re
import shutil
import subprocess
import tempfile
from datetime import datetime

REPOS = [
    {
        "name": "fastapi",
        "repo": "https://github.com/fastapi/fastapi.git",
        "docs_path": "docs/en/docs",
        "site_url": "https://fastapi.tiangolo.com/",
        "format": "md",
    },
    {
        "name": "pydantic",
        "repo": "https://github.com/pydantic/pydantic.git",
        "docs_path": "docs",
        "site_url": "https://docs.pydantic.dev/latest/",
        "format": "md",
    },
    {
        "name": "uvicorn",
        "repo": "https://github.com/encode/uvicorn.git",
        "docs_path": "docs",
        "site_url": "https://www.uvicorn.org/",
        "format": "md",
    },
    {
        "name": "uv",
        "repo": "https://github.com/astral-sh/uv.git",
        "docs_path": "docs",
        "site_url": "https://docs.astral.sh/uv/",
        "format": "md",
    },
    {
        "name": "langchain",
        "repo": "https://github.com/langchain-ai/docs.git",
        "docs_path": "src/oss/python",
        "site_url": "https://docs.langchain.com/oss/python/",
        "format": "md",
    },
    {
        "name": "llamaindex",
        "repo": "https://github.com/run-llama/llama_index.git",
        "docs_path": "docs/src/content/docs",
        "site_url": "https://docs.llamaindex.ai/en/stable/",
        "format": "md",
    },
    {
        "name": "pandas",
        "repo": "https://github.com/pandas-dev/pandas.git",
        "docs_path": "doc/source/user_guide",
        "site_url": "https://pandas.pydata.org/docs/user_guide/",
        "format": "rst",
    },
    {
        "name": "sklearn",
        "repo": "https://github.com/scikit-learn/scikit-learn.git",
        "docs_path": "doc/modules",
        "site_url": "https://scikit-learn.org/stable/modules/",
        "format": "rst",
    },
]

OUTPUT_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "markdown_files")
)


def sanitize(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]", "_", name)


def extract_title(content: str, fallback: str) -> str:
    # Markdown-style header
    m = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    if m:
        return m.group(1).strip()
    # RST-style: a line of text followed by ===== / ----- of equal or greater length
    rst_match = re.search(
        r"^(.+)\n([=\-~^*+#\"]{3,})$", content, re.MULTILINE
    )
    if rst_match and len(rst_match.group(2)) >= len(rst_match.group(1).strip()):
        return rst_match.group(1).strip()
    return fallback


def rst_to_text(text: str) -> str:
    """Light RST → readable text. Good enough for embedding; not a real converter."""
    # Inline roles: :func:`foo` → foo, :class:`Bar` → Bar
    text = re.sub(r":[\w:]+:`([^`]+)`", r"\1", text)
    # Strip `.. directive:: args` lines (note, code-block, currentmodule, etc.)
    text = re.sub(r"^\.\.\s+[\w-]+::.*$", "", text, flags=re.MULTILINE)
    # Strip standalone `..` comment markers
    text = re.sub(r"^\.\.\s*$", "", text, flags=re.MULTILINE)
    # Convert RST section headers (Title\n=====) to markdown headers
    lines = text.split("\n")
    out, i = [], 0
    level_map = {"=": 1, "-": 2, "~": 3, "^": 4, "*": 4, "+": 5, "#": 5, '"': 6}
    while i < len(lines):
        line = lines[i]
        if i + 1 < len(lines):
            nxt = lines[i + 1]
            stripped = line.strip()
            if (
                stripped
                and nxt
                and len(nxt) >= len(stripped)
                and len(set(nxt)) == 1
                and nxt[0] in level_map
            ):
                out.append("#" * level_map[nxt[0]] + " " + stripped)
                i += 2
                continue
        out.append(line)
        i += 1
    return "\n".join(out)


def build_doc_url(site_url: str, rel_path: str, fmt: str) -> str:
    no_ext = re.sub(r"\.(mdx|md|rst)$", "", rel_path).replace(os.sep, "/")
    if no_ext.endswith("/index"):
        no_ext = no_ext[: -len("/index")]
    base = site_url.rstrip("/")
    if fmt == "rst":
        return f"{base}/{no_ext}.html"
    return f"{base}/{no_ext}/"


def process_repo(spec: dict) -> int:
    print(f"📚 Cloning {spec['name']} ...")
    tmp = tempfile.mkdtemp(prefix=f"docs_{spec['name']}_")
    try:
        subprocess.run(
            ["git", "clone", "--depth", "1", spec["repo"], tmp],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )

        docs_dir = os.path.join(tmp, spec["docs_path"])
        if not os.path.isdir(docs_dir):
            print(f"   ⚠️  docs path '{spec['docs_path']}' not found in repo")
            return 0

        if spec["format"] == "rst":
            target_exts = (".rst",)
        else:
            target_exts = (".md", ".mdx")
        count = 0
        for root, _, files in os.walk(docs_dir):
            for fn in files:
                if not fn.endswith(target_exts):
                    continue

                src = os.path.join(root, fn)
                rel = os.path.relpath(src, docs_dir)

                with open(src, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()

                # Drop any pre-existing markdown frontmatter
                content = re.sub(
                    r"^---\n.*?\n---\n", "", content, count=1, flags=re.DOTALL
                )

                if spec["format"] == "rst":
                    content = rst_to_text(content)

                title = extract_title(content, rel)
                doc_url = build_doc_url(spec["site_url"], rel, spec["format"])
                stem = re.sub(r"\.(mdx|md|rst)$", "", rel)
                out_name = f"{spec['name']}__{sanitize(stem)}.md"
                out_path = os.path.join(OUTPUT_DIR, out_name)

                with open(out_path, "w", encoding="utf-8") as f:
                    f.write("---\n")
                    f.write(f'title: "{title}"\n')
                    f.write(f'original_url: "{doc_url}"\n')
                    f.write(f'downloaded_at: "{datetime.now().isoformat()}"\n')
                    f.write("---\n\n")
                    f.write(content)
                count += 1

        print(f"   ✅ {spec['name']}: saved {count} files")
        return count
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    total = 0
    for spec in REPOS:
        try:
            total += process_repo(spec)
        except subprocess.CalledProcessError as e:
            err = e.stderr.decode(errors="ignore") if e.stderr else ""
            print(f"❌ git clone failed for {spec['name']}: {err.strip()}")
        except Exception as e:
            print(f"❌ Failed to process {spec['name']}: {e}")
    print(f"\n✅ Done. Total files written: {total}")


if __name__ == "__main__":
    main()
