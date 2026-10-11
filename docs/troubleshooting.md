# Troubleshooting

## `external submit already attempted`

The same operation key already crossed the submit boundary. Inspect the ledger and reconcile the external system instead of deleting the record or retrying blindly.

## `SNAPSHOT_STALE`

Input changed after preview. Build a new preview and obtain a new immutable plan.

## `TARGET_MISMATCH`

The target identity or schema fingerprint changed. Revalidate the target and create a new plan.

## `READBACK_MISMATCH`

The target state does not match the planned values. Keep the job in `NEEDS_ATTENTION`; do not retry the write automatically.
