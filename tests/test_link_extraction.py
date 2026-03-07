"""Tests for the link extraction service."""

from app.services.link_extraction_service import (
    ExtractedLink,
    extract_links,
    extract_youtube_video_id,
)

# ── Sample teacher material used in the spec ──────────────────────────

SAMPLE_TEXT = """\
Analytic Geometry:
Equation of the median: https://www.youtube.com/watch?v=4Qa6jDc9Tb0
Equation of the perpendicular bisector: https://www.youtube.com/watch?v=_2r6RrGu2iA
Equation of the altitude: https://www.youtube.com/watch?v=yzGCmTLz944
Triangles:
Sum of the Interior Angles of a Triangle (0:00 1:38): https://www.youtube.com/watch?v=Dnu-gPjaIdY
Similar Triangles: https://www.youtube.com/watch?v=BBJaxMSl0m0
Right Triangles:
Pythagorean Theorem: https://www.youtube.com/watch?v=AA6RfgP-AHU
Solving Right Triangles (SOHCAHTOA): https://www.youtube.com/watch?v=5tp74g4N8EY
Time Stamps:
0:00-3:50: Formulas
3:51-8:05: Finding the Unknown Sides
8:06-10:28: Finding the Unknown Angles
10:29-13:43: More Examples
13:44-End: Application Questions
Non-Right Triangles (Acute Triangles):
Sine Law: https://www.youtube.com/watch?v=bDPRWJdVzfs
Cosine Law: https://www.youtube.com/watch?v=9CGY0s-uCUE
"""


# ── extract_youtube_video_id ──────────────────────────────────────────


def test_youtube_watch_url():
    assert extract_youtube_video_id("https://www.youtube.com/watch?v=ABC123") == "ABC123"


def test_youtube_short_url():
    assert extract_youtube_video_id("https://youtu.be/XYZ789") == "XYZ789"


def test_youtube_embed_url():
    assert extract_youtube_video_id("https://www.youtube.com/embed/EMB456") == "EMB456"


def test_youtube_shorts_url():
    assert extract_youtube_video_id("https://www.youtube.com/shorts/SHT999") == "SHT999"


def test_non_youtube_url():
    assert extract_youtube_video_id("https://example.com/page") is None


def test_youtube_watch_with_extra_params():
    vid = extract_youtube_video_id(
        "https://www.youtube.com/watch?v=ABC123&list=PLxyz&t=30"
    )
    assert vid == "ABC123"


# ── extract_links — sample material ──────────────────────────────────


def test_sample_returns_nine_links():
    links = extract_links(SAMPLE_TEXT)
    assert len(links) == 9


def test_sample_all_youtube():
    links = extract_links(SAMPLE_TEXT)
    for link in links:
        assert link.resource_type == "youtube"
        assert link.youtube_video_id is not None


def test_sample_topic_headings():
    links = extract_links(SAMPLE_TEXT)
    headings = [link.topic_heading for link in links]
    assert headings == [
        "Analytic Geometry",
        "Analytic Geometry",
        "Analytic Geometry",
        "Triangles",
        "Triangles",
        "Right Triangles",
        "Right Triangles",
        "Non-Right Triangles (Acute Triangles)",
        "Non-Right Triangles (Acute Triangles)",
    ]


def test_sample_titles():
    links = extract_links(SAMPLE_TEXT)
    titles = [link.title for link in links]
    assert titles == [
        "Equation of the median",
        "Equation of the perpendicular bisector",
        "Equation of the altitude",
        "Sum of the Interior Angles of a Triangle (0:00 1:38)",
        "Similar Triangles",
        "Pythagorean Theorem",
        "Solving Right Triangles (SOHCAHTOA)",
        "Sine Law",
        "Cosine Law",
    ]


def test_sample_sohcahtoa_has_timestamp_description():
    links = extract_links(SAMPLE_TEXT)
    # SOHCAHTOA is index 6 (7th link)
    sohcahtoa = links[6]
    assert sohcahtoa.title == "Solving Right Triangles (SOHCAHTOA)"
    assert sohcahtoa.description is not None
    assert "0:00-3:50: Formulas" in sohcahtoa.description
    assert "13:44-End: Application Questions" in sohcahtoa.description


def test_sample_display_order_resets_per_topic():
    links = extract_links(SAMPLE_TEXT)
    orders = [(link.topic_heading, link.display_order) for link in links]
    assert orders == [
        ("Analytic Geometry", 0),
        ("Analytic Geometry", 1),
        ("Analytic Geometry", 2),
        ("Triangles", 0),
        ("Triangles", 1),
        ("Right Triangles", 0),
        ("Right Triangles", 1),
        ("Non-Right Triangles (Acute Triangles)", 0),
        ("Non-Right Triangles (Acute Triangles)", 1),
    ]


# ── extract_links — edge cases ──────────────────────────────────────


def test_external_link():
    links = extract_links("Check out https://example.com/page")
    assert len(links) == 1
    assert links[0].resource_type == "external_link"
    assert links[0].youtube_video_id is None


def test_empty_text():
    assert extract_links("") == []


def test_no_urls():
    assert extract_links("Just some text\nwith no links") == []


def test_title_stripping():
    links = extract_links("My Video - https://youtu.be/ABC123")
    assert links[0].title == "My Video"


def test_description_stops_at_next_url():
    text = """\
Topic:
Link one: https://youtu.be/AAA
Description for link one
Another desc line
Link two: https://youtu.be/BBB
"""
    links = extract_links(text)
    assert len(links) == 2
    assert links[0].description == "Description for link one\nAnother desc line"
    assert links[1].description is None


def test_description_stops_at_heading():
    text = """\
Topic A:
Link: https://youtu.be/AAA
Some notes
Topic B:
Link: https://youtu.be/BBB
"""
    links = extract_links(text)
    assert links[0].description == "Some notes"
    assert links[0].topic_heading == "Topic A"
    assert links[1].topic_heading == "Topic B"
