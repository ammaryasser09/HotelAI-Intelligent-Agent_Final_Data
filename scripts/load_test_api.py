"""Load test for the API: many requests at the same time, then speed and errors.

Start the server with a high rate limit first (the default 60/minute would answer 429):
    $env:RATE_LIMIT="1000000/minute"; uvicorn app.api.main:app

Then, in another terminal:
    python scripts/load_test_api.py                       # 1,000 requests, 50 at a time
    python scripts/load_test_api.py --requests 3000 --concurrency 100
"""
import argparse
import asyncio
import statistics
import time
from collections import Counter

import httpx

ENDPOINTS = {
    "health": "/health",
    "availability": "/availability?room_type=Suite&check_in=2026-10-03&check_out=2026-10-06&guests=2",
    "room-types": "/room-types",
}


async def worker(client: httpx.AsyncClient, path: str, count: int, latencies: list, statuses: Counter):
    for _ in range(count):
        start = time.perf_counter()
        try:
            response = await client.get(path)
            statuses[str(response.status_code)] += 1
        except httpx.HTTPError as error:
            statuses[type(error).__name__] += 1
        latencies.append((time.perf_counter() - start) * 1000)


async def run(base_url: str, name: str, path: str, total: int, concurrency: int):
    latencies, statuses = [], Counter()
    share, extra = divmod(total, concurrency)
    counts = [share + (1 if i < extra else 0) for i in range(concurrency)]

    limits = httpx.Limits(max_connections=concurrency, max_keepalive_connections=concurrency)
    async with httpx.AsyncClient(base_url=base_url, timeout=30, limits=limits) as client:
        await client.get(path)  # warm up: open the database pool before timing
        start = time.perf_counter()
        await asyncio.gather(*(worker(client, path, n, latencies, statuses) for n in counts if n))
        seconds = time.perf_counter() - start

    latencies.sort()
    p95 = latencies[int(len(latencies) * 0.95) - 1]
    print(f"\n{name}  ({total} requests, {concurrency} at a time)")
    print(f"  requests per second : {total / seconds:,.0f}")
    print(f"  time per request    : median {statistics.median(latencies):.1f} ms | 95% under {p95:.1f} ms | slowest {latencies[-1]:.1f} ms")
    print(f"  answers             : {dict(statuses)}")


async def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--requests", type=int, default=1000)
    parser.add_argument("--concurrency", type=int, default=50)
    args = parser.parse_args()

    for name, path in ENDPOINTS.items():
        await run(args.base_url, name, path, args.requests, args.concurrency)


if __name__ == "__main__":
    asyncio.run(main())
