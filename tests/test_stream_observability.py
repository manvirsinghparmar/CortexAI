import logging

from server.stream_observability import StreamLogContext


def test_stream_log_context_records_client_disconnect(caplog):
    caplog.set_level(logging.WARNING, logger="server.stream_observability")

    stream_log = StreamLogContext(
        stream_name="chat",
        request_id="req-stream-log",
        provider="openai",
        model="gpt-4o-mini",
        research_mode=False,
    )
    stream_log.record_event('{"type":"start"}\n')
    stream_log.log(
        "client_disconnected",
        level="warning",
        terminal_reason="client_disconnected",
    )

    disconnect_records = [
        record for record in caplog.records
        if getattr(record, "extra_fields", {}).get("event") == "chat.stream.client_disconnected"
    ]
    assert len(disconnect_records) == 1
    fields = getattr(disconnect_records[0], "extra_fields", {})
    assert fields["request_id"] == "req-stream-log"
    assert fields["terminal_reason"] == "client_disconnected"
    assert fields["events_sent"] == 1
    assert fields["bytes_sent_estimate"] > 0
