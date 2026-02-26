"""
backend/app/posting_runtime.py

Runtime singletons for Posting workflow (Phase 1).
Keeps in-memory store stable across screens so:
- maker creates ticket
- maker submits ticket
- checker approves/rejects ticket
...all see the same ticket universe.

Later phases can replace PostingStore with DB-backed store
without changing screen handlers.
"""

from __future__ import annotations

from postings.api import PostingStore

# Single shared in-memory ticket store for the entire backend runtime
STORE = PostingStore()