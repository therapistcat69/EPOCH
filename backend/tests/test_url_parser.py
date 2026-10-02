import pytest

from app.utils.youtube import InvalidYouTubeURL, extract_video_id, is_valid_youtube_url

VID = "dQw4w9WgXcQ"


@pytest.mark.parametrize(
    "url",
    [
        f"https://www.youtube.com/watch?v={VID}",
        f"https://youtube.com/watch?v={VID}",
        f"https://youtu.be/{VID}",
        f"https://www.youtube.com/embed/{VID}",
        f"https://m.youtube.com/watch?v={VID}&t=42s",
        f"https://www.youtube.com/watch?feature=share&v={VID}",
        f"youtu.be/{VID}?si=abc",
        f"  https://youtu.be/{VID}  ",
    ],
)
def test_supported_formats(url):
    assert extract_video_id(url) == VID
    assert is_valid_youtube_url(url)


@pytest.mark.parametrize(
    "url,fragment",
    [
        ("", "paste"),
        ("   ", "paste"),
        ("not a url", "valid URL"),
        ("https://vimeo.com/12345", "Only YouTube"),
        ("https://www.youtube.com/watch", "No video ID"),
        ("https://www.youtube.com/watch?v=", "No video ID"),
        ("https://www.youtube.com/", "No video ID"),
        ("https://youtu.be/", "No video ID"),
        ("https://www.youtube.com/watch?v=short", "malformed"),
        ("https://www.youtube.com/shorts/dQw4w9WgXcQ", "isn't supported"),
        ("https://www.youtube.com/@somechannel", "isn't supported"),
    ],
)
def test_invalid_urls(url, fragment):
    with pytest.raises(InvalidYouTubeURL) as exc:
        extract_video_id(url)
    assert fragment in exc.value.message
    assert exc.value.code == "INVALID_URL"
    assert not is_valid_youtube_url(url)
