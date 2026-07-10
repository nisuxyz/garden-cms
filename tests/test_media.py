# tests/test_media.py
"""
Unit tests for cms.media — upload validation and SVG sanitisation.
"""
from __future__ import annotations

import pytest

from cms.media import (
    MAX_FILE_SIZE,
    MediaError,
    _safe_filename,
    sanitize_svg,
)


# ── sanitiser ───────────────────────────────────────────────


_MALICIOUS_SVG = b"""<?xml version="1.0"?>
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="10" height="10">
  <script>alert(document.cookie)</script>
  <rect onclick="evil()" width="5" height="5"/>
  <a xlink:href="javascript:alert(1)"><circle r="1"/></a>
  <foreignObject width="5" height="5"><body onload="x"/></foreignObject>
  <image xlink:href="data:image/svg+xml,evil"/>
</svg>"""

_SAFE_SVG = b"""<?xml version="1.0"?>
<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10">
  <rect x="0" y="0" width="5" height="5" fill="red"/>
</svg>"""


def test_sanitize_svg_strips_script_event_handlers_and_script_urls():
    out = sanitize_svg(_MALICIOUS_SVG)
    low = out.lower()
    assert b"<script" not in low
    assert b"onclick" not in low
    assert b"javascript:" not in low
    assert b"foreignobject" not in low
    assert b"data:image/svg+xml" not in low
    # Benign content survives (the SVG's <rect>, <a>, <circle>, <image>
# remain — note ElementTree rewrites tags as ns0:rect but "rect" still
# appears as a substring).
    assert b"rect" in low
    assert b"circle" in low
    assert b"image" in low


def test_sanitize_svg_preserves_safe_svg():
    out = sanitize_svg(_SAFE_SVG)
    assert b"rect" in out
    assert b"fill=\"red\"" in out


def test_sanitize_svg_rejects_non_xml():
    with pytest.raises(MediaError, match="not well-formed"):
        sanitize_svg(b"this is not xml at all <svg>")


def test_sanitize_svg_rejects_non_svg_root():
    with pytest.raises(MediaError, match="root element"):
        sanitize_svg(b"<?xml version='1.0'?><html><body>not svg</body></html>")


def test_sanitize_svg_rejects_empty_input():
    with pytest.raises(MediaError):
        sanitize_svg(b"")


# ── filename / validation ──────────────────────────────────


def test_safe_filename_preserves_extension():
    name = _safe_filename("My Photo.PnG")
    assert name.endswith(".png")
    assert len(name) == 32 + len(".png")


def test_safe_filename_rejects_disallowed_extension():
    with pytest.raises(MediaError, match="not allowed"):
        _safe_filename("evil.exe")


def test_safe_filename_normalises_case():
    # .JPEG and .Jpeg map to a lowercase stored extension.
    assert _safe_filename("a.JPEG").endswith(".jpeg")
    assert _safe_filename("a.Jpeg").endswith(".jpeg")


def test_max_file_size_is_reasonable():
    # 10 MB — guards against accidental drops.
    assert MAX_FILE_SIZE == 10 * 1024 * 1024