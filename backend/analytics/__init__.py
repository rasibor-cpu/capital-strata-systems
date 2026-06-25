"""Read-only analytics engines for profitability and signal edge observability."""

from .adaptive_position_sizing import AdaptivePositionSizingEngine, AdaptivePositionSizingError
from .adaptive_calibration_engine import AdaptiveCalibrationEngine, AdaptiveCalibrationEngineError
from .adaptive_threshold_calibration_engine import AdaptiveThresholdCalibrationEngine, AdaptiveThresholdCalibrationEngineError
from .autonomous_profitability_program import AutonomousProfitabilityProgram, AutonomousProfitabilityProgramError
from .autonomous_learning_controller import AutonomousLearningController, AutonomousLearningControllerError
from .dynamic_position_optimizer import DynamicPositionOptimizer, DynamicPositionOptimizerError
from .improvement_recommendation_engine import ImprovementRecommendationEngine, ImprovementRecommendationEngineError
from .closed_loop_learning_engine import ClosedLoopLearningEngine, ClosedLoopLearningEngineError
from .continuous_learning_feedback import ContinuousLearningFeedback, ContinuousLearningFeedbackError
from .capital_allocation_engine import CapitalAllocationEngine, CapitalAllocationEngineError
from .concentration_guard import ConcentrationGuard, ConcentrationGuardError
from .cost_reality_engine import CostRealityEngine
from .dynamic_acceptance_engine import DynamicAcceptanceEngine, DynamicAcceptanceEngineError
from .execution_selection_engine import ExecutionSelectionEngine, ExecutionSelectionEngineError
from .opportunity_cost_engine import OpportunityCostEngine, OpportunityCostEngineError
from .optimization_backtesting_engine import OptimizationBacktestingEngine, OptimizationBacktestingEngineError
from .optimization_summary_report import OptimizationSummaryReport, OptimizationSummaryReportError
from .optimization_validation_engine import OptimizationValidationEngine, OptimizationValidationEngineError
from .performance_attribution_engine import PerformanceAttributionEngine, PerformanceAttributionEngineError
from .performance_analytics_engine import PerformanceAnalyticsEngine, PerformanceAnalyticsEngineError
from .performance_reporting_engine import PerformanceReportingEngine, PerformanceReportingEngineError
from .opportunity_ranking_engine import OpportunityRankingEngine, OpportunityRankingEngineError
from .portfolio_correlation_engine import PortfolioCorrelationEngine, PortfolioCorrelationEngineError
from .profitability_ranking_engine import ProfitabilityRankingEngine, ProfitabilityRankingEngineError
from .profitability_optimizer import ProfitabilityOptimizer, ProfitabilityOptimizerError
from .portfolio_optimization_engine import PortfolioOptimizationEngine, PortfolioOptimizationError
from .signal_quality_engine import SignalQualityEngine
from .marathon_readiness_optimizer import MarathonReadinessOptimizer, MarathonReadinessOptimizerError
from .regime_parameter_profiles import RegimeParameterProfiles, RegimeParameterProfilesError
from .strategy_promotion_manager import StrategyPromotionManager, StrategyPromotionManagerError
from .strategy_league_table import StrategyLeagueTable, StrategyLeagueTableError
from .strategy_promotion_engine import StrategyPromotionEngine, StrategyPromotionError
from .strategy_evolution_engine import StrategyEvolutionEngine, StrategyEvolutionEngineError
from .autonomous_portfolio_manager import AutonomousPortfolioManager, AutonomousPortfolioManagerError
from .trade_explanation_repository import TradeExplanationRepository, TradeExplanationRepositoryError
from .trade_forensics_engine import TradeForensicsEngine, TradeForensicsEngineError
from .trade_quality_models import TradeQualityAssessment
from .trade_quality_scoring_engine import TradeQualityScoringEngine, TradeQualityScoringEngineError
from .trade_outcome_analytics_engine import TradeOutcomeAnalyticsEngine
from .trade_outcome_repository import (
    DuplicateTradeOutcomeError,
    TradeOutcomeRecord,
    TradeOutcomeRepository,
    TradeOutcomeRepositoryError,
    build_trade_outcome_analytics_adapter,
    persist_completed_trade_outcome,
)

__all__ = [
    "AdaptivePositionSizingEngine",
    "AdaptivePositionSizingError",
    "AdaptiveCalibrationEngine",
    "AdaptiveCalibrationEngineError",
    "AdaptiveThresholdCalibrationEngine",
    "AdaptiveThresholdCalibrationEngineError",
    "AutonomousProfitabilityProgram",
    "AutonomousProfitabilityProgramError",
    "AutonomousLearningController",
    "AutonomousLearningControllerError",
    "DynamicPositionOptimizer",
    "DynamicPositionOptimizerError",
    "ImprovementRecommendationEngine",
    "ImprovementRecommendationEngineError",
    "ClosedLoopLearningEngine",
    "ClosedLoopLearningEngineError",
    "ContinuousLearningFeedback",
    "ContinuousLearningFeedbackError",
    "CapitalAllocationEngine",
    "CapitalAllocationEngineError",
    "ConcentrationGuard",
    "ConcentrationGuardError",
    "CostRealityEngine",
    "DynamicAcceptanceEngine",
    "DynamicAcceptanceEngineError",
    "ExecutionSelectionEngine",
    "ExecutionSelectionEngineError",
    "OpportunityCostEngine",
    "OpportunityCostEngineError",
    "OptimizationBacktestingEngine",
    "OptimizationBacktestingEngineError",
    "OptimizationSummaryReport",
    "OptimizationSummaryReportError",
    "OptimizationValidationEngine",
    "OptimizationValidationEngineError",
    "PerformanceAttributionEngine",
    "PerformanceAttributionEngineError",
    "PerformanceAnalyticsEngine",
    "PerformanceAnalyticsEngineError",
    "PerformanceReportingEngine",
    "PerformanceReportingEngineError",
    "OpportunityRankingEngine",
    "OpportunityRankingEngineError",
    "ProfitabilityRankingEngine",
    "ProfitabilityRankingEngineError",
    "ProfitabilityOptimizer",
    "ProfitabilityOptimizerError",
    "SignalQualityEngine",
    "MarathonReadinessOptimizer",
    "MarathonReadinessOptimizerError",
    "RegimeParameterProfiles",
    "RegimeParameterProfilesError",
    "StrategyPromotionManager",
    "StrategyPromotionManagerError",
    "TradeQualityAssessment",
    "TradeQualityScoringEngine",
    "TradeQualityScoringEngineError",
    "TradeOutcomeAnalyticsEngine",
    "DuplicateTradeOutcomeError",
    "TradeOutcomeRecord",
    "TradeOutcomeRepository",
    "TradeOutcomeRepositoryError",
    "build_trade_outcome_analytics_adapter",
    "persist_completed_trade_outcome",
    "StrategyLeagueTable",
    "StrategyLeagueTableError",
    "AutonomousPortfolioManager",
    "AutonomousPortfolioManagerError",
    "PortfolioOptimizationEngine",
    "PortfolioOptimizationError",
    "PortfolioCorrelationEngine",
    "PortfolioCorrelationEngineError",
    "StrategyPromotionEngine",
    "StrategyPromotionError",
    "StrategyEvolutionEngine",
    "StrategyEvolutionEngineError",
    "TradeExplanationRepository",
    "TradeExplanationRepositoryError",
    "TradeForensicsEngine",
    "TradeForensicsEngineError",
]
