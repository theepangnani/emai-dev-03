"""Simple async load test for local endpoints.

Usage:
  python -m scripts.load_test --base-url http://localhost:8000 --users 10 --requests 50
"""
import argparse
import asyncio
import time

import httpx


async def login(client: httpx.AsyncClient, base_url: str, email: str, password: str) -> str:
    data = {"username": email, "password": password}
    resp = await client.post(f"{base_url}/api/auth/login", data=data)
    resp.raise_for_status()
    return resp.json()["access_token"]


async def worker(
    base_url: str,
    token: str,
    requests_per_user: int,
    results: list[float],
):
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(timeout=10.0) as client:
        for _ in range(requests_per_user):
            start = time.perf_counter()
            resp = await client.get(f"{base_url}/api/notifications", headers=headers)
            resp.raise_for_status()
            results.append((time.perf_counter() - start) * 1000)


async def run_load_test(base_url: str, users: int, requests_per_user: int):
    async with httpx.AsyncClient(timeout=10.0) as client:
        token = await login(client, base_url, "admin@classbridge.local", "password123!")

    results: list[float] = []
    tasks = [
        worker(base_url, token, requests_per_user, results)
        for _ in range(users)
    ]
    await asyncio.gather(*tasks)

    results.sort()
    p95 = results[int(len(results) * 0.95) - 1] if results else 0
    avg = sum(results) / len(results) if results else 0
    print(f"Requests: {len(results)} | Avg: {avg:.2f}ms | P95: {p95:.2f}ms")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--users", type=int, default=5)
    parser.add_argument("--requests", type=int, default=20)
    args = parser.parse_args()
    asyncio.run(run_load_test(args.base_url, args.users, args.requests))
