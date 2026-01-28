from abc import ABC, abstractmethod
from typing import List

from engine.domain.orders import OrderIntent
from engine.domain.executions import ExecutionReport


class BrokerAdapter(ABC):
    """
    Abstract execution boundary.

    Strategy submits OrderIntent.
    BrokerAdapter returns ExecutionReport(s).
    No strategy, regime, or signal logic is allowed here.
    """

    @abstractmethod
    def submit_order(self, order: OrderIntent) -> List[ExecutionReport]:
        """
        Submit an order for execution.

        Returns one or more ExecutionReport objects
        (to support partial fills).
        """
        raise NotImplementedError

    @abstractmethod
    def cancel_order(self, order_id: str) -> None:
        """
        Cancel an existing order.
        May be a no-op for paper execution.
        """
        raise NotImplementedError