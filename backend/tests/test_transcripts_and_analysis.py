import pytest

from app.errors import AppError
from app.schemas.transcript import SegmentIn
from app.services import transcript_service as ts
from app.services.transcript_analysis_service import analyze_transcript

SRT = """1
00:00:00,000 --> 00:00:05,000
Today we are comparing the best <i>AI tools</i> for developers.

2
00:00:05,000 --> 00:00:12,500
First, why does this matter? Because the AI tools save hours.

3
00:01:02,250 --> 00:01:08,000
Please subscribe to the channel and hit the like button.
"""

VTT = """WEBVTT

NOTE this is a comment

00:00.000 --> 00:04.000 align:start
Welcome back to the channel.

00:04.000 --> 00:09.000
We will build a small project.

01:00:00.000 --> 01:00:02.000
Late cue.
"""


def test_srt_parser():
    segs = ts.parse_cues(SRT)
    assert [s.segment_index for s in segs] == [0, 1, 2]
    assert segs[0].text == "Today we are comparing the best AI tools for developers."  # tags stripped
    assert (segs[2].start_seconds, segs[2].end_seconds) == (62.25, 68.0)


def test_vtt_parser_handles_header_notes_and_short_timestamps():
    segs = ts.parse_cues(VTT)
    assert len(segs) == 3 and segs[0].text == "Welcome back to the channel."
    assert segs[1].start_seconds == 4.0 and segs[2].start_seconds == 3600.0


def test_plain_text_with_timestamps_is_exact():
    segs, estimated = ts.parse_plain_text("0:00 Intro to the topic\n0:14 Main point here\n1:05 Wrap up", 100)
    assert estimated is False and [s.start_seconds for s in segs] == [0, 14, 65] and segs[-1].end_seconds == 100


def test_plain_text_without_timestamps_is_flagged_estimated():
    segs, estimated = ts.parse_plain_text("This is one sentence. Here is another one! And a third?", 60)
    assert estimated is True and len(segs) == 3
    assert segs[0].start_seconds == 0 and segs[-1].end_seconds == pytest.approx(60, abs=0.5)


def test_hindi_text_is_supported():
    segs, _ = ts.parse_plain_text("आज हम बात करेंगे एआई टूल्स के बारे में। यह वीडियो बहुत उपयोगी है।", 30)
    assert len(segs) == 2 and "एआई" in segs[0].text


def test_parse_upload_errors():
    with pytest.raises(AppError) as e:
        ts.parse_upload("srt", "   ", None, None)
    assert e.value.code == "TRANSCRIPT_EMPTY"
    with pytest.raises(AppError) as e:
        ts.parse_upload("vtt", "WEBVTT\n\nno cues here", None, None)
    assert e.value.code == "TRANSCRIPT_PARSE_FAILED"


def test_parse_upload_normalizes_to_internal_schema():
    data = ts.parse_upload("srt", SRT, "en", 600)
    assert data.provider == "uploaded" and data.language == "en" and data.timestamps_estimated is False
    assert data.segments[1].language == "en" and "AI tools" in data.full_text


async def test_caption_provider_disabled_by_default(yt_client):
    assert await ts.YouTubeCaptionProvider(yt_client).fetch("dQw4w9WgXcQ") is None  # needs opt-in + extra scope


# ---------------------------------------------------------------- analysis engine
def S(i, start, end, text):
    return SegmentIn(segment_index=i, start_seconds=start, end_seconds=end, text=text)


SEGS = [
    S(0, 0, 6, "Hey everyone, welcome back."),
    S(1, 6, 14, "Today we compare the best AI coding agents for developers, why does it matter?"),
    S(2, 14, 30, "Cursor and Claude Code are AI coding agents that edit files and run tests automatically."),
    S(3, 30, 50, "Pricing differs because Cursor charges a monthly subscription while Claude Code bills usage."),
    S(4, 50, 70, "Please subscribe to the channel and hit the like button."),
    S(5, 70, 90, "Cursor and Claude Code are AI coding agents that edit files and run tests automatically."),
]


def test_analysis_hook_promise_cta_and_repetition():
    a = analyze_transcript(SEGS, "Best AI Coding Agents for Developers", None, 90)
    assert a.segment_count == 6 and a.duration_seconds == 90
    assert a.hook_latency_seconds is not None and a.hook_latency_seconds <= 14  # question/title keyword inside 30s
    assert a.promise_gap_seconds is not None and a.promise_gap_seconds <= 14
    assert [c.type for c in a.ctas][:2] == ["subscribe", "like"] and a.ctas[0].start == 50
    assert a.segments[4].is_cta and not a.segments[4].is_hook
    rep = a.repeated_ideas[0]
    assert (rep.start, rep.end) == (70, 90) and rep.similar_to == [{"start": 14, "end": 30}] and rep.similarity > 0.95
    assert a.segments[5].repetition_score > 0.95 and a.segments[5].semantic_novelty < 0.05
    assert a.segments[1].is_question
    assert a.average_words_per_minute and 5 < a.average_words_per_minute < 200
    assert a.silence_rate is None  # needs audio: unavailable, not invented


def test_analysis_features_are_bounded_and_ordered():
    a = analyze_transcript(list(reversed(SEGS)), "x", None, None)  # input order must not matter
    assert [s.start for s in a.segments] == sorted(s.start for s in a.segments)
    for f in a.segments:
        assert 0 <= f.semantic_novelty <= 1 and 0 <= f.information_density <= 1 and 0 <= f.repetition_score <= 1


def test_hinglish_cta_detected():
    a = analyze_transcript([S(0, 0, 5, "Channel ko subscribe karo aur like karo")], "t", None, 5)
    assert {c.type for c in a.ctas} >= {"subscribe", "like"}
