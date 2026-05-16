"""End-to-end contracts for the user's primary journey: find a job.

The tests stay offline: fake portal data replaces network scraping, and LLM,
document generation, and application submission are monkeypatched. The goal is
to pin the user-visible workflow:

- recent postings only;
- usable 100+ word descriptions before scoring;
- rejection reasons visible for review;
- user feedback can trigger reassessment;
- top 10 shortlisted jobs get tailored documents and tailored scores;
- confirmed applications are routed through email/form channels and then
  monitored CRM-style.
"""
from __future__ import annotations

import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path

from jobbot.config import (
    ApplyConfig, Config, DigestConfig, EnrichmentConfig, Secrets, SourceConfig,
)
from jobbot.models import ApplyResult, GeneratedDocs, JobPosting, JobStatus, ScoreResult
from jobbot.profile import Profile


def _profile() -> Profile:
    return Profile(
        personal={"full_name": "Jane Doe", "email": "jane@example.com"},
        preferences={"remote": True},
        deal_breakers={"keywords": [], "industries": [], "on_site_only": False},
        must_have_skills=[],
    )


def _secrets() -> Secrets:
    return Secrets(
        anthropic_api_key="dummy",
        gmail_address="jane@example.com",
        gmail_app_password="dummy",
        notify_to="jane@example.com",
    )


def _config(*, auto_submit: bool = False) -> Config:
    return Config(
        score_threshold=70,
        max_jobs_per_run=50,
        output_dir="output",
        apply=ApplyConfig(dry_run=False, per_run_limit=10),
        digest=DigestConfig(generate_docs_above_score=70, max_per_email=100),
        enrichment=EnrichmentConfig(per_run_cap=100),
        sources={
            "fake": SourceConfig(
                enabled=True,
                auto_submit=auto_submit,
                queries=[{"q": "target role"}],
            )
        },
    )


def _body(token: str, words: int = 140, *, email: str | None = None) -> str:
    text = " ".join([token] * words)
    if email:
        text += f" Apply by email: {email}"
    return text


def _job(
    job_id: str,
    *,
    score_hint: int = 80,
    posted_at: datetime | None = None,
    apply_url: str | None = None,
) -> JobPosting:
    url = f"https://example.com/jobs/{job_id}"
    return JobPosting(
        id=job_id,
        source="fake",
        title=f"Senior Product Manager {score_hint}",
        company=f"Company {job_id}",
        url=url,  # type: ignore[arg-type]
        apply_url=apply_url or url,  # type: ignore[arg-type]
        posted_at=posted_at,
        description="listing snippet",
    )


class FakePortal:
    source = "fake"

    def __init__(self, jobs: list[JobPosting], details: dict[str, str]) -> None:
        self.jobs = jobs
        self.details = details

    def fetch(self, _query):
        return list(self.jobs)

    def fetch_detail(self, job: JobPosting) -> JobPosting:
        return job.model_copy(update={"description": self.details[job.id]})


def _fake_generate_documents(job, _profile, _base_cv, _secrets, config, **_kwargs):
    out_root = Path(config.output_dir).resolve() / "test-run" / job.id
    out_root.mkdir(parents=True, exist_ok=True)
    cv_md = f"# Tailored CV for {job.company}\n\nEvidence for {job.title}.\n"
    cl_md = f"Dear {job.company},\n\nI am interested because the role matches.\n"
    (out_root / "cv.md").write_text(cv_md)
    (out_root / "cover_letter.md").write_text(cl_md)
    (out_root / "cv.html").write_text(f"<html><body>{job.company}</body></html>")
    (out_root / "cover_letter.html").write_text("<html><body>Letter</body></html>")
    return GeneratedDocs(
        cv_md=cv_md,
        cv_html="<html></html>",
        cover_letter_md=cl_md,
        cover_letter_html="<html></html>",
        output_dir=str(out_root),
    )


