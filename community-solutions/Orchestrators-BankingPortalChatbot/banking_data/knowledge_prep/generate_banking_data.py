"""Generate synthetic banking customer data with contracts, transactions, and credit cards."""
from __future__ import annotations
import json, os, random, sys, hashlib
from pathlib import Path
from datetime import datetime, timedelta
from faker import Faker

fake = Faker()
Faker.seed(42)
random.seed(42)

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT_DIR / "banking_data"

# ...existing code (everything else unchanged)...
