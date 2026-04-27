import logging

from core.observability import log_throttled, reset_throttled_logs


def test_log_throttled_suppresses_repeats_and_reports_summary(caplog):
    logger = logging.getLogger("tests.observability")
    reset_throttled_logs()

    with caplog.at_level(logging.WARNING, logger="tests.observability"):
        assert log_throttled(
            logger,
            logging.WARNING,
            "loader:fallback",
            "Repeated issue for %s",
            "cell_a",
            now=0.0,
            interval_seconds=30.0,
        )
        assert not log_throttled(
            logger,
            logging.WARNING,
            "loader:fallback",
            "Repeated issue for %s",
            "cell_b",
            now=10.0,
            interval_seconds=30.0,
        )
        assert log_throttled(
            logger,
            logging.WARNING,
            "loader:fallback",
            "Repeated issue for %s",
            "cell_c",
            now=31.0,
            interval_seconds=30.0,
        )

    messages = [record.message for record in caplog.records]

    assert messages == [
        "Repeated issue for cell_a",
        "Repeated issue for cell_c (suppressed 1 similar events)",
    ]
