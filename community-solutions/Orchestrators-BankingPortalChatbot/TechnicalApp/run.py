#!/usr/bin/env python3
"""TechnicalApp — standalone launcher."""
import os, sys
from pathlib import Path
from jinja2 import FileSystemLoader

_PARENT = str(Path(__file__).resolve().parent.parent)
_LOCAL = str(Path(__file__).resolve().parent)
os.chdir(_PARENT)
sys.path.insert(0, _LOCAL)
sys.path.insert(1, _PARENT)

try:
    from dotenv import load_dotenv
    load_dotenv(Path(_PARENT) / ".env", override=True)
except ImportError:
    pass

import app as app_module
app_module.CHAT_HISTORY_DIR = Path(__file__).resolve().parent / "chat_history_tech"
app_module.CHAT_HISTORY_DIR.mkdir(exist_ok=True)

# Fix template/static paths to point to TechnicalApp/
app_module.app.template_folder = os.path.join(_LOCAL, "templates")
app_module.app.static_folder = os.path.join(_LOCAL, "static")
app_module.app.jinja_loader = FileSystemLoader(os.path.join(_LOCAL, "templates"))

if __name__ == "__main__":
    port = int(os.environ.get("TECH_PORT", 5002))
    print(f"[TechnicalApp] Technical Portal on port {port}")
    app_module.app.run(host="0.0.0.0", port=port, debug=False)
