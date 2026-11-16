"""``strip_markdown(emphasis=...)``: plain-text platforms (iMessage, SMS) can keep bold/italic visible
as CAPS or Unicode bold/italic glyphs instead of dropping it."""
import pytest

from gateway.platforms.helpers import plain_emphasis_mode, strip_markdown

TEXT = "## Plan\nThis is **very important** and *quietly* noted, also __big__ and _soft_."


def test_strip_is_the_default_and_unchanged() -> None:
    assert strip_markdown(TEXT) == "Plan\nThis is very important and quietly noted, also big and soft."
    assert strip_markdown(TEXT, emphasis="strip") == strip_markdown(TEXT)


def test_caps_uppercases_bold_and_headings_only() -> None:
    assert strip_markdown(TEXT, emphasis="caps") == (
        "PLAN\nThis is VERY IMPORTANT and quietly noted, also BIG and soft.")


def test_unicode_maps_bold_and_italic_to_math_glyphs() -> None:
    out = strip_markdown("**Hi 42** and *ok*", emphasis="unicode")
    assert out == "𝗛𝗶 𝟰𝟮 and 𝘰𝘬"
    assert "*" not in out


def test_unicode_leaves_non_ascii_alone() -> None:
    assert strip_markdown("**café ✅**", emphasis="unicode") == "𝗰𝗮𝗳é ✅"


@pytest.mark.parametrize("mode", ["caps", "unicode"])
def test_urls_and_code_inside_emphasis_stay_literal(mode: str) -> None:
    assert strip_markdown("**see https://example.com/a**", emphasis=mode) == "see https://example.com/a"
    assert strip_markdown("**run `ls -la`**", emphasis=mode) == "run ls -la"


@pytest.mark.parametrize("mode", ["caps", "unicode"])
def test_links_still_keep_targets(mode: str) -> None:
    out = strip_markdown("[**Open**](https://example.com)", keep_link_targets=True, emphasis=mode)
    assert out.endswith("\nhttps://example.com")


@pytest.mark.parametrize("raw,mode", [("CAPS", "caps"), (" Unicode ", "unicode"), ("bogus", "strip"),
                                      (None, "strip"), ("", "strip")])
def test_plain_emphasis_mode_normalises(raw, mode) -> None:
    assert plain_emphasis_mode(raw) == mode
