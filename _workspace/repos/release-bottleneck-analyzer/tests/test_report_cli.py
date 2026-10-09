from __future__ import annotations

import json
import xml.etree.ElementTree as ET

from release_analyzer.analysis import analyze, compare
from release_analyzer.cli import main
from release_analyzer.report import compare_markdown, stage_svg, to_json, to_markdown


def test_markdown_sections(before):
    md = to_markdown(analyze(before))
    for needle in (
        "# Release bottleneck report",
        "## Where the time goes",
        "## DORA-style metrics",
        "## Batching",
        "## Teams",
        "## Recommendations",
        "<- bottleneck",
        "Data quality",
    ):
        assert needle in md


def test_markdown_without_recommendations_says_so():
    from conftest import change, ts

    balanced = change(first=ts(2, 16), approved=ts(2, 23), merged=ts(3, 4), deployed=ts(3, 10))  # 7/7/5/6 h
    res = analyze([balanced])
    assert res.recommendations == [] and "No stage exceeds" in to_markdown(res)


def test_json_roundtrip(before):
    data = json.loads(to_json(analyze(before)))
    assert data["bottleneck"] == "release_wait" and len(data["stages"]) == 4


def test_svg_is_well_formed_and_escaped(before):
    svg = stage_svg(analyze(before), title="A & B <test>")
    root = ET.fromstring(svg)
    rects = [e for e in root.iter() if e.tag.endswith("rect")]
    assert len(rects) == 1 + 4 + 4  # background + bars + legend swatches
    assert "A &amp; B &lt;test&gt;" in svg and "(bottleneck)" in svg


def test_compare_markdown(before, after):
    md = compare_markdown(compare(analyze(before), analyze(after)), "before", "after")
    assert md.startswith("| Metric | before | after | Change |") and "Change failure rate" in md and "%" in md


def test_cli_end_to_end(tmp_path, capsys):
    assert main(["demo", "--out", str(tmp_path)]) == 0
    b, a = tmp_path / "before.json", tmp_path / "after.json"
    out, svg = tmp_path / "r.md", tmp_path / "r.svg"
    assert main(["analyze", str(b), "--out", str(out), "--svg", str(svg)]) == 0
    assert "Merged until in production" in out.read_text(encoding="utf-8")
    ET.parse(svg)
    capsys.readouterr()
    assert main(["analyze", str(b), "--format", "json"]) == 0
    assert json.loads(capsys.readouterr().out)["analyzed"] == 117
    assert main(["compare", str(b), str(a)]) == 0
    assert "Lead time p50" in capsys.readouterr().out
    assert main(["simulate", str(b), "--stage", "release_wait", "--reduction", "0.5"]) == 0
    assert "cut by 50%" in capsys.readouterr().out


def test_cli_working_hours_flag(tmp_path, capsys):
    main(["demo", "--out", str(tmp_path)])
    capsys.readouterr()
    assert main(["analyze", str(tmp_path / "before.json"), "--working-hours", "--tz-offset", "3"]) == 0
    assert "working hours" in capsys.readouterr().out


def test_cli_errors_exit_2(tmp_path, capsys):
    assert main(["analyze", str(tmp_path / "nope.json")]) == 2
    main(["demo", "--out", str(tmp_path)])
    assert main(["simulate", str(tmp_path / "before.json"), "--stage", "bogus", "--reduction", "0.5"]) == 2
    assert main(["simulate", str(tmp_path / "before.json"), "--stage", "review", "--reduction", "2"]) == 2
    assert capsys.readouterr().err.count("error:") == 3
