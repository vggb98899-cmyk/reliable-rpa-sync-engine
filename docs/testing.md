# Testing strategy

The suite focuses on negative paths that commonly break automation systems:

- duplicate and empty primary keys
- stale snapshots and target identity drift
- blast-radius limits
- transient read recovery without a second export
- unknown write results without automatic replay
- persisted operation intent across engine instances
- NOOP completion without fake writes
- lease ownership and competing workers
- API health contract

Production project test counts are described as prior experience only. The public repository reports only tests executed against this codebase.
