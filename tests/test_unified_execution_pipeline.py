from __future__ import annotations

import pytest

from backend.execution.unified_execution_pipeline import (
    UnifiedExecutionPipeline,
    UnifiedExecutionPipelineError,
    UnifiedExecutionRequest,
)


@pytest.fixture
def pipeline() -> UnifiedExecutionPipeline:
    return UnifiedExecutionPipeline()


def test_fx_paper_request_accepted(pipeline: UnifiedExecutionPipeline) -> None:
    request = UnifiedExecutionRequest(
        asset_class="FX",
        symbol="eur/usd",
        side="buy",
        quantity=1,
        mode="paper",
    )

    result = pipeline.execute(request)

    assert result.status == "accepted"
    assert result.asset_class == "FX"
    assert result.symbol == "EUR/USD"
    assert result.side == "BUY"
    assert result.quantity == 1
    assert result.mode == "paper"
    assert result.trade_id


def test_crypto_paper_request_accepted(pipeline: UnifiedExecutionPipeline) -> None:
    request = UnifiedExecutionRequest(
        asset_class="CRYPTO",
        symbol="btc/usd",
        side="sell",
        quantity=2,
        mode="paper",
    )

    result = pipeline.execute(request)

    assert result.status == "accepted"
    assert result.asset_class == "CRYPTO"
    assert result.symbol == "BTC/USD"
    assert result.side == "SELL"
    assert result.quantity == 2
    assert result.mode == "paper"


def test_options_paper_request_accepted(pipeline: UnifiedExecutionPipeline) -> None:
    request = UnifiedExecutionRequest(
        asset_class="OPTIONS",
        symbol="AAPL240119C00100000",
        side="buy",
        quantity=1,
        mode="paper",
    )

    result = pipeline.execute(request)

    assert result.status == "accepted"
    assert result.asset_class == "OPTIONS"
    assert result.symbol == "AAPL240119C00100000"
    assert result.quantity == 1


def test_futures_paper_request_accepted(pipeline: UnifiedExecutionPipeline) -> None:
    request = UnifiedExecutionRequest(
        asset_class="FUTURES",
        symbol="ESM6",
        side="buy",
        quantity=1,
        mode="paper",
    )

    result = pipeline.execute(request)

    assert result.status == "accepted"
    assert result.asset_class == "FUTURES"
    assert result.symbol == "ESM6"
    assert result.quantity == 1


def test_unsupported_asset_fails_closed(pipeline: UnifiedExecutionPipeline) -> None:
    request = UnifiedExecutionRequest(
        asset_class="COMMODITY",
        symbol="GOLD",
        side="buy",
        quantity=1,
        mode="paper",
    )

    with pytest.raises(UnifiedExecutionPipelineError):
        pipeline.execute(request)


def test_missing_fields_fail_closed(pipeline: UnifiedExecutionPipeline) -> None:
    with pytest.raises(UnifiedExecutionPipelineError):
        pipeline.execute(
            UnifiedExecutionRequest(
                asset_class="FX",
                symbol="",
                side="buy",
                quantity=1,
                mode="paper",
            )
        )

    with pytest.raises(UnifiedExecutionPipelineError):
        pipeline.execute(
            UnifiedExecutionRequest(
                asset_class="FX",
                symbol="EUR/USD",
                side="",
                quantity=1,
                mode="paper",
            )
        )

    with pytest.raises(UnifiedExecutionPipelineError):
        pipeline.execute(
            UnifiedExecutionRequest(
                asset_class="FX",
                symbol="EUR/USD",
                side="buy",
                quantity=0,
                mode="paper",
            )
        )

    with pytest.raises(UnifiedExecutionPipelineError):
        pipeline.execute(
            UnifiedExecutionRequest(
                asset_class="FX",
                symbol="EUR/USD",
                side="buy",
                quantity=1,
                mode="",
            )
        )


def test_live_mode_rejected_in_foundation_phase(pipeline: UnifiedExecutionPipeline) -> None:
    request = UnifiedExecutionRequest(
        asset_class="FX",
        symbol="EUR/USD",
        side="buy",
        quantity=1,
        mode="live",
    )

    with pytest.raises(UnifiedExecutionPipelineError):
        pipeline.execute(request)


def test_normalized_result_shape(pipeline: UnifiedExecutionPipeline) -> None:
    request = UnifiedExecutionRequest(
        asset_class="fx",
        symbol="eur/usd",
        side="buy",
        quantity=1,
        mode="paper",
    )

    result = pipeline.execute(request)
    result_dict = result.to_dict()

    assert set(result_dict.keys()) == {
        "trade_id",
        "symbol",
        "asset_class",
        "side",
        "quantity",
        "mode",
        "status",
        "reason",
    }
    assert result_dict["symbol"] == "EUR/USD"
    assert result_dict["asset_class"] == "FX"
    assert result_dict["side"] == "BUY"
    assert result_dict["mode"] == "paper"
