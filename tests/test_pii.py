"""Tests for PII scrubber."""
from __future__ import annotations

from localkoreantts import pii


def test_mask_digits() -> None:
    assert pii.mask_digits("call 010-1234", token="x") == "call xxx-xxxx"


def test_mask_emails() -> None:
    assert pii.mask_emails("contact me at foo@example.com") == "***@***"


def test_scrub_combines_filters() -> None:
    scrubbed = pii.scrub("010-1234 reached foo@example.com")
    assert "*" in scrubbed and "@" in scrubbed

def test_mask_emails_no_match() -> None:
    assert pii.mask_emails("no email here") == "no email here"

def test_scrub_applies_extra_filters() -> None:
    result = pii.scrub("123", extra_filters=[lambda value: value.replace("*", "#")])
    assert result == "###"
