from __future__ import annotations

from backend.execution.execution_controller import ExecutionController


def main() -> None:
    controller = ExecutionController()

    result_1 = controller.execute(
        user_id="00000",
        role="ADMIN",
        action="post_transaction",
        payload={
            "amount": 50000,
            "currency": "USD",
            "reference": "TEST-POST-001",
        },
    )

    print("=== TEST 1: NORMAL EXECUTION ===")
    print(f"allowed  : {result_1.allowed}")
    print(f"executed : {result_1.executed}")
    print(f"reason   : {result_1.reason}")
    print()

    result_2 = controller.execute(
        user_id="10001",
        role="TELLER",
        action="post_transaction",
        payload={
            "amount": 25000000,
            "currency": "USD",
            "reference": "TEST-POST-002",
        },
    )

    print("=== TEST 2: HIGH-VALUE / APPROVAL OR BLOCK SCENARIO ===")
    print(f"allowed  : {result_2.allowed}")
    print(f"executed : {result_2.executed}")
    print(f"reason   : {result_2.reason}")
    print()


if __name__ == "__main__":
    main()