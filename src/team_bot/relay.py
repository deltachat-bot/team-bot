import logging
import json

from deltachat_rpc_client import events, EventType

from .util import get_crew_id, get_relay_group, reply
from .commands import crew_help, set_display_name, set_avatar, start_chat, set_outside_help

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
    event.account = account
    crew_id = get_crew_id(event)

    import pdb; pdb.set_trace()
    if msg.is_info:
        if msg.chat_id == crew_id:
            log.debug("Ignoring system message in crew.")
            return
        if not get_relay_group(msg.chat):
            log.debug(f"Ignoring system message in the relay group {msg.chat_id}")
        else:
            log.debug(f"This is a system message in the outside chat {msg.chat_id}")
            relay_group = get_relay_group(msg.chat)
            if "image changed by" in msg.text:
                relay_group.set_image(msg.chat.get_full_snapshot().profile_image)
            if "name changed from" in msg.text:
                group_name = "[%s] %s" % (
                    account.get_config("addr").split("@")[0],
                    msg.chat.get_full_snapshot().name,
                )
                relay_group.set_name(group_name)
        return

    if msg.chat_id == crew_id:
        if msg.text.startswith("/"):
            log.debug(f"handling command by {msg.sender.get_snapshot().name_and_addr}: {msg.text}")
            arguments = msg.text.split(" ")
            if arguments[0] == "/help":
                reply(msg.chat, crew_help(), quote=msg.message)
            if arguments[0] == "/set_name":
                displayname = msg.text.split("/set_name ")[1]
                reply(
                    msg.chat,
                    set_display_name(account, displayname),
                    quote=msg.message,
                )
            if arguments[0] == "/set_avatar":
                result = set_avatar(account, msg, msg.chat)
                reply(msg.chat, result, quote=msg.message)
            if arguments[0] == "/generate_invite":
                reply(msg.chat, account.get_qr_code(), quote=msg.message)
            if arguments[0] == "/start_chat":
                outside_chat, result = start_chat(account, msg)
                if "success" in result:
                    for msg in outside_chat.get_messages():
                        pass  # :todo self.forward_to_relay_group(msg, started_by_crew=True)
                reply(msg.chat, result, quote=msg.message)
            if arguments[0] == "/set_outside_help":
                try:
                    help_message = msg.text.split("/set_outside_help ")[1]
                except IndexError:
                    set_outside_help(account, "")
                    return reply(msg.chat,"Removed help message for outsiders", quote=msg.message)
                set_outside_help(account, help_message)
                reply(msg.chat,f"Set help message for outsiders to {help_message}", quote=msg.message)
        else:
            logging.debug("Ignoring message, just the crew chatting")

    # see RelayPlugin.ac_incoming_message()
