from reliable_sync.adapters import MockSource, MockTarget
from reliable_sync.engine import SyncEngine


source = MockSource([
    {"id": "PO-001", "supplier": "Demo Supplier", "amount": 120.0},
    {"id": "PO-002", "supplier": "Example Factory", "amount": 88.0},
])
target = MockTarget("demo-orders", "DEMO", "schema-v1", {})
engine = SyncEngine(source, target)

snapshot = engine.acquire_snapshot("demo-run-001")
plan = engine.prepare(snapshot)
result = engine.execute(plan, snapshot, confirmed=True)

print(result)
