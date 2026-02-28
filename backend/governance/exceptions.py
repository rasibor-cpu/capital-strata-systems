class PostingValidationError(Exception):
    """Raised when a posting fails governance validation."""
    pass


class BranchValidationError(PostingValidationError):
    """Invalid or malformed branch BIC."""
    pass


class GLValidationError(PostingValidationError):
    """Invalid GL format or schema violation."""
    pass


class PostingTypeError(PostingValidationError):
    """Posting Type Code violation."""
    pass


class DimensionValidationError(PostingValidationError):
    """Required dimension missing."""
    pass


class BalanceValidationError(PostingValidationError):
    """Debit/Credit imbalance."""
    pass