import sys

import readme_renderer.markdown
import readme_renderer.rst
import readme_renderer.txt
from pygments.formatters import HtmlFormatter

_RENDERERS = {
    None: readme_renderer.rst,
    "": readme_renderer.rst,
    "text/plain": readme_renderer.txt,
    "text/x-rst": readme_renderer.rst,
    "text/markdown": readme_renderer.markdown,
}

_CSS = "\n".join(
    (
        '<style type="text/css">',
        "pre { background-color: #eeeeee }",
        HtmlFormatter().get_style_defs(),
        "</style>",
    )
)


def description_to_html(content, content_type):
    renderer = _RENDERERS.get(content_type, readme_renderer.rst)
    rendered = renderer.render(content)
    if rendered is None:
        rendered = readme_renderer.txt.render(content)
    return _CSS, rendered


def running_under_virtualenv():
    if sys.prefix != getattr(sys, "base_prefix", sys.prefix):
        # venv
        return True
    # virtualenv
    return hasattr(sys, "real_prefix")
