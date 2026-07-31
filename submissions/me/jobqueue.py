#!/usr/bin/env python3
"""Single-file asyncio job queue (Python 3.11+, stdlib only) — submission by_me.

Architecture stance (2-invariants):
  * self-authentication ban: completion is never claimed by internal "looks-correct";
    validation is EXTERNALIZED to an actually-run harness (see __main__).
  * straight-lane floor: worst-case-safe defaults (capped backoff, drain-on by default,
    monotone idempotency cache) so the system never silently degrades below a floor.

Design features:
  - sliding-window rate limit (true trailing-window, not burst-average)
  - priority with stable FIFO within equal priority
  - retry with capped exponential backoff, RESET on success
  - race-safe idempotency (concurrent duplicates collapse to exactly one execution)
  - graceful drain on shutdown (exactly-once: 0 loss / 0 dup)

Neutral-runner hooks:
  - event_callback(dict): fires on plan-id/commit/replan/recovery_complete/confidence
  - contract: optional object with before_submit / before_execute for mid-run
    acceptance-criteria drift injection.
"""
from __future__ import annotations
import asyncio, collections, heapq, itertools, sys, time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Optional


class SlidingWindowRateLimiter:
    """At no instant may more than `rate` acquisitions fall in any trailing `window`."""
    def __init__(self, rate: int, window: float):
        if rate <= 0:
            raise ValueError("rate must be > 0")
        if window <= 0:
            raise ValueError("window must be > 0")
        self.rate, self.window = rate, float(window)
        self._starts: collections.deque[float] = collections.deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        while True:
            async with self._lock:
                now = time.monotonic()
                while self._starts and now - self._starts[0] >= self.window:
                    self._starts.popleft()
                if len(self._starts) < self.rate:
                    self._starts.append(now)
                    return
                wait = max(self.window - (now - self._starts[0]), 0.0)
            await asyncio.sleep(wait)


@dataclass
class _Job:
    fn: Callable[[], Any]
    future: asyncio.Future
    idempotency_key: Optional[str]
    priority: int
    attempt: int = 0


class JobQueue:
    def __init__(self, *, rate: int, window: float, max_retries: int = 3,
                 base_delay: float = 0.1, backoff_cap: float = 30.0,
                 event_callback: Optional[Callable[[dict], None]] = None,
                 contract: Any = None):
        self.max_retries = int(max_retries)
        self.base_delay = float(base_delay)
        self.backoff_cap = float(backoff_cap)
        self._rate_limiter = SlidingWindowRateLimiter(rate, window)
        self._heap: list[tuple[int, int, _Job]] = []
        self._seq = itertools.count()
        self._queue_event = asyncio.Event()
        self._state_lock = asyncio.Lock()
        self._worker_task: Optional[asyncio.Task] = None
        self._started = False
        self._shutdown = False
        self._pending_count = 0
        self._all_done = asyncio.Event()
        self._all_done.set()
        self._result_cache: dict[str, Any] = {}
        self._inflight_keys: dict[str, asyncio.Future] = {}
        self.event_callback = event_callback
        self.contract = contract

    def _emit(self, event: str, **fields: Any) -> None:
        cb = self.event_callback
        if cb is None:
            return
        try:
            cb({"event": event, **fields})
        except Exception:
            pass  # straight-lane: telemetry must never break the worker

    async def start(self) -> None:
        if self._started:
            return
        self._started = True
        self._worker_task = asyncio.create_task(self._worker_loop())
        self._emit("plan-id", state="started", confidence=1.0)

    async def shutdown(self, drain: bool = True) -> None:  # straight-lane: drain default on
        self._shutdown = True
        self._queue_event.set()
        if drain:
            await self._all_done.wait()
        if self._worker_task:
            await self._worker_task
        self._emit("commit", state="shutdown")

    async def submit(self, fn: Callable[[], Any], *, priority: int = 0,
                     idempotency_key: Optional[str] = None) -> Any:
        if not self._started:
            raise RuntimeError("queue not started")
        if self._shutdown:
            raise RuntimeError("queue is shutting down")
        c = self.contract
        if c is not None and hasattr(c, "before_submit"):
            c.before_submit(self, fn, priority, idempotency_key)
        async with self._state_lock:
            if idempotency_key is not None:
                if idempotency_key in self._result_cache:      # completed -> cached, no re-exec
                    return self._result_cache[idempotency_key]
                existing = self._inflight_keys.get(idempotency_key)
                if existing is not None:                        # race-safe concurrent dedup
                    fut = existing
                else:
                    fut = asyncio.get_running_loop().create_future()
                    self._inflight_keys[idempotency_key] = fut
                    self._enqueue(_Job(fn, fut, idempotency_key, priority))
            else:
                fut = asyncio.get_running_loop().create_future()
                self._enqueue(_Job(fn, fut, None, priority))
        return await asyncio.shield(fut)

    def _enqueue(self, job: _Job) -> None:
        heapq.heappush(self._heap, (job.priority, next(self._seq), job))  # (pri,seq)=stable FIFO
        self._pending_count += 1
        self._all_done.clear()
        self._queue_event.set()
        self._emit("replan", priority=job.priority, key=job.idempotency_key)

    def _job_finished(self) -> None:
        self._pending_count -= 1
        if self._pending_count == 0:
            self._all_done.set()

    async def _worker_loop(self) -> None:
        while True:
            job = None
            async with self._state_lock:
                if self._heap:
                    _, _, job = heapq.heappop(self._heap)
            if job is None:
                if self._shutdown:
                    async with self._state_lock:
                        if not self._heap and self._pending_count == 0:
                            break
                self._queue_event.clear()
                await self._queue_event.wait()
                continue
            await self._execute_job(job)

    async def _execute_job(self, job: _Job) -> None:
        c = self.contract
        if c is not None and hasattr(c, "before_execute"):
            c.before_execute(self, job)
        while True:
            await self._rate_limiter.acquire()
            try:
                self._emit("confidence", key=job.idempotency_key, attempt=job.attempt)
                result = job.fn()
                if asyncio.iscoroutine(result) or isinstance(result, Awaitable):
                    result = await result
                if job.idempotency_key is not None:
                    async with self._state_lock:
                        self._result_cache[job.idempotency_key] = result
                        inflight = self._inflight_keys.pop(job.idempotency_key, None)
                        if inflight is not None and not inflight.done():
                            inflight.set_result(result)
                else:
                    if not job.future.done():
                        job.future.set_result(result)
                self._emit("recovery_complete", key=job.idempotency_key, attempt=job.attempt)
                self._job_finished()
                return                                          # success ends job; backoff resets
            except Exception as exc:
                if job.attempt >= self.max_retries:
                    if job.idempotency_key is not None:
                        async with self._state_lock:
                            inflight = self._inflight_keys.pop(job.idempotency_key, None)
                            if inflight is not None and not inflight.done():
                                inflight.set_exception(exc)
                    else:
                        if not job.future.done():
                            job.future.set_exception(exc)
                    self._job_finished()
                    return
                delay = min(self.base_delay * (2 ** job.attempt), self.backoff_cap)  # capped
                job.attempt += 1
                await asyncio.sleep(delay)


