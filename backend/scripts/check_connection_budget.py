"""Run before increasing replica counts; reserve capacity for admin/failover."""
import argparse
parser = argparse.ArgumentParser()
parser.add_argument("--api-replicas", type=int, default=1)
parser.add_argument("--api-workers", type=int, default=2)
parser.add_argument("--api-pool", type=int, default=5)
parser.add_argument("--api-overflow", type=int, default=2)
parser.add_argument("--worker-replicas", type=int, default=1)
parser.add_argument("--worker-concurrency", type=int, default=2)
parser.add_argument("--worker-pool", type=int, default=2)
parser.add_argument("--worker-overflow", type=int, default=0)
parser.add_argument("--postgres-max", type=int, default=100)
parser.add_argument("--reserve", type=int, default=20)
args = parser.parse_args()
if any(value < 0 for value in vars(args).values()):
    parser.error("Budgets must be nonnegative.")
api = args.api_replicas * args.api_workers * (args.api_pool + args.api_overflow)
workers = args.worker_replicas * args.worker_concurrency * (args.worker_pool + args.worker_overflow)
print(f"API={api}, workers={workers}, reserved={args.reserve}, PostgreSQL={args.postgres_max}")
if api + workers + args.reserve > args.postgres_max:
    raise SystemExit("FAIL: connection budget exceeds PostgreSQL capacity")
print("PASS: configured process pools fit the connection budget")
