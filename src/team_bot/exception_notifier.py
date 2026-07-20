"""Exception notifications for team-bot hooks.

Exceptions caught in the deltachat-rpc-client event loop are only registered in
the systemd journal; this decorator exposes them to the crew chat as messages.
"""

import functools
import html
import logging
import time
import traceback

from .util import get_crew_id_from_account

log = logging.getLogger("root")


class ExceptionNotifier:
    """Send hook exceptions to the chat group.

    At least cooldown_seconds have to have passed for recurring exceptions to
    not flood the group; exceptions are always logged to journald."""

    def __init__(self, cooldown_seconds: int = 3600):
        self._account = None  # set by main.py: set_account()
        self._last_notification = 0.0  # timestamp
        self._cooldown = cooldown_seconds

    def set_account(self, account) -> None:
        self._account = account

    def should_notify(self, now: float) -> bool:
        return now - self._last_notification >= self._cooldown

    def notify_crew(self, exc: Exception, hook_name: str) -> bool:
        """Send the crew one exception notification, subject to the cooldown."""
        try:
            if self._account is None:
                log.error("ExceptionNotifier: no account set; skipping crew notice.")
                return False
            now = time.time()
            if not self.should_notify(now):
                return False
            crew_id = get_crew_id_from_account(self._account)
            if not crew_id:
                log.error("ExceptionNotifier: no crew configured; skipping crew notice.")
                return False
            text, body = format_exception_message(exc, hook_name)
            self._account.get_chat_by_id(crew_id).send_message(text=text, html=body)
            self._last_notification = now
            return True
        except Exception:
            log.exception("failed to send exception notification to crew")
            return False


# Module-level singleton shared by every wrapped hook.
exception_notifier = ExceptionNotifier()


def format_exception_message(exc: Exception, hook_name: str) -> tuple[str, str]:
    """Return (text_summary, html_body) for a hook exception."""
    exc_type = type(exc).__name__
    text = f"Exception in {hook_name}: {exc_type}: {exc} (open for traceback)"
    tb_text = html.escape("".join(traceback.format_exception(exc)))
    body = (
        f"<p><b>Exception in {html.escape(hook_name)}</b></p>"
        f"<p>{html.escape(f'{exc_type}: {exc}')}</p>"
        f"<pre>{tb_text}</pre>"
    )
    return text, body


def with_exception_notification(func):
    """Wrap an event hook for crew notification."""

    @functools.wraps(func)
    def wrapper(event):
        try:
            return func(event)
        except Exception as e:
            log.exception("Exception in hook %s: %s", func.__name__, type(e).__name__)
            exception_notifier.notify_crew(e, func.__name__)

    return wrapper
