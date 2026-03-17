# Trade Decision Orchestrator Integration Plan

## Purpose

This document defines how the newly introduced **TradeDecisionOrchestrator**
module will integrate with the existing CSS signal classification system.

The objective is to centralize trade decision logic while preserving the
existing signal grading architecture.

---

## Architectural Principle

The TradeDecisionOrchestrator should **aggregate intelligence inputs**
but should **not replace the existing signal classifier**.

Signal classification remains the responsibility of the existing layer
that assigns signal classes:

- ELITE
- STRONG
- WEAK
- NOISE

---

## Intended System Flow

Market Data  
→ Feature Builder  
→ Intelligence Engines  
→ TradeDecisionOrchestrator  
→ Existing Signal Classification Layer  
→ Position Manager / Risk Layer  
→ Execution Layer  

---

## Orchestrator Responsibilities

The TradeDecisionOrchestrator should:

• Aggregate outputs from intelligence engines  
• Evaluate market regime  
• Detect liquidity sweeps  
• Assess opportunity pressure  
• Combine signal confluence factors  
• Produce a normalized decision object

Example output structure:

{
    "confidence": 0.71,
    "direction": "LONG",
    "regime": "MEAN_REVERSION",
    "reason": "VWAP elasticity + liquidity sweep + confluence"
}

---

## Classification Responsibility

The existing **Signal Classification Layer** will take the orchestrator
decision output and convert it into the official CSS signal class.

Example:

confidence = 0.71  
→ ELITE signal

confidence = 0.54  
→ STRONG signal

confidence = 0.41  
→ WEAK signal

confidence < 0.40  
→ NOISE

---

## Integration Goal

This separation ensures that:

• Intelligence aggregation remains centralized  
• Signal classification remains modular  
• Risk logic remains independent  
• CSS architecture remains scalable

---

## Next Development Step

Refactor the TradeDecisionOrchestrator output interface so that it feeds
directly into the existing classification layer without duplicating logic.
