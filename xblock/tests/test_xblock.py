"""Tests for the pure iframe-building helper — not a constructed XBlock.

``SparkthPxcXBlock`` needs a real XBlock runtime to construct (mocking ``scope_ids`` into the
constructor does not work, mirroring the reference ``PxcXBlock``'s own test module), so the
iframe URL is built by a module-level function that takes plain ids and is testable on its own.
"""

from sparkth_pxc.xblock import build_embed_iframe


def test_the_iframe_points_at_sparkths_embed_route_with_a_token() -> None:
    html = build_embed_iframe(
        "https://sparkth.example/", "mcq", "placement-1", "course-v1:X+Y+Z", "learner-7", "s", 300
    )

    assert 'src="https://sparkth.example/api/v1/pxc/embed?token=' in html
    assert html.startswith("<iframe")


def test_the_iframe_is_sandboxed() -> None:
    html = build_embed_iframe("https://sparkth.example", "mcq", "placement-1", "course-v1:X+Y+Z", "learner-7", "s", 300)

    assert 'sandbox="allow-scripts allow-forms allow-same-origin"' in html


def test_a_trailing_slash_on_the_base_url_does_not_double_up() -> None:
    html = build_embed_iframe(
        "https://sparkth.example/", "mcq", "placement-1", "course-v1:X+Y+Z", "learner-7", "s", 300
    )

    assert "example//api" not in html
