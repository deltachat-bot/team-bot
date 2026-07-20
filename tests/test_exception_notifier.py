from team_bot.exception_notifier import format_exception_message


def test_format_exception_message_structure_and_escaping():
    try:
        raise ValueError("bad <tag> & 'stuff'")
    except ValueError as e:
        text, body = format_exception_message(e, "incoming_message")

    # text is a single-line preview naming the hook and exception type
    assert "\n" not in text
    assert "incoming_message" in text
    assert "ValueError" in text

    # html body puts the traceback in a <pre> block
    assert "<pre>" in body and "</pre>" in body
    assert "Traceback (most recent call last)" in body

    # the exception message's angle brackets are escaped, never injected raw
    assert "<tag>" not in body
    assert "&lt;tag&gt;" in body
    assert "&amp;" in body
