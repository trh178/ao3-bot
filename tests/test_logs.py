import logging
import sys

from ao3bot.logs import RedactingFormatter


def test_secret_is_redacted_from_message_and_traceback():
    formatter = RedactingFormatter("%(message)s", ["hunter2-secret"])
    try:
        raise ValueError("login failed for password hunter2-secret")
    except ValueError:
        exc_info = sys.exc_info()
    record = logging.LogRecord(
        "ao3bot", logging.ERROR, __file__, 1, "using %s", ("hunter2-secret",), exc_info
    )
    text = formatter.format(record)
    assert "hunter2-secret" not in text
    assert "using ***" in text
    assert "ValueError" in text


def test_no_secrets_leaves_text_alone():
    formatter = RedactingFormatter("%(message)s", [])
    record = logging.LogRecord("ao3bot", logging.INFO, __file__, 1, "hello", (), None)
    assert formatter.format(record) == "hello"
