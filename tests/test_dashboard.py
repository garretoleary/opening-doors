"""The nightly dashboard: every number with its receipts, a zero with a note, thin evidence said plainly, a dated file."""
import json
from datetime import date
from pathlib import Path

from opening_doors import config, night_review as nr, review_report
from tests.test_nightly import make_run, line, words_ask


def two_runs():
    for r in ("20261017T010000000Z", "20261017T020000000Z"):
        make_run(r, [line("desk", "registered", "Researcher"), line("desk", "run started", "25 accounts"), line("Researcher", "read book", "25 accounts"),
                     line("Writer", "send email", "X", "denied", "not permitted, deliberate_check"), line("Planner", "read book", "", "denied", "not permitted"),
                     line("Writer", "STOPPED by AE", "", "stopped", "token revoked"),
                     {"time": "2026-10-17T01:02:03+00:00", "who": "desk", "what": "run finished", "on_what": "", "outcome": "ok", "detail": "£0.49 this run, 29 model calls"}],
                 {"ranked": [], "spend": {"gbp": 0.49, "calls": 29}})


def test_every_number_has_a_receipt_and_zeros_have_a_note():
    two_runs()
    s = nr.NightlyReview(ask=words_ask, today=date(2026, 10, 17)).run()
    dash = review_report.build()
    assert dash["ready"] and review_report.receipts_ok(dash) == []
    t = dash["tiles"]
    assert t["runs"]["value"] == 2 and [r["run"] for r in t["runs"]["receipts"]] == ["20261017T020000000Z", "20261017T010000000Z"]
    assert t["model_calls"]["value"] == 58 and t["cost_gbp"]["value"] == 0.98 and len(t["cost_gbp"]["receipts"]) == 2
    assert t["denials"]["value"] == 4 and all(r["line"] in (4, 5) for r in t["denials"]["receipts"])
    assert t["stops"]["value"] == 2 and all(r["line"] == 6 for r in t["stops"]["receipts"])
    scorer = next(a for a in dash["agents"] if a["name"] == "Scorer")
    assert scorer["actions"]["value"] == 0 and scorer["actions"]["receipts"] == [] and scorer["actions"]["note"] == "nothing to count"
    writer = next(a for a in dash["agents"] if a["name"] == "Writer")
    assert writer["stops"]["value"] == 2 and writer["stop_state"] == "stopped" and "2 stopped" in writer["words"]
    assert dash["checks_passed"]["value"] == 2 and len(dash["checks_passed"]["receipts"]) == 2
    assert dash["findings"][0]["family"] == "repeated denial" and dash["findings"][0]["receipts"]
    assert dash["night_review"]["model_calls"] == 0 and dash["night_review"]["denials"]["value"] == 0   # the stand-in model spends nothing
    assert dash["alliance"][0]["answer"].startswith("7 registered") and dash["alliance"][3]["receipts"]


def test_thin_evidence_says_so_and_the_dated_file_is_written():
    make_run("20261017T010000000Z", [line("desk", "run started", "25 accounts")])
    nr.NightlyReview(ask=words_ask, today=date(2026, 10, 17)).run()
    dash = review_report.build()
    assert dash["thin"] and dash["thin_message"] == "Not enough runs yet to judge."
    files = [p for p in config.REPORTS_DIR.iterdir() if p.is_file() and "dashboard-2026-10-17" in p.name]
    assert len(files) == 1
    text = files[0].read_text()
    assert "All data invented" in text and "Not enough runs yet to judge." in text and "Runs 1" in text and "## The four questions" in text


def test_receipts_rule_catches_a_number_without_one():
    dash = {"tiles": {"runs": {"value": 3, "receipts": [], "note": ""}, "stops": {"value": 0, "receipts": [], "note": ""}}, "agents": [], "findings": [],
            "checks_passed": {"value": 0, "receipts": [], "note": "no deliberate check seen"}, "night_review": {"denials": {"value": 0, "receipts": [], "note": "nothing to count"}}}
    breaches = review_report.receipts_ok(dash)
    assert breaches == ["tile runs: 3 without a receipt", "tile stops: zero without a note"]


def test_no_review_yet_is_said_plainly():
    assert review_report.build() == {"ready": False, "message": "No night review yet. Press Run night review."}
