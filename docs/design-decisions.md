# Design decisions

## Retry reads, reconcile writes

Timeouts and connection failures during side-effect-free reads use bounded retry. A write timeout can mean the remote system committed the request, so the engine records `UNKNOWN` and blocks automatic replay.

## Freeze identity before execution

The plan includes snapshot and target fingerprints. A changed source snapshot or target schema invalidates the plan instead of silently redirecting data.

## Keep NOOP as a successful terminal path

When no changes are required, no write or write read-back is fabricated. The execution still ends successfully with an auditable NOOP count.

## Persist external-operation intent before submit

The ledger increments `submit_count` before calling the external adapter. A process crash after the call cannot cause the next worker to submit again.

## Separate public implementation from production claims

This repository is independently written. Production platform adapters, selectors, field catalogs, credentials, records and deployment details are intentionally excluded.