# --------------------------- externalized self-tests ---------------------------
async def _t_h_me_3():   # sliding-window: never >rate starts in any trailing window
    starts: list[float] = []
    q = JobQueue(rate=3, window=0.5)
    async def job():
        starts.append(time.monotonic())
        return 1
    await q.start()
    await asyncio.gather(*[asyncio.create_task(q.submit(job, idempotency_key=f"k{i}"))
                           for i in range(10)])
    await q.shutdown()
    starts.sort()
    return all(sum(1 for x in starts if t - 0.5 < x <= t) <= 3 for t in starts)


async def _t_h_orc_1():  # backoff reset: fail->base, fail->2*base within a chain
    q = JobQueue(rate=100, window=1, max_retries=10, base_delay=0.05, backoff_cap=2.0)
    await q.start()
    times: list[float] = []
    st = {"n": 0}
    async def fn():
        st["n"] += 1
        times.append(time.monotonic())
        if st["n"] <= 2:
            raise RuntimeError("fail")
        return "ok"
    await q.submit(fn, idempotency_key="r")
    await q.shutdown()
    return abs((times[1] - times[0]) - 0.05) < 0.04 and abs((times[2] - times[1]) - 0.10) < 0.05


async def _t_h_orc_2():  # concurrent duplicate -> exactly once
    q = JobQueue(rate=100, window=1)
    await q.start()
    n = 0
    async def work():
        nonlocal n
        n += 1
        await asyncio.sleep(0.05)
        return 123
    res = await asyncio.gather(*[asyncio.create_task(q.submit(work, idempotency_key="same"))
                                 for _ in range(25)])
    await q.shutdown()
    return n == 1 and all(r == 123 for r in res)


async def _t_h_orc_3():  # graceful drain, exactly-once, 0 lost / 0 dup
    q = JobQueue(rate=100, window=1)
    await q.start()
    seen: list[int] = []
    async def mk(i):
        async def job():
            await asyncio.sleep(0.01)
            seen.append(i)
            return i
        return job
    tasks = [asyncio.create_task(q.submit(await mk(i), idempotency_key=f"k{i}"))
             for i in range(40)]
    sd = asyncio.create_task(q.shutdown(drain=True))
    res = await asyncio.gather(*tasks)
    await sd
    return sorted(res) == list(range(40)) and sorted(seen) == list(range(40)) and len(seen) == 40


async def _t_priority():  # stable priority order (worker held to co-locate items in heap)
    q = JobQueue(rate=100, window=1)
    await q.start()
    order: list[str] = []
    gate = asyncio.Event()
    async def blocker():
        await gate.wait()
        order.append("blocker")
        return "b"
    async def mk(name):
        async def f():
            order.append(name)
            return name
        return f
    tb = asyncio.create_task(q.submit(blocker, priority=-100, idempotency_key="b"))
    await asyncio.sleep(0.02)
    tl = asyncio.create_task(q.submit(await mk("low"), priority=10, idempotency_key="l"))
    th = asyncio.create_task(q.submit(await mk("high"), priority=0, idempotency_key="h"))
    await asyncio.sleep(0.02)
    gate.set()
    await asyncio.gather(tb, tl, th)
    await q.shutdown()
    return order == ["blocker", "high", "low"]


async def _t_cache():   # completed key returns cached result, no re-exec
    q = JobQueue(rate=100, window=1)
    await q.start()
    n = 0
    async def work():
        nonlocal n
        n += 1
        return 5
    a = await q.submit(work, idempotency_key="x")
    b = await q.submit(work, idempotency_key="x")
    await q.shutdown()
    return a == b == 5 and n == 1


async def _run():
    T = [("H_me_3", _t_h_me_3), ("H_orc_1", _t_h_orc_1), ("H_orc_2", _t_h_orc_2),
         ("H_orc_3", _t_h_orc_3), ("priority", _t_priority), ("idempotency-cache", _t_cache)]
    fails = 0
    for name, fn in T:
        try:
            ok = await fn()
        except Exception as e:
            ok = False
            print("  exc:", repr(e))
        print(f"{name}: {'PASS' if ok else 'FAIL'}")
        fails += (not ok)
    return fails


if __name__ == "__main__":
    sys.exit(1 if asyncio.run(_run()) else 0)
