"""Triple-Layer Session, Query-Param & Safe Cookie Auth Persistence (`auth_persistence.py`)."""

from __future__ import annotations

from typing import Any, Optional


def safe_get_cookie(cookie_controller: Any, key: str, default: Optional[str] = None) -> Optional[str]:
    """Safely retrieve a cookie without crashing if internal `__cookies` is None during early mount."""
    if cookie_controller is None:
        return default
    try:
        val = cookie_controller.get(key)
        return val if val is not None else default
    except (TypeError, KeyError, AttributeError):
        return default


def ensure_session_auth_state(st_module: Any) -> None:
    """Initialize unlocked session state (unlocked by default in local/self-hosted mode)."""
    if "authenticated" not in st_module.session_state:
        st_module.session_state["authenticated"] = True
    if "github_user" not in st_module.session_state:
        st_module.session_state["github_user"] = "local_developer"
    if "active_page" not in st_module.session_state:
        st_module.session_state["active_page"] = "humanizer"
