-- Preserve every existing amount and period key without rewriting rows.
-- The neutral name supports both legacy crystallization and final selected fees.
ALTER TABLE commercial_settlement_readiness
RENAME COLUMN crystallizable_amount TO economic_amount;

ALTER TABLE commercial_settlement_readiness
ADD COLUMN final_fee_selection_id TEXT
REFERENCES commercial_final_fee_selections(fee_selection_id) ON DELETE RESTRICT;

CREATE UNIQUE INDEX idx_settlement_readiness_final_selection
ON commercial_settlement_readiness(final_fee_selection_id)
WHERE final_fee_selection_id IS NOT NULL;
