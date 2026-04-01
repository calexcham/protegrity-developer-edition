"""Unit tests for services/banking_service.py."""
import json, hashlib
import pytest
from unittest.mock import patch, MagicMock
import services.banking_service as bs


class TestStripPiiTags:
    def test_strips_person_tag(self):
        assert bs._strip_pii_tags("[PERSON]John Smith[/PERSON]") == "John Smith"

    def test_strips_multiple_tags(self):
        text = "[PERSON]Alice[/PERSON] at [EMAIL_ADDRESS]a@b.com[/EMAIL_ADDRESS]"
        assert bs._strip_pii_tags(text) == "Alice at a@b.com"

    def test_no_tags_unchanged(self):
        assert bs._strip_pii_tags("hello world") == "hello world"


class TestUnprotect:
    def test_fallback_strips_tags_when_no_guard(self):
        with patch.object(bs, '_get_guard', return_value=None):
            result = bs._unprotect("[PERSON]Token123[/PERSON]")
            assert result == "Token123"

    def test_uses_guard_when_available(self):
        mock_guard = MagicMock()
        mock_result = MagicMock()
        mock_result.transformed_text = "Real Name"
        mock_guard.find_and_unprotect.return_value = mock_result
        with patch.object(bs, '_get_guard', return_value=mock_guard):
            assert bs._unprotect("[PERSON]Token123[/PERSON]") == "Real Name"

    def test_falls_back_on_guard_exception(self):
        mock_guard = MagicMock()
        mock_guard.find_and_unprotect.side_effect = RuntimeError("fail")
        with patch.object(bs, '_get_guard', return_value=mock_guard):
            assert bs._unprotect("[PERSON]Token123[/PERSON]") == "Token123"


class TestAuthenticate:
    def test_valid_login_unprotects_name(self):
        pw_hash = hashlib.sha256(b"pass100").hexdigest()
        svc = bs.BankingService.__new__(bs.BankingService)
        svc.credentials = [{"username": "user1", "password_hash": pw_hash, "customer_id": "C1"}]
        svc.customers = {"C1": {"name": "[PERSON]TokenName[/PERSON]"}}
        with patch.object(bs, '_unprotect', return_value="Alice Smith"):
            result = svc.authenticate("user1", "pass100")
            assert result["name"] == "Alice Smith"

    def test_invalid_login(self):
        svc = bs.BankingService.__new__(bs.BankingService)
        svc.credentials = [{"username": "user1", "password_hash": "wrong", "customer_id": "C1"}]
        svc.customers = {}
        assert svc.authenticate("user1", "badpass") is None

    def test_missing_customer_uses_fallback(self):
        pw_hash = hashlib.sha256(b"pass").hexdigest()
        svc = bs.BankingService.__new__(bs.BankingService)
        svc.credentials = [{"username": "u", "password_hash": pw_hash, "customer_id": "MISSING"}]
        svc.customers = {}
        assert svc.authenticate("u", "pass")["name"] == "Customer"


class TestGetAccountSummary:
    def _make_service(self):
        svc = bs.BankingService.__new__(bs.BankingService)
        svc.customers = {
            "C1": {
                "name": "[PERSON]TokenName[/PERSON]",
                "accounts": [{
                    "account_id": "A1",
                    "account_number": "[ACCOUNT_NUMBER]Tok12345[/ACCOUNT_NUMBER]",
                    "type": "checking", "balance": 1000.00, "currency": "USD", "status": "active",
                }],
                "credit_cards": [{
                    "card_id": "CC1",
                    "card_number": "[CREDIT_CARD]4111111111111111[/CREDIT_CARD]",
                    "card_type": "Visa", "card_tier": "Gold", "credit_limit": 5000,
                    "current_balance": 500, "available_credit": 4500, "reward_points": 1000,
                    "status": "active", "expiration": "12/28",
                }],
                "contracts": [],
                "transactions": [{
                    "date": "2026-03-01T10:00:00", "merchant": "Store", "amount": 50.0,
                    "type": "debit", "category": "grocery", "status": "completed",
                }],
            }
        }
        svc.credentials = []
        return svc

    def test_returns_none_for_unknown(self):
        assert self._make_service().get_account_summary("UNKNOWN") is None

    def test_unprotects_and_masks_account(self):
        svc = self._make_service()
        with patch.object(bs, '_unprotect', return_value="9697354961"):
            summary = svc.get_account_summary("C1")
            assert summary["accounts"][0]["account_number_masked"] == "****4961"

    def test_unprotects_card_last_four(self):
        svc = self._make_service()
        with patch.object(bs, '_unprotect', return_value="4111111111111111"):
            summary = svc.get_account_summary("C1")
            assert summary["credit_cards"][0]["last_four"] == "1111"

    def test_no_unprotect_for_plain_values(self):
        svc = self._make_service()
        svc.customers["C1"]["name"] = "Plain Name"
        svc.customers["C1"]["accounts"][0]["account_number"] = "1234567890"
        svc.customers["C1"]["credit_cards"][0]["card_number"] = "4111111111111111"
        with patch.object(bs, '_unprotect') as mock_up:
            summary = svc.get_account_summary("C1")
            mock_up.assert_not_called()
            assert summary["name"] == "Plain Name"
            assert summary["accounts"][0]["account_number_masked"] == "****7890"


class TestSingleton:
    def test_returns_same_instance(self):
        bs._service_instance = None
        s1 = bs.get_banking_service()
        s2 = bs.get_banking_service()
        assert s1 is s2
        bs._service_instance = None
