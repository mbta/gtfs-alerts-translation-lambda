# Protocol Buffer Serialization Field Names

## Problem Statement
The `serialize` method for JSON uses `preserving_proto_field_name=True`. However, GTFS-RT consumers sometimes expect the `camelCase` names defined in the proto file for JSON, or specific field names.

## Findings
- `json_format.MessageToJson(feed, preserving_proto_field_name=True)` is used.
- MBTA feeds use snake_case in the JSON, which `preserving_proto_field_name=True` ensures.

## Recommendation
The current implementation is correct for MBTA standards.

## Acceptance Criteria
- [x] Verify JSON field naming convention matches MBTA (snake_case).
