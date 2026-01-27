\# REA Capital – Prompt Schema (v3.4)



This document defines the canonical, stable schema for prompt-only signal outputs.

No execution is performed. Prompts are data artifacts for review or downstream decisioning.



\## File Formats



\### 1) JSONL batch export

\- File: `prompts.jsonl`

\- Format: one JSON object per line

\- Producer: `batch\_exports\_prompts.py`



\### 2) Single prompt export

\- File: `last\_prompt.json`

\- Format: JSON

\- Producer: `engine\_loop.py` (when `export\_last\_prompt\_json=True`)



\## Canonical Prompt Object (Normalized)



The normalized prompt is produced by `utils/prompt\_export.py: normalize\_prompt(prompt)`.



\### Fields

\- `signal` (string)

&nbsp; - Signal identifier.

&nbsp; - Current value: `VWAP\_MEAN\_REVERSION`



\- `symbol` (string)

&nbsp; - Instrument symbol.

&nbsp; - Example: `SPY`



\- `price` (number)

&nbsp; - Last observed price at time of prompt evaluation.



\- `vwap` (number)

&nbsp; - VWAP computed over the rolling window.



\- `vwap\_context` (string)

&nbsp; - Relationship of price to VWAP.

&nbsp; - Expected values:

&nbsp;   - `ABOVE\_VWAP`

&nbsp;   - `BELOW\_VWAP`

&nbsp;   - `AT\_VWAP`



\- `vwap\_distance\_bucket` (string)

&nbsp; - Coarse bucketization of distance from VWAP.

&nbsp; - Expected values (current):

&nbsp;   - `NEAR\_VWAP`

&nbsp;   - (future may add: `MID\_VWAP`, `FAR\_VWAP`)



\- `window` (integer)

&nbsp; - VWAP rolling window length in bars.

&nbsp; - Example: `5`



\- `as\_of\_utc` (string)

&nbsp; - UTC timestamp (ISO 8601).

&nbsp; - Example: `2026-01-27T02:49:29.496127+00:00`



\## Invariants (Must Hold)



\- Prompt-only: no broker connectivity, no order routing, no execution.

\- Normalized object must always be JSON-serializable.

\- Missing fields should be `null` (JSON) rather than omitted, where practical.

\- The schema is append-only: new fields may be added, but existing fields must not change meaning.



\## Example (JSON)



{

&nbsp; "signal": "VWAP\_MEAN\_REVERSION",

&nbsp; "symbol": "SPY",

&nbsp; "price": 100.0,

&nbsp; "vwap": 100.0,

&nbsp; "vwap\_context": "AT\_VWAP",

&nbsp; "vwap\_distance\_bucket": "NEAR\_VWAP",

&nbsp; "window": 5,

&nbsp; "as\_of\_utc": "2026-01-27T02:49:29.496127+00:00"

}

