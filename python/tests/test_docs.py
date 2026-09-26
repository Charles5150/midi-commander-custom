"""Checks on the documentation: every link between pages leads somewhere.

Run from the repository root:

    python -m unittest python/tests/test_docs.py
"""

import glob
import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
MANUAL = os.path.join(ROOT, "docs", "manual")

LINK = re.compile(r"\]\(([^)\s]+)\)|<img[^>]*\ssrc=\"([^\"]+)\"")
HEADING = re.compile(r"^#+ (.*)$")


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def pages():
    found = [os.path.join(ROOT, n) for n in ("README.md", "CHANGELOG.md", "CONTRIBUTING.md")]
    return found + sorted(glob.glob(os.path.join(MANUAL, "**", "*.md"), recursive=True))


def strip_code(text):
    """The text without fenced code blocks and inline code, where a link is not a link."""
    text = re.sub(r"^```.*?^```", "", text, flags=re.S | re.M)
    return re.sub(r"`[^`\n]*`", "", text)


def anchors(path):
    """GitHub's anchors for the headings of a page."""
    out = set()
    fence = False
    for line in read(path).split("\n"):
        if line.lstrip().startswith("```"):
            fence = not fence
        m = None if fence else HEADING.match(line)
        if m:
            h = m.group(1).strip().lower().replace("`", "")
            h = re.sub(r"[^\w\- ]", "", h)
            out.add(h.replace(" ", "-"))
    return out


class LinkTest(unittest.TestCase):
    def test_links_resolve(self):
        broken = []
        for page in pages():
            text = strip_code(read(page))
            for m in LINK.finditer(text):
                target = m.group(1) or m.group(2)
                if re.match(r"[a-z]+:", target):
                    continue
                path, _, anchor = target.partition("#")
                dest = os.path.normpath(os.path.join(os.path.dirname(page), path)) if path else page
                rel = os.path.relpath(page, ROOT)
                if not os.path.exists(dest):
                    broken.append(f"{rel}: {target} (no such file)")
                elif anchor and dest.endswith(".md") and anchor not in anchors(dest):
                    broken.append(f"{rel}: {target} (no such heading)")
        self.assertEqual(broken, [], "\n".join(broken))


if __name__ == "__main__":
    unittest.main()