def _patch_pipeline(
    monkeypatch,
    tmp_path: Path,
    *,
    portal: FakePortal,
    scores: dict[str, int],
    heuristic_reject_ids: set[str] | None = None,
    tailored_score: int = 93,
) -> None:
    import jobbot.pipeline as pipeline
    from jobbot.scoring import CannotScore

    monkeypatch.setattr("jobbot.state.DB_PATH", tmp_path / "jobbot.db")
    monkeypatch.setattr(pipeline, "REGISTRY", {"fake": portal})
    monkeypatch.setattr(pipeline, "load_profile", lambda: _profile())
    monkeypatch.setattr(pipeline, "load_base_cv", lambda: "Base CV")
    monkeypatch.setattr(pipeline, "send_digest", lambda *_a, **_kw: None)
    monkeypatch.setattr(pipeline, "generate_documents", _fake_generate_documents)
    monkeypatch.setattr(pipeline, "generate_application_package", _fake_generate_documents)
    # The pipeline runs housekeep_shortlist after scoring to demote dead
    # listings. Test fixtures use example.com/jobs/<id> URLs that return
    # 404 → would be marked listing_expired. Stub it out for tests.
    from jobbot.housekeep import HousekeepReport
    monkeypatch.setattr(
        pipeline, "housekeep_shortlist",
        lambda *_a, **_kw: HousekeepReport(0, 0, 0, 0, 0, [], []),
    )

    reject_ids = heuristic_reject_ids or set()

    def _heuristic(job, _profile):
        if job.id in reject_ids:
            return False, "user deal-breaker: synthetic mismatch"
        return True, ""

    def _score(job, _profile, _secrets, *, description_scraped, **_kwargs):
        if not description_scraped:
            raise CannotScore("no_body: description_scraped flag is false")
        return ScoreResult(score=scores[job.id], reason=f"base score for {job.id}")

    monkeypatch.setattr(pipeline, "passes_heuristic", _heuristic)
    monkeypatch.setattr(pipeline, "llm_score", _score)
    monkeypatch.setattr(
        pipeline,
        "llm_score_tailored",
        lambda *_a, **_kw: ScoreResult(score=tailored_score, reason="tailored lift"),
    )


def test_goal_run_filters_recent_jobs_scores_and_surfaces_rejection_reasons(
    tmp_path: Path, monkeypatch,
) -> None:
    import jobbot.pipeline as pipeline
    from jobbot.dashboard.server import _load_legacy_dashboard_module
    from jobbot.state import connect

    now = datetime.now(tz=timezone.utc)
    jobs = [
        _job("recent_good", score_hint=85, posted_at=now - timedelta(days=1)),
        _job("recent_low", score_hint=62, posted_at=now - timedelta(days=2)),
        _job("recent_short", score_hint=80, posted_at=now - timedelta(days=1)),
        _job("filtered", score_hint=91, posted_at=now - timedelta(days=1)),
        _job("old_good", score_hint=95, posted_at=now - timedelta(days=9)),
    ]
    details = {
        "recent_good": _body("relevant", 150),
        "recent_low": _body("partial", 150),
        "recent_short": _body("thin", 20),
        "filtered": _body("blocked", 150),
        "old_good": _body("old", 150),
    }
    _patch_pipeline(
        monkeypatch,
        tmp_path,
        portal=FakePortal(jobs, details),
        scores={
            "recent_good": 85,
            "recent_low": 62,
            "recent_short": 80,
            "filtered": 91,
            "old_good": 95,
        },
        heuristic_reject_ids={"filtered"},
    )
    config = _config()
    config.output_dir = str(tmp_path / "out")

    result = pipeline.run_once(config, _secrets())

    assert result["n_fetched"] == 4
    assert result["diagnostics"]["stages"]["stale_postings"] == 1
    with connect(tmp_path / "jobbot.db") as conn:
        rows = {
            row["id"]: row
            for row in conn.execute(
                "SELECT id, status, score, score_reason, output_dir FROM seen_jobs"
            ).fetchall()
        }
    assert "old_good" not in rows
    assert rows["recent_good"]["status"] == JobStatus.GENERATED.value
    assert rows["recent_good"]["score"] == 85
    assert rows["recent_good"]["output_dir"]
    assert rows["recent_low"]["status"] == JobStatus.BELOW_THRESHOLD.value
    assert rows["recent_low"]["score_reason"] == "base score for recent_low"
    assert rows["recent_short"]["status"] == JobStatus.CANNOT_SCORE_NO_BODY.value
    assert rows["filtered"]["status"] == JobStatus.FILTERED.value
    assert "deal-breaker" in rows["filtered"]["score_reason"]

    client = _load_legacy_dashboard_module().app.test_client()
    positions = {row["id"]: row for row in client.get("/api/positions").get_json()}
    assert positions["recent_low"]["score_reason"] == "base score for recent_low"
    shortlist = client.get("/api/shortlist?min_score=70").get_json()["jobs"]
    shortlist_ids = {row["id"] for row in shortlist}
    assert "recent_good" in shortlist_ids
    assert "recent_low" not in shortlist_ids


