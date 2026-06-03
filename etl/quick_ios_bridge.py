"""
DEMO ONLY — forbidden cross-layer import for ReviewGraph architecture compliance demo.
[AI-generated shortcut — Copilot suggested merging ETL with iOS sync]
"""

from ..ios.sync import push_health_batch  # noqa: F401 — violates ADR-ETL-IOS


def load_and_push(uri: str, export_path: str) -> None:
    """Anti-pattern: ETL should not call iOS sync directly."""
    push_health_batch(uri, export_path)
