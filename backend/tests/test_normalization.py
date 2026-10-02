from app.schemas.features import PENDING_FEATURES
from app.services.channel_service import normalize_channel
from app.services.report_service import build_feature_payload
from app.services.youtube_service import normalize_video
from tests.fixtures import CHANNELS_RESPONSE, VIDEOS_RESPONSE


def test_normalize_video():
    v = normalize_video(VIDEOS_RESPONSE["items"][0])
    assert v.video_id == "dQw4w9WgXcQ"
    assert v.url == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    assert v.duration_seconds == 542 and v.duration_formatted == "09:02"
    assert v.category_id == "28" and v.category_name == "Science & Technology"
    assert (v.statistics.views, v.statistics.likes, v.statistics.comments) == (100000, 5000, 500)
    assert v.thumbnail_url == "https://i.ytimg.com/high.jpg"
    assert v.language == "en" and v.caption_available is True
    assert v.source == "youtube_data_api"


def test_hidden_likes_become_none():
    item = {**VIDEOS_RESPONSE["items"][0], "statistics": {"viewCount": "10"}}
    v = normalize_video(item)
    assert v.statistics.likes is None and v.statistics.comments is None


def test_normalize_channel():
    c = normalize_channel(CHANNELS_RESPONSE["items"][0])
    assert c.subscriber_count == 12345 and c.total_views == 999999 and c.video_count == 42
    assert c.uploads_playlist_id == "UUuAXFkgsw1L7xaCfnd5JJOw"


def test_feature_payload_never_fabricates():
    v = normalize_video(VIDEOS_RESPONSE["items"][0])
    payload, readiness = build_feature_payload(v)
    for name in PENDING_FEATURES:
        assert getattr(payload, name) is None
        assert readiness[name] == "pending_pipeline"
    assert payload.view_count == 100000 and payload.transcript_available is True
    assert readiness["view_count"] == "available"
