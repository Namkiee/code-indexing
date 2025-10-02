# Logging & Request Tracing

The server now emits structured JSON logs and propagates a request scoped identifier so
that every log line can be correlated to a single API call.

## Request IDs

- Incoming requests can provide an `X-Request-ID` header.
- When the header is not provided the server generates a UUID4 based identifier.
- The final request identifier is returned in the response via the same header so that
  clients can correlate logs, traces, and API responses.
- All log lines that are produced while the request is being processed include this
  identifier under the `request_id` key.

## Structured JSON output

Logging output is formatted as JSON and written to standard output. The schema contains a
minimal set of well defined fields:

| Field        | Description                                                    |
| ------------ | -------------------------------------------------------------- |
| `timestamp`  | UTC timestamp in ISO-8601 format.                               |
| `level`      | Log level (e.g. `INFO`, `WARNING`, `ERROR`).                    |
| `logger`     | Logger name that produced the message.                          |
| `message`    | Human readable message.                                         |
| `request_id` | Present when a request identifier has been assigned.           |
| `…`          | Any additional contextual attributes passed via `logger.info`. |

### Example

```json
{
  "timestamp": "2024-06-01T08:15:27.123456+00:00",
  "level": "INFO",
  "logger": "app.request",
  "message": "request_completed",
  "request_id": "7a0d1bd2061d4c4f9c8262756f170e02",
  "method": "POST",
  "path": "/v1/search",
  "status_code": 200,
  "duration_ms": 42
}
```

## Accessing request IDs inside handlers

The middleware exposes the current request identifier through
`app.utils.logging.REQUEST_ID_CTX`. This can be used inside routes or background tasks to
include the request identifier in downstream calls.

```python
from app.utils.logging import REQUEST_ID_CTX

request_id = REQUEST_ID_CTX.get()  # returns None outside of an active request
```
