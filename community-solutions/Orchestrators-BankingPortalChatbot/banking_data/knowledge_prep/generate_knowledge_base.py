"""
Regenerate knowledge base .txt files from customers_protected.json.
"""
from __future__ import annotations
import json, re, sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

DATA_DIR = ROOT_DIR / "banking_data"
KB_DIR = DATA_DIR / "knowledge_base"
CUSTOMERS_FILE = DATA_DIR / "customers_protected.json"

KB_DIR.mkdir(exist_ok=True)


def _fix_double_tags(text: str) -> str:
    prev = ""
    while prev != text:
        prev = text
        text = re.sub(r'\[([A-Z_]+)\]\[(\1)\](.*?)\[/\2\]\[/\1\]', r'[\1]\3[/\1]', text)
    return text


def _mask_account_number(acct_num: str) -> str:
    # Tokenized values pass through as-is
    if re.match(r'\[[A-Z_]+\].*\[/[A-Z_]+\]', acct_num):
        return acct_num
    # Plain account numbers are kept unmasked for LLM lookup
    return acct_num


def generate_kb_file(customer: dict) -> str:
    cid = customer["customer_id"]
    lines = []

    lines.append(f"Customer Profile: {cid}")
    lines.append(f"Name: {customer.get('name', 'N/A')}")
    lines.append(f"Email: {customer.get('email', 'N/A')}")
    lines.append(f"Phone: {customer.get('phone', 'N/A')}")
    lines.append(f"DOB: {customer.get('dob', customer.get('date_of_birth', 'N/A'))}")
    lines.append(f"SSN: {customer.get('ssn', 'N/A')}")
    lines.append(f"Address: {customer.get('address', 'N/A')}")

    accounts = customer.get("accounts", [])
    if accounts:
        lines.append("")
        lines.append("=== Bank Accounts ===")
        for a in accounts:
            acct_display = _mask_account_number(str(a.get("account_number", "")))
            lines.append(
                f"  {a.get('account_id', 'N/A')} | {a.get('type', 'N/A')} | "
                f"Acct#: {acct_display} | "
                f"Balance: ${a.get('balance', 0):,.2f} | "
                f"Opened: {a.get('opened_date', 'N/A')} | "
                f"Status: {a.get('status', 'N/A')}"
            )

    cards = customer.get("credit_cards", [])
    if cards:
        lines.append("")
        lines.append("=== Credit Cards ===")
        for c in cards:
            card_num = str(c.get("card_number", ""))
            lines.append(
                f"  {c.get('card_id', 'N/A')} | {c.get('card_type', '')} {c.get('card_tier', '')} | "
                f"Card#: {card_num} | "
                f"Exp: {c.get('expiration', 'N/A')} | "
                f"Limit: ${c.get('credit_limit', 0):,} | "
                f"Balance: ${c.get('current_balance', 0):,.2f} | "
                f"Available: ${c.get('available_credit', 0):,.2f} | "
                f"Points: {c.get('reward_points', 0):,} | "
                f"Status: {c.get('status', 'N/A')}"
            )

    contracts = customer.get("contracts", [])
    if contracts:
        lines.append("")
        lines.append("=== Loans & Contracts ===")
        for lo in contracts:
            loan_type = lo.get("type", "loan").replace("_", " ").title()
            lines.append(
                f"  {lo.get('contract_id', 'N/A')} | {loan_type} | "
                f"Principal: ${lo.get('principal', 0):,.2f} | "
                f"Rate: {lo.get('interest_rate', 0)}% | "
                f"Term: {lo.get('term_months', 0)} months | "
                f"Payment: ${lo.get('monthly_payment', 0):,.2f}/mo | "
                f"Remaining: ${lo.get('remaining_balance', 0):,.2f} | "
                f"Status: {lo.get('status', 'N/A')}"
            )

    transactions = customer.get("transactions", [])
    if transactions:
        lines.append("")
        lines.append("=== Recent Transactions ===")
        sorted_txns = sorted(transactions, key=lambda t: t.get("date", ""), reverse=True)
        for tx in sorted_txns[:15]:
            sign = "+" if tx.get("type") == "credit" else "-"
            lines.append(
                f"  {str(tx.get('date', ''))[:10]} | {tx.get('merchant', 'N/A')} | "
                f"{sign}${tx.get('amount', 0):,.2f} | "
                f"{tx.get('category', 'N/A')} | {tx.get('status', 'N/A')}"
            )

    result = "\n".join(lines)
    return _fix_double_tags(result)


def main():
    if not CUSTOMERS_FILE.exists():
        print(f"ERROR: {CUSTOMERS_FILE} not found")
        return

    with open(CUSTOMERS_FILE) as f:
        customers = json.load(f)

    print(f"Regenerating KB files for {len(customers)} customers...")

    for cust in customers:
        cid = cust["customer_id"]
        content = generate_kb_file(cust)
        filepath = KB_DIR / f"{cid}.txt"
        filepath.write_text(content)
        has_loans = "=== Loans" in content
        print(f"  ✅ {cid}.txt ({len(content)} chars)"
              f"{' [has loans]' if has_loans else ''}")

    print(f"\nDone! Files written to {KB_DIR}")


if __name__ == "__main__":
    main()
