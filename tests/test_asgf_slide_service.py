"""Unit tests for ASGF slide service — bounded-concurrency generation (#3735)."""

import asyncio
import time
from unittest.mock import patch

import pytest

from app.services.asgf_slide_service import ASGFSlideService, TOTAL_SLIDES


def _slide_stub(slide_number: int) -> dict:
    return {
        "slide_number": slide_number,
        "title": f"Slide {slide_number}",
        "body": f"body-{slide_number}",
        "vocabulary_terms": [],
        "source_attribution": None,
        "read_more_content": None,
        "bloom_tier": "understand",
    }


class TestGenerateSlidesConcurrency:
    """Regression tests for bounded-concurrency in-order slide emission."""

    @pytest.mark.asyncio
    async def test_slides_yield_in_order_despite_out_of_order_completion(self):
        """Varying per-slide delays should still yield slides in slide_number order."""
        # Completion order would be: 1, 3, 5, 7, 4, 6, 2 (by delay).
        delays = {
            1: 0.01,
            2: 0.30,  # slowest among 2-7
            3: 0.05,
            4: 0.20,
            5: 0.08,
            6: 0.15,
            7: 0.10,
        }

        async def fake_generate(
            client, system_prompt, learning_cycle_plan, context_package, slide_number
        ):
            await asyncio.sleep(delays[slide_number])
            return _slide_stub(slide_number)

        service = ASGFSlideService()

        with patch.object(
            ASGFSlideService, "_generate_single_slide", side_effect=fake_generate
        ), patch(
            "app.services.asgf_slide_service.get_async_anthropic_client",
            return_value=object(),
        ):
            start = time.perf_counter()
            collected: list[dict] = []
            async for slide in service.generate_slides({}, {}):
                collected.append(slide)
            elapsed = time.perf_counter() - start

        # All 7 slides, in order, no gaps, no duplicates.
        assert len(collected) == TOTAL_SLIDES
        assert [s["slide_number"] for s in collected] == list(range(1, TOTAL_SLIDES + 1))

        # Proves parallelism: wall-clock must be strictly less than sum of delays.
        total_sequential = sum(delays.values())
        assert elapsed < total_sequential, (
            f"expected parallel execution: elapsed={elapsed:.3f}s, "
            f"sequential sum={total_sequential:.3f}s"
        )

    @pytest.mark.asyncio
    async def test_slide_one_yields_before_slides_two_through_seven_start(self):
        """Slide 1 should complete synchronously before slides 2-7 run."""
        started_slides: list[int] = []

        async def fake_generate(
            client, system_prompt, learning_cycle_plan, context_package, slide_number
        ):
            started_slides.append(slide_number)
            await asyncio.sleep(0.01)
            return _slide_stub(slide_number)

        service = ASGFSlideService()

        with patch.object(
            ASGFSlideService, "_generate_single_slide", side_effect=fake_generate
        ), patch(
            "app.services.asgf_slide_service.get_async_anthropic_client",
            return_value=object(),
        ):
            agen = service.generate_slides({}, {})
            first = await agen.__anext__()

            # At this point only slide 1 should have started.
            assert first["slide_number"] == 1
            assert started_slides == [1]

            # Drain the rest so the generator closes cleanly.
            remaining = [slide async for slide in agen]
            assert [s["slide_number"] for s in remaining] == list(range(2, TOTAL_SLIDES + 1))

    @pytest.mark.asyncio
    async def test_error_placeholder_yielded_in_order_on_failure(self):
        """If one slide raises, its error-placeholder must still be yielded in slot."""

        async def fake_generate(
            client, system_prompt, learning_cycle_plan, context_package, slide_number
        ):
            await asyncio.sleep(0.01)
            if slide_number == 4:
                raise RuntimeError("boom")
            return _slide_stub(slide_number)

        service = ASGFSlideService()

        with patch.object(
            ASGFSlideService, "_generate_single_slide", side_effect=fake_generate
        ), patch(
            "app.services.asgf_slide_service.get_async_anthropic_client",
            return_value=object(),
        ):
            collected: list[dict] = []
            async for slide in service.generate_slides({}, {}):
                collected.append(slide)

        assert [s["slide_number"] for s in collected] == list(range(1, TOTAL_SLIDES + 1))
        slide_four = collected[3]
        assert slide_four["slide_number"] == 4
        assert slide_four.get("error") is True
        assert "failed" in slide_four["body"].lower()
        # Other slides should not be marked as errors.
        for s in collected:
            if s["slide_number"] != 4:
                assert not s.get("error")

    @pytest.mark.asyncio
    async def test_slide_one_failure_still_yields_remaining_slides(self):
        """If slide 1 raises, an error-placeholder is yielded and slides 2-7 still run."""

        async def fake_generate(
            client, system_prompt, learning_cycle_plan, context_package, slide_number
        ):
            if slide_number == 1:
                raise RuntimeError("slide-1 boom")
            await asyncio.sleep(0.01)
            return _slide_stub(slide_number)

        service = ASGFSlideService()

        with patch.object(
            ASGFSlideService, "_generate_single_slide", side_effect=fake_generate
        ), patch(
            "app.services.asgf_slide_service.get_async_anthropic_client",
            return_value=object(),
        ):
            collected: list[dict] = []
            async for slide in service.generate_slides({}, {}):
                collected.append(slide)

        assert [s["slide_number"] for s in collected] == list(range(1, TOTAL_SLIDES + 1))
        assert collected[0].get("error") is True

    @pytest.mark.asyncio
    async def test_pending_tasks_cancelled_on_generator_close(self):
        """Closing the generator early must cancel in-flight slide-2..7 tasks."""

        async def fake_generate(
            client, system_prompt, learning_cycle_plan, context_package, slide_number
        ):
            if slide_number == 1:
                return _slide_stub(slide_number)
            # Slides 2-7 sleep long enough that they would still be pending
            # at the time we call aclose().
            await asyncio.sleep(2.0)
            return _slide_stub(slide_number)

        recorded_tasks: list[asyncio.Task] = []
        real_create_task = asyncio.create_task

        def recording_create_task(coro, *args, **kwargs):
            task = real_create_task(coro, *args, **kwargs)
            recorded_tasks.append(task)
            return task

        service = ASGFSlideService()

        with patch.object(
            ASGFSlideService, "_generate_single_slide", side_effect=fake_generate
        ), patch(
            "app.services.asgf_slide_service.get_async_anthropic_client",
            return_value=object(),
        ), patch(
            "app.services.asgf_slide_service.asyncio.create_task",
            new=recording_create_task,
        ):
            agen = service.generate_slides({}, {})
            first = await agen.__anext__()
            assert first["slide_number"] == 1

            # Trigger dispatch of slides 2-7 by requesting the next slide,
            # but bail out before any of them finish so tasks are in-flight.
            try:
                await asyncio.wait_for(agen.__anext__(), timeout=0.05)
            except asyncio.TimeoutError:
                pass

            # Close early — simulates user abort / tab close.
            await agen.aclose()

        # Every task that was dispatched (slides 2-7) must be resolved,
        # not still running in the background.
        assert len(recorded_tasks) == TOTAL_SLIDES - 1
        for task in recorded_tasks:
            assert task.done(), f"task for slide not done after aclose(): {task}"

    @pytest.mark.asyncio
    async def test_semaphore_bounds_concurrency_to_three(self):
        """Never more than 3 concurrent slide-2..7 generations in flight."""
        in_flight = 0
        peak = 0
        lock = asyncio.Lock()

        async def fake_generate(
            client, system_prompt, learning_cycle_plan, context_package, slide_number
        ):
            nonlocal in_flight, peak
            if slide_number == 1:
                return _slide_stub(slide_number)
            async with lock:
                in_flight += 1
                peak = max(peak, in_flight)
            try:
                await asyncio.sleep(0.05)
                return _slide_stub(slide_number)
            finally:
                async with lock:
                    in_flight -= 1

        service = ASGFSlideService()

        with patch.object(
            ASGFSlideService, "_generate_single_slide", side_effect=fake_generate
        ), patch(
            "app.services.asgf_slide_service.get_async_anthropic_client",
            return_value=object(),
        ):
            collected = [slide async for slide in service.generate_slides({}, {})]

        assert len(collected) == TOTAL_SLIDES
        assert peak <= 3, f"semaphore breach: peak concurrency = {peak}"