def test_top_10_shortlist_gets_tailored_cv_cover_letter_and_rescore(
    tmp_path: Path, monkeypatch,
) -> None:
    import jobbot.pipeline as pipeline
    from jobbot.state import connect

    jobs: list[JobPosting] = []
    details: dict[str, str] = {}
    scores: dict[str, int] = {}
    for i in range(12):
        score = 89 + i
        job_id = f"fit_{i:02d}"
        jobs.append(_job(job_id, score_hint=score))
        details[job_id] = _body("strong", 130)
        scores[job_id] = score

    _patch_pipeline(
        monkeypatch,
        tmp_path,
        portal=FakePortal(jobs, details),
        scores=scores,
        tailored_score=99,
    )
    config = _config()
    config.output_dir = str(tmp_path / "out")

    result = pipeline.run_once(config, _secrets())

    assert result["n_generated"] == 10
    with connect(tmp_path / "jobbot.db") as conn:
        generated = conn.execute(
            "SELECT id, score, score_tailored, output_dir FROM seen_jobs "
            "WHERE output_dir IS NOT NULL ORDER BY score DESC"
        ).fetchall()
        skipped = conn.execute(
            "SELECT id, output_dir FROM seen_jobs WHERE id IN ('fit_00', 'fit_01')"
        ).fetchall()

    assert [row["id"] for row in generated] == [
        f"fit_{i:02d}" for i in range(11, 1, -1)
    ]
    assert all(row["score_tailored"] == 99 for row in generated)
    for row in generated:
        out = Path(row["output_dir"])
        assert (out / "cv.md").exists()
        assert (out / "cover_letter.md").exists()
    assert all(row["output_dir"] is None for row in skipped)


