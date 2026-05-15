"""`_is_expired_listing(url, status_code)` decides whether an apply
attempt should be aborted with `LISTING_EXPIRED` instead of launching
a browser or filling a form.

Real-world driver: 2026-05-15, two Consensys Senior PM positions had
their listings pulled between scoring and apply. The Greenhouse URL
returned HTTP 200 but redirected to `consensys.io/open-roles` (no
specific job to apply to). The runner shouldn't try to fill a form
that doesn't exist; surface an ⏱ expired pill on Stage 3 and move on.

Per user feedback:
  *"if its gone, mark with expired pill in stage 3 and move to next
   project"*
"""
from __future__ import annotations

from jobbot.applier.runner import _is_expired_listing


# ---------------------------------------------------------------------------
# HTTP-status signals
# ---------------------------------------------------------------------------

def test_http_403_means_expired():
    """The WWR Consensys URL returned 403 — listing pulled."""
    expired, reason = _is_expired_listing(
        "https://weworkremotely.com/remote-jobs/consensys-senior-product-manager-metamask-engagement",
        403,
    )
    assert expired is True
    assert "403" in reason


def test_http_404_means_expired():
    expired, reason = _is_expired_listing("https://job-boards.greenhouse.io/x/jobs/99", 404)
    assert expired is True
    assert "404" in reason


def test_http_410_means_expired():
    expired, _ = _is_expired_listing("https://example.com/jobs/old", 410)
    assert expired is True


# ---------------------------------------------------------------------------
# Redirect-to-generic-careers signals
# ---------------------------------------------------------------------------

def test_redirect_to_open_roles_means_expired():
    """The Consensys regression: Greenhouse 7551395 returned 200 but
    final URL was `consensys.io/open-roles` — no specific job."""
    expired, reason = _is_expired_listing("https://consensys.io/open-roles", 200)
    assert expired is True
    assert "open-roles" in reason or "generic" in reason.lower()


def test_redirect_to_careers_index_means_expired():
    expired, _ = _is_expired_listing("https://example.com/careers/index", 200)
    assert expired is True


def test_redirect_to_jobs_search_means_expired():
    expired, _ = _is_expired_listing("https://boards.greenhouse.io/x/jobs/search", 200)
    assert expired is True


def test_explicit_404_path_means_expired():
    expired, _ = _is_expired_listing("https://example.com/404", 200)
    assert expired is True


# ---------------------------------------------------------------------------
# Legitimate apply URLs — must NOT trip the detector
# ---------------------------------------------------------------------------

def test_greenhouse_specific_job_is_NOT_expired():
    """The whole point: a normal Greenhouse listing URL must pass through."""
    expired, _ = _is_expired_listing(
        "https://job-boards.greenhouse.io/backblaze/jobs/5210076008", 200
    )
    assert expired is False


def test_recruitee_specific_job_is_NOT_expired():
    expired, _ = _is_expired_listing(
        "https://gtowizard.recruitee.com/o/product-manager-3", 200
    )
    assert expired is False


def test_personio_specific_job_is_NOT_expired():
    expired, _ = _is_expired_listing(
        "https://xpate.jobs.personio.com/job/2633050?language=en", 200
    )
    assert expired is False


def test_join_specific_job_is_NOT_expired():
    expired, _ = _is_expired_listing(
        "https://join.com/companies/insurgo/16121331-product-manager-m-w-d-oder-remote", 200
    )
    assert expired is False


def test_company_careers_subpath_with_job_id_NOT_expired():
    """A URL that mentions 'careers' but ALSO has a numeric job id
    is a live listing, not a generic index. We require the path to
    end on a known generic segment."""
    expired, _ = _is_expired_listing(
        "https://example.com/careers/jobs/12345-product-manager", 200
    )
    # 'jobs/12345' is fine; the test is that 'careers' alone isn't enough
    # to trip the detector when a specific job id follows.
    assert expired is False
