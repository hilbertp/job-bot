"""Mailbox selection for the alert scanner.

Board accounts are not always registered to the address the bot already
reads, so the scanner must be able to open a third, dedicated mailbox
without disturbing the Gmail digest box or the outbound business box.
"""
from __future__ import annotations

import pytest

from jobbot.alerts import mailbox as mb
from jobbot.config import Secrets


def _secrets(**kw) -> Secrets:
    base = dict(anthropic_api_key="x", gmail_address="me@gmail.com",
                gmail_app_password="gpass", notify_to="me@gmail.com",
                imap_host="imap.gmail.com", imap_port=993,
                truenorth_smtp_user="biz@true-north.berlin",
                truenorth_smtp_pass="tpass",
                truenorth_imap_host="imap.ionos.de", truenorth_imap_port=993)
    base.update(kw)
    return Secrets(**base)


class _FakeIMAP:
    opened: list[tuple] = []
    timeouts: list = []

    def __init__(self, host, port, ssl_context=None, timeout=None):
        # `timeout` mirrors the real imaplib signature. A double that
        # silently swallowed it would let a timeout-less socket ship.
        self.host, self.port = host, port
        _FakeIMAP.timeouts.append(timeout)

    def login(self, user, password):
        _FakeIMAP.opened.append((self.host, self.port, user, password))


@pytest.fixture(autouse=True)
def fake_imap(monkeypatch):
    _FakeIMAP.opened = []
    _FakeIMAP.timeouts = []
    monkeypatch.setattr(mb.imaplib, "IMAP4_SSL", _FakeIMAP)
    return _FakeIMAP


def test_gmail_is_the_default(fake_imap):
    mb.connect(_secrets())
    host, port, user, password = fake_imap.opened[0]
    assert (host, port, user) == ("imap.gmail.com", 993, "me@gmail.com")
    assert password == "gpass"


def test_truenorth_uses_the_business_box(fake_imap):
    mb.connect(_secrets(), mailbox="truenorth")
    host, _port, user, _pw = fake_imap.opened[0]
    assert (host, user) == ("imap.ionos.de", "biz@true-north.berlin")


def test_alerts_mailbox_uses_its_own_credentials(fake_imap):
    mb.connect(
        _secrets(alerts_imap_host="imap.ionos.de", alerts_imap_port=993,
                 alerts_imap_user="alerts@example.com", alerts_imap_pass="apass"),
        mailbox="alerts",
    )
    host, port, user, password = fake_imap.opened[0]
    assert (host, port, user, password) == (
        "imap.ionos.de", 993, "alerts@example.com", "apass")


def test_unconfigured_alerts_mailbox_returns_none_instead_of_connecting(fake_imap):
    """Missing credentials must skip quietly, not crash the daily run."""
    assert mb.connect(_secrets(), mailbox="alerts") is None
    assert fake_imap.opened == []


def test_alert_mailbox_socket_carries_a_timeout(fake_imap):
    """A mailbox scan runs inside the pipeline; an untimed socket there
    wedges the run exactly as the digest send did (run 451)."""
    mb.connect(_secrets())
    assert fake_imap.timeouts, "IMAP4_SSL was never constructed"
    assert all(t for t in fake_imap.timeouts), fake_imap.timeouts