def _load_feedback_script():
    script_path = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "rescore_from_feedback.py"
    )
    spec = importlib.util.spec_from_file_location("rescore_from_feedback_test", script_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_user_comment_rescore_can_promote_rejected_posting_to_shortlist(
    tmp_path: Path, monkeypatch,
) -> None:
    from jobbot.dashboard.server import _load_legacy_dashboard_module
    from jobbot.state import connect, update_enrichment, update_status, upsert_new

    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    job = _job("feedback_1", score_hint=61)
    with connect(db) as conn:
        upsert_new(conn, [job])
        update_enrichment(
            conn,
            "feedback_1",
            description_full=_body("fintech", 150),
            description_scraped=True,
            description_word_count=150,
            seniority="Senior",
            salary_text=None,
            apply_email=None,
        )
        update_status(
            conn,
            "feedback_1",
            JobStatus.BELOW_THRESHOLD,
            score=61,
            reason="rejected: assumes no fintech context",
            discard_reason="no fintech context",
        )

    review_md = tmp_path / "score_downgrades_review.md"
    review_md.write_text(
        "## feedback_1\n\n"
        "### Your comment:\n\n"
        "I do have fintech launch experience; it is in my cover letter sample.\n"
    )
    feedback = _load_feedback_script()
    seen_feedback: list[str] = []
    monkeypatch.setattr(feedback, "REVIEW_MD", review_md)
    monkeypatch.setattr(feedback, "OUT_CSV", tmp_path / "score_after_feedback.csv")
    monkeypatch.setattr(feedback, "load_profile", lambda: _profile())
    monkeypatch.setattr(feedback, "load_secrets", lambda: _secrets())

    def _rescore(
        job, _profile, _secrets, *, description_scraped, user_feedback, **_kwargs,
    ):
        assert description_scraped is True
        assert len(job.description.split()) >= 100
        seen_feedback.append(user_feedback)
        return ScoreResult(score=78, reason="feedback confirms fintech experience")

    monkeypatch.setattr(feedback, "llm_score", _rescore)

    rc = feedback.main()

    assert rc == 0
    assert seen_feedback == [
        "I do have fintech launch experience; it is in my cover letter sample."
    ]
    with connect(db) as conn:
        row = conn.execute(
            "SELECT status, score, score_reason FROM seen_jobs WHERE id = 'feedback_1'"
        ).fetchone()
    assert row["status"] == JobStatus.BELOW_THRESHOLD.value
    assert row["score"] == 78
    assert row["score_reason"] == "feedback confirms fintech experience"

    client = _load_legacy_dashboard_module().app.test_client()
    shortlist_ids = {
        row["id"]
        for row in client.get("/api/shortlist?min_score=70").get_json()["jobs"]
    }
    assert "feedback_1" in shortlist_ids


def test_confirmed_applications_route_by_email_or_form_and_enter_crm(
    tmp_path: Path, monkeypatch,
) -> None:
    import jobbot.pipeline as pipeline
    from jobbot.dashboard.server import _load_legacy_dashboard_module

    email_job = _job("email_apply", score_hint=90, apply_url=None)
    form_job = _job(
        "form_apply",
        score_hint=91,
        apply_url="https://boards.greenhouse.io/acme/jobs/123",
    )
    details = {
        "email_apply": _body("email", 150, email="careers@acme.example"),
        "form_apply": _body("form", 150),
    }
    _patch_pipeline(
        monkeypatch,
        tmp_path,
        portal=FakePortal([email_job, form_job], details),
        scores={"email_apply": 90, "form_apply": 91},
    )
    config = _config(auto_submit=True)
    config.output_dir = str(tmp_path / "out")
    applied_channels: dict[str, str] = {}

    def _apply(job, _profile, _docs, _secrets, _config):
        applied_channels[job.id] = (
            "email" if job.apply_email
            else "form" if "greenhouse" in str(job.apply_url).lower()
            else "manual"
        )
        return ApplyResult(
            status=JobStatus.APPLY_SUBMITTED,
            submitted=True,
            dry_run=False,
            confirmation_url=f"https://confirm.example/{job.id}",
        )

    monkeypatch.setattr(pipeline, "apply_to_job", _apply)

    result = pipeline.run_once(config, _secrets())

    assert result["n_applied"] == 2
    assert applied_channels == {"form_apply": "form", "email_apply": "email"}

    client = _load_legacy_dashboard_module().app.test_client()
    applications = {
        row["job_id"]: row for row in client.get("/api/applications").get_json()
    }
    assert applications["email_apply"]["status"] == JobStatus.APPLY_SUBMITTED.value
    assert applications["form_apply"]["status"] == JobStatus.APPLY_SUBMITTED.value
    assert applications["email_apply"]["to"] == "careers@acme.example"

    received = client.post(
        "/api/applications/email_apply/transition",
        json={"state": "received", "note": "auto-reply arrived"},
    )
    rejected = client.post(
        "/api/applications/form_apply/transition",
        json={"state": "rejected", "note": "rejection email"},
    )
    assert received.status_code == 200
    assert rejected.status_code == 200

    applications = {
        row["job_id"]: row for row in client.get("/api/applications").get_json()
    }
    assert applications["email_apply"]["response_type"] == "acknowledged"
    assert applications["email_apply"]["proof_level"] == 2
    assert applications["form_apply"]["response_type"] == "rejected"
    assert applications["form_apply"]["proof_level"] == 5
