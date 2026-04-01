"""
Protect customer PII fields using appython Protector SDK.

Reads:  banking_data/customers.json
Writes: banking_data/customers_protected.json

Usage:
    python banking_data/knowledge_prep/protect_customer_data.py
    python banking_data/knowledge_prep/protect_customer_data.py --test
"""
from __future__ import annotations
import json, copy, re, sys, argparse
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT_DIR / ".env", override=True)
except ImportError:
    pass

from config.protegrity_config import (
    FIELD_PROTECTION_MAP,
    CREDIT_CARD_TAG, CREDIT_CARD_DE,
    get_data_element,
)

DATA_DIR = ROOT_DIR / "banking_data"
CUSTOMERS_FILE = DATA_DIR / "customers.json"
PROTECTED_FILE = DATA_DIR / "customers_protected.json"


def _wrap(tag: str, value: str) -> str:
    return f"[{tag}]{value}[/{tag}]"


def protect_address(session, address: str) -> str:
    m = re.match(
        r'^(\d+)\s+(.+?),\s*(.+?),\s*([A-Z]{2})\s+(\d{5}(?:-\d{4})?)$',
        address.strip()
    )
    if not m:
        protected = session.protect(address, get_data_element("LOCATION"))
        return _wrap("LOCATION", protected)

    street_num, street_name, city, state, zipcode = m.groups()
    p_street_num = session.protect(street_num, get_data_element("LOCATION"))
    p_street_name = session.protect(street_name, get_data_element("LOCATION"))
    p_city = session.protect(city, get_data_element("LOCATION"))
    p_state = session.protect(state, get_data_element("LOCATION"))
    p_zip = session.protect(zipcode, get_data_element("LOCATION"))

    return (
        f"{_wrap('LOCATION', p_street_num)} "
        f"{_wrap('LOCATION', p_street_name)}, "
        f"{_wrap('LOCATION', p_city)}, "
        f"{_wrap('LOCATION', p_state)} "
        f"{_wrap('LOCATION', p_zip)}"
    )


def protect_customer(session, customer: dict, dry_run: bool = False) -> dict:
    c = copy.deepcopy(customer)
    cid = c["customer_id"]

    for field, (tag, de) in FIELD_PROTECTION_MAP.items():
        if field in c and c[field]:
            raw = str(c[field])
            if dry_run:
                c[field] = _wrap(tag, f"<{de}:{raw[:20]}>")
            else:
                try:
                    protected = session.protect(raw, de)
                    c[field] = _wrap(tag, protected)
                except Exception as e:
                    print(f"    ⚠ {cid}.{field} ({de}): {e}")

    if "address" in c and c["address"]:
        if dry_run:
            c["address"] = f"[LOCATION]<addr:{c['address'][:30]}>[/LOCATION]"
        else:
            try:
                c["address"] = protect_address(session, c["address"])
            except Exception as e:
                print(f"    ⚠ {cid}.address: {e}")

    # Account numbers are kept as plain text (used as identifiers, not PII)
    # Only card_number, name, email, phone, SSN, DOB, address are tokenized

    for card in c.get("credit_cards", []):
        raw_num = str(card.get("card_number", ""))
        if raw_num and raw_num.isdigit():
            if dry_run:
                card["card_number"] = _wrap(CREDIT_CARD_TAG, f"<{CREDIT_CARD_DE}:{raw_num}>")
            else:
                try:
                    protected = session.protect(raw_num, CREDIT_CARD_DE)
                    card["card_number"] = _wrap(CREDIT_CARD_TAG, protected)
                except Exception as e:
                    print(f"    ⚠ {cid}.card_number: {e}")

    return c


def main():
    parser = argparse.ArgumentParser(description="Protect customer PII data")
    parser.add_argument("--user", default="superuser")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--test", action="store_true")
    args = parser.parse_args()

    if args.test:
        print(f"Testing protect capability as user '{args.user}'...")
        from appython import Protector
        p = Protector()
        s = p.create_session(args.user)
        test_cases = [
            ("string", "John Smith"), ("email", "test@example.com"),
            ("phone", "555-123-4567"), ("ssn", "123-45-6789"),
            ("ccn", "4111111111111111"), ("address", "12345"),
            ("datetime", "1990-01-01"),
        ]
        for de, val in test_cases:
            try:
                result = s.protect(val, de)
                print(f"  ✅ {de:12s} → {result}")
            except Exception as e:
                print(f"  ❌ {de:12s} → {e}")
        return

    if not CUSTOMERS_FILE.exists():
        print(f"ERROR: {CUSTOMERS_FILE} not found")
        sys.exit(1)

    with open(CUSTOMERS_FILE) as f:
        customers = json.load(f)
    if args.limit:
        customers = customers[:args.limit]

    print(f"{'[DRY RUN] ' if args.dry_run else ''}Protecting {len(customers)} customers...")

    protector = None
    if not args.dry_run:
        from appython import Protector
        protector = Protector()

    protected = []
    for cust in customers:
        cid = cust["customer_id"]
        name_val = str(cust.get("name", ""))
        if name_val.startswith("[PERSON]"):
            print(f"  ⏭ {cid} — already protected")
            protected.append(copy.deepcopy(cust))
            continue
        try:
            session = protector.create_session(args.user) if not args.dry_run else None
            p = protect_customer(session, cust, dry_run=args.dry_run)
            protected.append(p)
            print(f"  ✅ {cid}")
        except Exception as e:
            print(f"  ❌ {cid}: {e}")
            protected.append(copy.deepcopy(cust))

    with open(PROTECTED_FILE, "w") as f:
        json.dump(protected, f, indent=2, default=str)

    print(f"\nWritten to {PROTECTED_FILE}")
    print(f"Next: python banking_data/knowledge_prep/generate_knowledge_base.py")


if __name__ == "__main__":
    main()
