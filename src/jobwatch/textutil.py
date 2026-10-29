import html
import re
from html.parser import HTMLParser

_BREAK = {"p", "div", "br", "li", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6",
          "tr", "table", "section", "article", "header", "footer", "hr"}
_SKIP = {"script", "style"}


class _Extractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in _SKIP:
            self._skip += 1
        elif tag == "li":
            self.parts.append("\n\u2022 ")
        elif tag in _BREAK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in _SKIP:
            self._skip = max(0, self._skip - 1)
        elif tag in _BREAK:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def html_to_text(s):
    """Convert (possibly entity-escaped) HTML into plain text with line breaks."""
    if not s:
        return ""
    if "<" not in s and "&lt;" in s:
        s = html.unescape(s)
    p = _Extractor()
    p.feed(s)
    p.close()
    text = "".join(p.parts).replace("\xa0", " ")
    out = []
    for line in text.split("\n"):
        line = re.sub(r"[ \t]+", " ", line).strip()
        if line or (out and out[-1]):
            out.append(line)
    return "\n".join(out).strip()
