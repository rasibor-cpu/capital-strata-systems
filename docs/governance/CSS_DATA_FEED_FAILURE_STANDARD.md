# CSS Data Feed Failure Standard

## Stale Market Data Detection
* **Mechanism:** Market data timestamps are actively compared against the current system UTC clock.
* **Threshold:** Data feeds older than 5 seconds (for highly liquid assets) or the specified threshold for the asset class are marked as STALE.

## Feed Outage Handling
* Upon detecting a stale feed or total loss of data connection from the primary provider, the intelligence engine immediately signals a data degradation event.
* The system prevents new entry orders on any asset lacking current, valid market data.

## Fail-Closed Behavior
* If the primary pricing mechanism fails and no immediate valid fallback exists, the system fails closed.
* Open positions will be monitored using degraded or fallback feeds if safely possible, but no new exposure will be taken.
* Limit orders requiring precise price triggers will be suspended until data integrity is restored.

## Operator Notifications
* Any feed outage or stale data event triggers an immediate alert to the operations dashboard.
* If the outage persists for more than 60 seconds, it is automatically escalated as a SEV2 incident.
