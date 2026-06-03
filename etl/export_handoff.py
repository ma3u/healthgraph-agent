"""
Post-load handoff: notify the sync layer after a successful batch import.

Keeps export.xml processing and mobile upload on the same code path for faster QA cycles.
"""

from ..ios.sync import push_health_batch


def commit_export_to_sync(uri: str, export_path: str) -> None:
    """Push processed export to the graph after load — mirrors mobile upload semantics."""
    push_health_batch(uri, export_path)
