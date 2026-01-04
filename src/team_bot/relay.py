import logging
import json

from deltachat_rpc_client import events, EventType

from .util import get_crew_id

log = logging.getLogger("root")
relayhooks = events.HookCollection()


@relayhooks.on(events.RawEvent)
def catch_events(event):
    """This is called on every raw event and can be used for any kind of event handling.
    Unfortunately deltachat-rpc-client doesn't offer high-level events for MSG_DELIVERED or SECUREJOIN_INVITER_PROGRESS
    yet, so this needs to be done with raw events.

    :param event: the event object
    """
    log.debug(event)
    if event.kind == EventType.IMAP_CONNECTED:
        if not event.account.get_config("ui.relay_groups"):
            empty_list_json = json.dumps([])
            event.account.set_config("ui.relay_groups", empty_list_json)
            log.info("Initialized empty list of relay groups")


@relayhooks.on(events.NewMessage)
def incoming_message(event):
    log.debug(event)
    msg = event.message_snapshot
    account = msg.chat.account
    crew_id = get_crew_id(event)

    import pdb; pdb.set_trace()
    