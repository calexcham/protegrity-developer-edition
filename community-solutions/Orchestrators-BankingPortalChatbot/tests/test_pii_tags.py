"""Unit tests for PII tag handling in protected data files."""
import re, json
from pathlib import Path

TAG_PATTERN = re.compile(r'\[([A-Z_]+)\](.*?)\[/\1\]')
DATA_DIR = Path(__file__).resolve().parent.parent / "banking_data"


class TestPiiTagFormat:
    def test_customers_protected_has_tagged_names(self):
        f = DATA_DIR / "customers_protected.json"
        if not f.exists():
            return
        for c in json.loads(f.read_text()):
            assert "[PERSON]" in c["name"], f"{c['customer_id']} name not tagged"

    def test_account_numbers_plain(self):
        """Account numbers are kept as plain text identifiers (not tokenized)."""
        f = DATA_DIR / "customers_protected.json"
        if not f.exists():
            return
        for c in json.loads(f.read_text()):
            for a in c.get("accounts", []):
                an = a.get("account_number", "")
                assert an.isdigit(), f"{c['customer_id']} {a.get('account_id')} should be plain digits"

    def test_card_numbers_tagged(self):
        f = DATA_DIR / "customers_protected.json"
        if not f.exists():
            return
        for c in json.loads(f.read_text()):
            for cc in c.get("credit_cards", []):
                cn = cc.get("card_number", "")
                assert "[CREDIT_CARD]" in cn, f"{c['customer_id']} {cc.get('card_id')} not tagged"

    def test_credentials_has_no_name_field(self):
        f = DATA_DIR / "credentials.json"
        if not f.exists():
            return
        for cred in json.loads(f.read_text()):
            assert "name" not in cred, f"credentials.json has 'name' for {cred['customer_id']}"

    def test_knowledge_base_contains_tags(self):
        kb = DATA_DIR / "knowledge_base"
        if not kb.exists():
            return
        for f in kb.glob("*.txt"):
            content = f.read_text()
            matches = TAG_PATTERN.findall(content)
            assert len(matches) > 0, f"{f.name} has no PII tags"

    def test_non_pii_fields_not_tagged(self):
        f = DATA_DIR / "customers_protected.json"
        if not f.exists():
            return
        c = json.loads(f.read_text())[0]
        for a in c.get("accounts", []):
            assert isinstance(a["balance"], (int, float))
            assert "[" not in str(a["status"])
