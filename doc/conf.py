# Configuration file for the Sphinx documentation builder.
from pygments.lexer import RegexLexer, bygroups
from pygments import token as t
from sphinx.highlighting import lexers

# -- Project information -----------------------------------------------------

project = "Plover"
copyright = "Open Steno Project"
author = copyright

release = "5.2.0"
version = release

# -- General configuration ---------------------------------------------------

extensions = [
    "sphinx_plover",
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.todo",
]

myst_enable_extensions = ["colon_fence"]

templates_path = ["_templates"]

exclude_patterns = []

pygments_style = "manni"
pygments_dark_style = "monokai"

source_suffix = [".rst", ".md"]

todo_include_todos = True

# -- Options for HTML output -------------------------------------------------

html_theme = "furo"

html_static_path = ["_static"]

html_title = f"{project} {version}"

html_favicon = "_static/favicon.ico"

html_css_files = [
    "custom.css",
]

html_theme_options = {
    "navigation_with_keys": True,
    "light_css_variables": {
        "color-brand-primary": "#3d6961",
        "color-brand-content": "#3d6961",
        "color-sidebar-background": "#3d6961",
        "color-sidebar-brand-text": "white",
        "color-sidebar-brand-text--hover": "white",
        "color-sidebar-caption-text": "white",
        "color-sidebar-link-text": "white",
        "color-sidebar-link-text--top-level": "white",
        "color-sidebar-item-background--hover": "#71a89f",
        "color-sidebar-item-expander-background--hover": "#71a89f",
        "color-inline-code-background": "transparent",
        "font-stack--header": "'Patua One', -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif, 'Apple Color Emoji', 'Segoe UI Emoji'",
        "font-stack--monospace": "'JetBrains Mono', SFMono-Regular, Menlo, Consolas, Monaco, Liberation Mono, Lucida Console, monospace",
    },
    "dark_css_variables": {
        "color-link": "#68a69b",
        "color-link--hover": "#68a69b",
    },
    "light_logo": "dolores.svg",
    "dark_logo": "dolores.svg",
}


class RTFLexer(RegexLexer):
    name = "rtf"

    tokens = {
        "root": [
            (r"(\\[a-z*\\_~\{\}]+)(-?\d+)?", bygroups(t.Keyword, t.Number.Integer)),
            (r"{\\\*\\cxcomment\s+", t.Comment.Multiline, "comment"),
            (
                r"({)(\\\*\\cxs)(\s+)([A-Z#0-9\-/#!,]+)(})",
                bygroups(t.Operator, t.Keyword, t.Text, t.String, t.Operator),
            ),
            (r"{", t.Operator),
            (r"}", t.Operator),
            (r".+?", t.Text),
        ],
        "comment": [
            (r"{", t.Comment.Multiline, "#push"),
            (r"}", t.Comment.Multiline, "#pop"),
            (r".+", t.Comment.Multiline),
        ],
    }


lexers["rtf"] = RTFLexer(startinline=True)
