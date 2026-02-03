# Handle Smartling API Auth Token Refresh Race Condition

## Problem Statement
The `SmartlingTranslator` has a race condition where multiple concurrent requests might see `_token` is expired or missing and all try to authenticate simultaneously.

## Findings
- `_get_token` checks `_token` and `_token_expiry` but is not protected by a lock.
- `asyncio.gather` in `process_feed` will cause many `_get_token` calls to happen at once.

## Proposed Solutions

### Solution 1: Add an `asyncio.Lock` to `_get_token`
Ensure only one request refreshes the token while others wait.

- **Pros**: Thread/task safe, prevents redundant auth calls.
- **Cons**: Minor overhead.
- **Effort**: Small
- **Risk**: Low

## Acceptance Criteria
- [x] Add `self._token_lock = asyncio.Lock()` to `SmartlingTranslator`.
- [x] Use the lock in `_get_token`.
