"""Recursos locais do relatório; o HTML gerado também funciona sem rede."""

from base64 import b64encode
from html import escape
from importlib.resources import files

_ASSETS = files("retail_pipeline").joinpath("assets")
FONT_CSS = (
    '@font-face{font-family:"Source Sans 3";font-style:normal;font-weight:200 900;'
    "font-display:swap;src:url(data:font/woff2;base64,"
    + b64encode(_ASSETS.joinpath("source-sans-3.woff2").read_bytes()).decode("ascii")
    + ') format("woff2");}'
)
FONT_NOTICE = escape(_ASSETS.joinpath("source-sans-LICENSE.md").read_text(encoding="utf-8"))
BRAND_MARK = (
    _ASSETS.joinpath("brand-mark.svg")
    .read_text(encoding="utf-8")
    .replace("<svg ", '<svg aria-hidden="true" ')
)
FAVICON = "data:image/svg+xml;base64," + b64encode(
    _ASSETS.joinpath("favicon.svg").read_bytes()
).decode("ascii")
