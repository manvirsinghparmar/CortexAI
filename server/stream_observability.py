"""Structured lifecycle logging for NDJSON streaming responses."""

from __future__ import annotations

import time
from typing import Any

from utils.logger import get_logger

logger = get_logger(__name__)


class StreamLogContext:
    """Track stream body progress after StreamingResponse has returned headers."""

    def __init__(
        self,
        *,
        stream_name: str,
        request_id: str,
        provider: str = "",
        model: str = "",
        research_mode: bool | None = None,
        target_count: int | None = None,
        request_group_id: str = "",
    ) -> None:
        self.stream_name = str(stream_name or "stream").strip() or "stream"
        self.request_id = str(request_id or "").strip()
        self.provider = str(provider or "").strip()
        self.model = str(model or "").strip()
        self.research_mode = research_mode
        self.target_count = target_count
        self.request_group_id = str(request_group_id or "").strip()
        self.started = time.perf_counter()
        self.events_sent = 0
        self.bytes_sent_estimate = 0

    def record_event(self, payload: str | bytes) -> str | bytes:
        self.events_sent += 1
        if isinstance(payload, bytes):
            self.bytes_sent_estimate += len(payload)
        else:
            self.bytes_sent_estimate += len(str(payload).encode("utf-8"))
        return payload

    def log(self, suffix: str, *, level: str = "info", terminal_reason: str = "", **fields: Any) -> None:
        extra_fields: dict[str, Any] = {
            "event": f"{self.stream_name}.stream.{suffix}",
            "request_id": self.request_id,
            "elapsed_ms": int((time.perf_counter() - self.started) * 1000),
            "events_sent": self.events_sent,
            "bytes_sent_estimate": self.bytes_sent_estimate,
        }
        if self.provider:
            extra_fields["provider"] = self.provider
        if self.model:
            extra_fields["model"] = self.model
        if self.research_mode is not None:
            extra_fields["research_mode"] = bool(self.research_mode)
        if self.target_count is not None:
            extra_fields["target_count"] = int(self.target_count)
        if self.request_group_id:
            extra_fields["request_group_id"] = self.request_group_id
        if terminal_reason:
            extra_fields["terminal_reason"] = str(terminal_reason)

        for key, value in fields.items():
            if value is None or value == "":
                continue
            extra_fields[key] = value

        message = f"{self.stream_name} stream {suffix}"
        if level == "warning":
            logger.warning(message, extra={"extra_fields": extra_fields})
        elif level == "error":
            logger.error(message, extra={"extra_fields": extra_fields})
        elif level == "exception":
            logger.exception(message, extra={"extra_fields": extra_fields})
        else:
            logger.info(message, extra={"extra_fields": extra_fields})
