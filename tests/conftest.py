# -*- coding: utf-8 -*-
"""Test setup: fake environment (the scripts read secrets at import time) and
a path to scripts/. No test touches the network."""
import os
import sys

os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-key")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-token")
os.environ.setdefault("TELEGRAM_CHAT_ID", "0")
os.environ.setdefault("TZ_SISTEMA", "Europe/Madrid")

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
