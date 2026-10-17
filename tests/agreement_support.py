"""Test helper: an operator who pages through the whole agreement and accepts once at the end."""
from __future__ import annotations


def accept_agreement(review) -> None:
    while not review.at_final_screen:
        review.page()
        review.next()
    review.accept(acknowledged=True, policy_hash_shown=review.summary()["policy_hash"])


class TestOnlyProtectBackend:
    """SYNTHETIC, TEST-ONLY stand-in for Windows DPAPI (Linux CI has no DPAPI). It is reversible
    on purpose and binds the blob to the entropy (account + machine + key id) the same way DPAPI
    does, so account-binding failures can be tested. Never used by production code."""

    MAGIC = b"TEST-ONLY-NOT-DPAPI|"

    def protect(self, data: bytes, entropy: bytes) -> bytes:
        import hashlib
        return self.MAGIC + hashlib.sha256(entropy).digest() + data

    def unprotect(self, blob: bytes, entropy: bytes) -> bytes:
        import hashlib
        if not blob.startswith(self.MAGIC) or blob[len(self.MAGIC):len(self.MAGIC) + 32] != hashlib.sha256(entropy).digest():
            raise ValueError("entropy mismatch (wrong account)")
        return blob[len(self.MAGIC) + 32:]


def test_key_store(directory, **kw):
    from backend.trading_profiles.consent_signing import ConsentKeyStore
    return ConsentKeyStore(directory, backend=TestOnlyProtectBackend(), **kw)


test_key_store.__test__ = False  # helper, not a test
TestOnlyProtectBackend.__test__ = False
