import logging

from deltachat_rpc_client import events
from deltachat_rpc_client._utils import AttrDict

from .commands import crew_help, offboard, outside_help, set_avatar, set_display_name, set_outside_help, start_chat
from .forwarding import forward_to_outside, forward_to_relay_group, reply
from .util import get_crew_id_from_account, get_outside_chat, get_relay_group, is_relay_group, mark_seen

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

    if event.kind == EventType.MSG_DELIVERED:
        delivered_msg = event.account.get_message_by_id(event.msg_id).get_snapshot()
        relay_group = get_relay_group(delivered_msg.chat)
        if relay_group:
            for message in relay_group.get_messages():
                msg = message.get_snapshot()
                if msg.quote:
                    if msg.text == delivered_msg.text and msg.file == delivered_msg.file:
                        log.debug("Confirming successful delivery to outside chat.")
                        msg.message.send_reaction("✅")

    elif event.kind == EventType.MSG_FAILED:
        failed_msg = event.account.get_message_by_id(event.msg_id).get_snapshot()
        relay_group = get_relay_group(failed_msg.chat)
        if relay_group:
            for message in relay_group.get_messages():
                msg = message.get_snapshot()
                if msg.quote:
                    if msg.text == failed_msg.text and msg.file == failed_msg.file:
                        log.debug("Reporting delivery error to outside chat.")
                        delivery_error = "Delivery failed:\n\n" + msg.message.get_info()
                        msg.message.send_reaction("❌")
                        relay_group.send_message(text=delivery_error, quoted_msg=msg.message)


@relayhooks.on(events.MemberListChanged)
def member_added_or_removed(event):
    msg = event.message_snapshot
    account = msg.chat.account
    if msg.chat_id == get_crew_id_from_account(account):
        change = "added" if event.member_added else "removed"
        log.info("crew member %s was %s" % (event.member, change))
        if not event.member_added:
            offboard(msg, event.member)


@relayhooks.on(events.NewMessage)
def incoming_message(event):
    msg = event.message_snapshot
    log.debug(msg)
    account = msg.chat.account
    crew_id = get_crew_id_from_account(account)

    if msg.is_info:
        handle_info_msg(msg, crew_id)
        return

    if msg.chat_id == crew_id:
        handle_msg_in_crew_chat(msg)
    elif is_relay_group(msg.chat):
        handle_msg_in_relay_group(msg)
    else:
        handle_msg_in_outside_chat(msg)


def handle_msg_in_crew_chat(msg: AttrDict):
    account = msg.chat.account

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
        if arguments[0] == "/generate_invite" or arguments[0] == "/generate-invite":
            reply(msg.chat, account.get_qr_code(), quote=msg.message)
        if arguments[0] == "/new_message":
            message, result = start_chat(account, msg)
            if "success" in result:
                forward_to_relay_group(message.get_snapshot(), started_by_crew=True)
            reply(msg.chat, result, quote=msg.message)
        if arguments[0] == "/set_outside_help":
            try:
                help_message = msg.text.split("/set_outside_help ")[1]
            except IndexError:
                set_outside_help(account, "")
                return reply(msg.chat, "Removed help message for outsiders", quote=msg.message)
            set_outside_help(account, help_message)
            reply(msg.chat, f"Set help message for outsiders to {help_message}", quote=msg.message)
    else:
        log.debug("Ignoring message, just the crew chatting")


def handle_msg_in_relay_group(msg: AttrDict):
    account = msg.chat.account
    if msg.quote:
        quoted_msg = account.get_message_by_id(msg.quote.message_id).get_snapshot()
        if quoted_msg.sender == account.self_contact:
            if not msg.quote.text.startswith("This is the relay group for"):
                log.debug("Forwarding message to outsider")
                forward_to_outside(msg)
            else:
                log.debug("Ignoring reply to the group creation message")
        else:
            log.debug("Ignoring message, just the crew chatting")
    else:
        mark_seen(msg.chat)
        log.debug("Ignoring message, just the crew chatting")


def handle_msg_in_outside_chat(msg: AttrDict):
    """Handle an incoming message in an outside chat, decide whether to forward it to a relay group."""
    account = msg.chat.account

    # if the message came to an outside chat
    if msg.text.startswith("/help"):
        log.info("Outsider %s asked for help", msg.sender.get_snapshot().name_and_addr)
        help_message = outside_help(account)
        if help_message is None:
            help_message = f"I forward messages to the {account.get_config('displayname')} team."
        if help_message == "":
            log.debug("Help message empty, forwarding message to relay group")
        else:
            log.debug(
                "Sending help text to %s: %s",
                msg.sender.get_snapshot().name_and_addr,
                help_message,
            )
            return reply(msg.chat, help_message, quote=msg.message)
    log.debug("Forwarding message to relay group")
    forward_to_relay_group(msg)


def handle_info_msg(msg: AttrDict, crew_id: int):
    """Handle an incoming info message, whether in the crew, a relay group, or an outside chat."""
    account = msg.chat.account

    if msg.chat_id == crew_id:
        log.debug("Ignoring system message in crew.")
        return
    if get_outside_chat(msg.chat):
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
