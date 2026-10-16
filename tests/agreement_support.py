"""Test helper: an operator who pages through the whole agreement and accepts once at the end."""
from __future__ import annotations


def accept_agreement(review) -> None:
    while not review.at_final_screen:
        review.page()
        review.next()
    review.accept(acknowledged=True, policy_hash_shown=review.summary()["policy_hash"])
