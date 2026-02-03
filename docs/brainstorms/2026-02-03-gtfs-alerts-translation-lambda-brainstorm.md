---
date: 2026-02-03
topic: gtfs-alerts-translation-lambda
---

# GTFS-RT ServiceAlerts Translation Lambda

## What We're Building
An AWS Lambda function written in Python that intercepts or fetches a GTFS-Realtime ServiceAlerts feed, translates the English text fields into other languages using the Smartling API, and uploads the translated feed to a destination (S3).

## Why This Approach
We selected the **Typed GTFS Processor** approach (Approach 1). By deserializing the data into strict Python objects using `gtfs-realtime-bindings`, we ensure that we only modify specific fields (`header_text`, `description_text`) and guarantee that the output remains a valid GTFS-RT feed. This avoids the risks of accidental corruption inherent in generic "tree-walking" approaches.

## Key Decisions

- **Language:** Python (excellent library support for both Protobuf and JSON handling).
- **Trigger Strategy:** "Event-Aware Config-Driven".
  - Default: Pulls from `SOURCE_URL` (HTTP or S3) defined in env vars.
  - Override: If triggered by an S3 Event, it ignores the default and processes the specific file that triggered the event.
- **Translation Interface:**
  - We will define a `Translator` abstract base class to decouple the business logic from the specific provider.
  - The initial implementation will be `SmartlingTranslator`, hitting the `POST /machine-translation/v2/accounts/{accountUid}/locales/{localeId}/translate` endpoint.
- **Data Handling:**
  - Input format (JSON vs Protobuf) will be auto-detected via file headers or extensions.
  - Output format will rigorously match the input format.
- **Configuration:**
  - `SMARTLING_USER_ID` / `SMARTLING_USER_SECRET`
  - `SOURCE_URL` (Default pull source)
  - `DESTINATION_BUCKET_URL` (S3 path for output)
  - `TARGET_LANGUAGES` (Comma-separated list, e.g., "es,fr,pt")

## Open Questions
- **Smartling Batching:** Does the Smartling API support batch translation of multiple strings in one request? (We will implement individual calls first, but optimization may be needed later).
- **Caching:** Should we cache translations for identical alert strings to save costs? (Deferred for v2).

## Next Steps
→ `/workflows:plan` for implementation details
