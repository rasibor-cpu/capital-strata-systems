from governance.posting_governance_engine import PostingGovernanceEngine
from governance.exceptions import PostingValidationError


engine = PostingGovernanceEngine()


def run_test(name, payload):
    print(f"\nRunning Test: {name}")
    try:
        result = engine.validate_and_authorize_posting(payload)
        print("STATUS:", result["status"])
    except PostingValidationError as e:
        print("FAILED:", str(e))


# -------------------------------------------------
# TEST 1 — VALID CUSTOMER TRANSACTION (PTC=1)
# -------------------------------------------------

valid_customer_txn = {
    "branch_bic": "CSSXNGAB001",
    "posting_type_code": 1,
    "customer_id": "CUST001",
    "lines": [
        {
            "gl_code": "100000001",  # internal cash
            "dc": "D",
            "amount": 1000
        },
        {
            "gl_code": "201000001",  # customer control (lane=1)
            "dc": "C",
            "amount": 1000
        }
    ]
}

run_test("Valid Customer Transaction", valid_customer_txn)


# -------------------------------------------------
# TEST 2 — INVALID (Customer account without customer_id)
# -------------------------------------------------

invalid_customer_txn = {
    "branch_bic": "CSSXNGAB001",
    "posting_type_code": 1,
    "lines": [
        {
            "gl_code": "201000001",
            "dc": "D",
            "amount": 500
        },
        {
            "gl_code": "100000001",
            "dc": "C",
            "amount": 500
        }
    ]
}

run_test("Customer Without ID", invalid_customer_txn)


# -------------------------------------------------
# TEST 3 — INVALID (Unbalanced)
# -------------------------------------------------

invalid_unbalanced = {
    "branch_bic": "CSSXNGAB001",
    "posting_type_code": 2,
    "lines": [
        {
            "gl_code": "600000001",
            "dc": "D",
            "amount": 1000
        },
        {
            "gl_code": "600000002",
            "dc": "C",
            "amount": 900
        }
    ]
}

run_test("Unbalanced Journal", invalid_unbalanced)


# -------------------------------------------------
# TEST 4 — INVALID BIC
# -------------------------------------------------

invalid_bic = {
    "branch_bic": "BADBIC001",
    "posting_type_code": 2,
    "lines": [
        {
            "gl_code": "600000001",
            "dc": "D",
            "amount": 1000
        },
        {
            "gl_code": "600000002",
            "dc": "C",
            "amount": 1000
        }
    ]
}

run_test("Invalid BIC", invalid_bic)