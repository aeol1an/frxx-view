"""Window-scoped lifecycle management for interactive tools."""
from __future__ import annotations

from typing import Any, Protocol


class InteractionSession(Protocol):
    scope: str

    def close(self, reason: str): ...


class InteractionManager:
    """Own transient interactions and data belonging to one data window."""

    def __init__(self, window):
        self.window = window
        self.mask: Any = None
        self._sessions: dict[str, InteractionSession] = {}
        window.state.scan_changed.connect(self._on_scan_changed)

    def start(self, name: str, session: InteractionSession):
        if name in self._sessions:
            self.stop(name, reason="replaced")
        self._sessions[name] = session

    def get(self, name: str) -> InteractionSession | None:
        return self._sessions.get(name)

    def is_active(self, name: str) -> bool:
        return name in self._sessions

    def stop(self, name: str, reason: str = "toggle") -> bool:
        session = self._sessions.pop(name, None)
        if session is None:
            return False
        session.close(reason)
        return True

    def stop_all(self, scope: str | None = None, reason: str = "clear"):
        for name, session in tuple(self._sessions.items()):
            if scope is None or session.scope == scope:
                self.stop(name, reason=reason)

    def _on_scan_changed(self):
        self.stop_all(scope="scan", reason="scan_changed")
        self.mask = None
