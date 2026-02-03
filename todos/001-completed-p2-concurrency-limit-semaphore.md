# Concurrency Limit for Translation Requests

## Problem Statement
The current implementation fires off all translation requests concurrently using `asyncio.gather`. While efficient, a very large GTFS feed with hundreds of alerts could trigger hundreds of simultaneous HTTP requests, potentially hitting Smartling rate limits or exceeding Lambda resource limits (file descriptors/memory).

## Findings
- `FeedProcessor.process_feed` gathers all `_process_translated_string` tasks without limiting concurrency.
- Each string translation then gathers translations for multiple languages.
- Total concurrent requests = (Number of Alerts * Fields per Alert * Target Languages).

## Proposed Solutions

### Solution 1: Use an `asyncio.Semaphore`
Wrap the translation calls in a semaphore to limit the number of active requests.

- **Pros**: Simple to implement, effectively prevents bursts.
- **Cons**: Might slightly slow down processing if the limit is too low.
- **Effort**: Small
- **Risk**: Low

### Solution 2: Batching
Batch strings into groups of 10 or 20.

- **Pros**: Similar to semaphore.
- **Cons**: More complex logic to manage batches.
- **Effort**: Medium

## Recommendation
Use a Semaphore with a reasonable default (e.g., 20).

## Acceptance Criteria
- [x] Add a `CONCURRENCY_LIMIT` setting.
- [x] Use `asyncio.Semaphore` in `FeedProcessor` or `SmartlingTranslator` to limit active requests.
