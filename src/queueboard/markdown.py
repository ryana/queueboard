from collections.abc import Callable

from markupsafe import Markup, escape

try:
    from markdown_it import MarkdownIt
except ImportError:
    _render: Callable[[str], str] | None = None
else:
    _render = MarkdownIt("commonmark", {"html": False}).render


def render_markdown(source: str) -> Markup:
    if _render is None:
        escaped = escape(source).replace("\n", Markup("<br>\n"))
        return Markup("<p>") + escaped + Markup("</p>")
    return Markup(_render(source))
