import pytest

from src.preprocessing import canonicalize, clean_text, fix_cue_times, format_clock, parse_timestamp, remove_duplicate_cues, segment_transcript


@pytest.mark.parametrize("raw,sec", [("00:01:02,250", 62.25), ("1:02", 62.0), ("01:00:00.000", 3600.0), ("62.5", 62.5), (62.5, 62.5), ("0:00", 0.0)])
def test_parse_timestamp(raw, sec):
    assert parse_timestamp(raw) == pytest.approx(sec)


@pytest.mark.parametrize("bad", ["abc", "12:xx", "", -3])
def test_parse_timestamp_rejects_garbage(bad):
    with pytest.raises(ValueError):
        parse_timestamp(bad)


def test_format_clock():
    assert format_clock(75) == "01:15" and format_clock(3725) == "1:02:05"


def test_fix_malformed_times():
    cues = [dict(start=10, end=5, text="swapped"), dict(start=0, end=12, text="overlaps next"), dict(start=20, end=20, text="zero length"),
            dict(start=-3, end=2, text="negative"), dict(start=400, end=500, text="beyond video")]
    fixed, n = fix_cue_times(cues, duration=100)
    assert n >= 4
    assert all(c["end"] > c["start"] for c in fixed)
    assert all(a["end"] <= b["start"] + 1e-9 for a, b in zip(fixed, fixed[1:]))  # no overlaps
    assert max(c["end"] for c in fixed) <= 100 and all(c["text"] != "beyond video" for c in fixed)


def test_cleaning_keeps_negations_and_removes_artifacts():
    t = clean_text("[Music]  I will   never, ever  do that ♪♪ but however … it's   fine !!!!")
    assert "[Music]" not in t and "♪" not in t
    for kept in ("never", "but", "however"):  # contextual words must survive
        assert kept in t
    assert "  " not in t and t.count("!") <= 2


def test_duplicate_and_rolling_captions_removed():
    cues = [dict(start=0, end=2, text="hello there"), dict(start=2, end=4, text="hello there"),
            dict(start=4, end=6, text="we are"), dict(start=6, end=8, text="we are going to play")]
    out, removed = remove_duplicate_cues(cues)
    assert removed == 2 and [c["text"] for c in out] == ["hello there", "we are going to play"]
    assert out[1]["start"] == 4  # the rolling caption keeps its earlier start


def test_canonical_accepts_multiple_provider_formats():
    a = canonicalize("v", [dict(segment_id=1, start_time=0, end_time=5, text="hi")])
    b = canonicalize("v", [dict(segment_index=1, start_seconds=0.0, end_seconds=5.0, text="hi")])
    c = canonicalize("v", [dict(start="00:00:00,000", end="00:00:05,000", text="hi")])
    assert a.cues[0]["start"] == b.cues[0]["start"] == c.cues[0]["start"] == 0.0
    assert a.to_dict()["segments"][0].keys() == {"segment_id", "start", "end", "text"}


def test_canonical_drops_unparseable_but_keeps_going():
    tr = canonicalize("v", [dict(start="oops", end=3, text="bad"), dict(start=0, end=3, text="good")])
    assert len(tr.cues) == 1 and tr.corrections["unparseable_dropped"] == 1


def make_tr():
    return canonicalize("v", [dict(start=0, end=10, text="one two three four five"), dict(start=10, end=40, text="a b c d e f g h i j k l m n o p q r s t"),
                              dict(start=80, end=90, text="late words here")], duration=100)


@pytest.mark.parametrize("seg", [10, 15, 20, 30])
def test_segmentation_is_configurable_and_complete(seg):
    segs = segment_transcript(make_tr(), seg, 100)
    assert len(segs) == -(-100 // seg)  # ceil
    assert segs[0].start_time == 0 and segs[-1].end_time == 100
    assert all(abs((b.start_time - a.start_time) - seg) < 1e-6 for a, b in zip(segs, segs[1:]))
    # every word lands in exactly one segment: nothing lost, nothing duplicated
    assert sum(len(s.text.split()) for s in segs) == 5 + 20 + 3


def test_segmentation_preserves_positions_and_marks_empty():
    segs = segment_transcript(make_tr(), 15, 100)
    assert segs[0].relative_position == 0.0 and segs[3].relative_position == pytest.approx(45 / 100)
    assert segs[1].absolute_time == 15
    assert any(s.is_empty for s in segs) and segs[4].is_empty  # 60-75s has no captions
    assert segs[0].raw_text and segs[0].cue_ids == [0, 1]  # raw text and cue provenance preserved


def test_long_cue_splits_across_boundary():
    tr = canonicalize("v", [dict(start=0, end=30, text=" ".join(f"w{i}" for i in range(30)))], duration=30)
    segs = segment_transcript(tr, 10, 30)
    assert [len(s.text.split()) for s in segs] == [10, 10, 10]


def test_invalid_segment_size():
    with pytest.raises(ValueError):
        segment_transcript(make_tr(), 0, 100)
