import logging

from deltachat_rpc_client import EventType, events
from deltachat_rpc_client._utils import AttrDict

from .commands import (
    add_contact,
    crew_help,
    mute_relay_group,
    offboard,
    outside_help,
    relay_group_help,
    resend_missed_messages,
    set_avatar,
    set_display_name,
    set_ephemeral_timer,
    set_outside_help,
    set_prefix,
    start_chat,
    unmute_relay_group,
)
from .exception_notifier import with_exception_notification
from .forwarding import forward_to_outside, forward_to_relay_group, reply
from .util import (
    find_original_message,
    get_crew_id_from_account,
    get_group_creation_msg,
    get_outside_chat,
    get_relay_group,
    get_relay_groups,
    is_relay_group,
)

log = logging.getLogger("root")
relayhooks = events.HookCollection()
relayhooks.__name__ = "Relay hooks"


@relayhooks.on(events.RawEvent)
@with_exception_notification
def catch_events(event):
    """This is called on every raw event and can be used for any kind of event handling.
    Unfortunately deltachat-rpc-client doesn't offer high-level events for MSG_DELIVERED or SECUREJOIN_INVITER_PROGRESS
    yet, so this needs to be done with raw events.

    :param event: the event object
    """
    log.debug(event)

    if event.kind == EventType.MSG_DELIVERED:
        delivered_msg = event.account.get_message_by_id(event.msg_id)
        log.info(f"Delivered message successfully: {delivered_msg.get_snapshot().text}")
        if get_relay_group(delivered_msg.get_snapshot().chat):
            orig_chat, orig_message = find_original_message(delivered_msg, event.account)
            if orig_chat:
                log.debug(f"Notifying success in {orig_chat.get_full_snapshot().name}")
                orig_message.send_reaction("✅")

    elif event.kind == EventType.MSG_FAILED:
        failed_msg = event.account.get_message_by_id(event.msg_id)
        log.warning(f"Sending message failed: {failed_msg.get_snapshot().text}")
        if get_relay_group(failed_msg.get_snapshot().chat):
            orig_chat, orig_message = find_original_message(failed_msg, event.account)
            if orig_chat:
                delivery_error = "Delivery failed:\n\n" + failed_msg.get_info()
                orig_chat.send_message(text=delivery_error, quoted_msg=orig_message)
                orig_message.send_reaction("❌")


@relayhooks.on(events.MemberListChanged)
@with_exception_notification
def member_added_or_removed(event):
    msg = event.message_snapshot
    account = msg.chat.account
    if msg.chat_id == get_crew_id_from_account(account):
        change = "added" if event.member_added else "removed"
        log.info("crew member %s was %s" % (event.member, change))
        if not event.member_added:
            offboard(msg, event.member)
    if msg.chat_id in [relay_group for _, relay_group in get_relay_groups(account)]:
        if event.member_added:
            log.info("%s was added to relay group %s, resending group creation message" % (event.member, msg.chat_id))
            get_group_creation_msg(msg.chat).resend()


@relayhooks.on(events.NewMessage)
@with_exception_notification
def incoming_message(event):
    msg = event.message_snapshot
    log.debug(msg)
    msg.message.mark_seen()
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

    if not msg.text.startswith("/"):
        log.debug("Ignoring message, just the crew chatting")
        return

    log.debug(f"handling Team Chat command by {msg.sender.get_snapshot().name_and_addr}: {msg.text}")
    arguments = msg.text.split()

    match arguments:
        case ["/help", *_]:
            reply(msg.chat, crew_help(), quote=msg.message)

        case ["/set_name", *_] if len(arguments) > 1:
            displayname = msg.text.split("/set_name ", 1)[1]
            reply(msg.chat, set_display_name(account, displayname), quote=msg.message)
        case ["/set_name"]:
            reply(msg.chat, "Invalid syntax. Usage: /set_name <new bot name>", quote=msg.message)

        case ["/set_avatar", *_]:
            result = set_avatar(account, msg, msg.chat)
            reply(msg.chat, result, quote=msg.message)

        case ["/generate_invite", *_] | ["/generate-invite", *_]:
            reply(msg.chat, account.get_qr_code(), quote=msg.message)

        case ["/new_message", *_]:
            try:
                message, result = start_chat(account, msg)
            except (IndexError, ValueError):
                reply(
                    msg.chat,
                    "Invalid syntax. Usage: /new_message alice@example.org,bob@example.org Chat_Title Hello friends!",
                    quote=msg.message,
                )
            else:
                if "success" in result:
                    forward_to_relay_group(message.get_snapshot(), started_by_crew=True)
                reply(msg.chat, result, quote=msg.message)

        case ["/add_contact", *_]:
            message = add_contact(account, msg)
            reply(msg.chat, message, quote=msg.message)

        case ["/set_prefix", *_]:
            message = set_prefix(account, arguments)
            reply(msg.chat, message, quote=msg.message)

        case ["/set_outside_help", *_] if len(arguments) > 1:
            help_message = msg.text.split("/set_outside_help ", 1)[1]
            set_outside_help(account, help_message)
            reply(msg.chat, f"Set help message for outsiders to {help_message}", quote=msg.message)
        case ["/set_outside_help"]:
            set_outside_help(account, "")
            reply(msg.chat, "Removed help message for outsiders", quote=msg.message)


def handle_msg_in_relay_group(msg: AttrDict):
    account = msg.chat.account
    if msg.text.startswith("/"):
        log.debug(f"handling Relay Group command by {msg.sender.get_snapshot().name_and_addr}: {msg.text}")
        arguments = msg.text.split()

        match arguments:
            case ["/help", *_]:
                reply(msg.chat, relay_group_help(), quote=msg.message)

            case ["/timer"]:
                result = set_ephemeral_timer(msg.chat, "0")
                reply(msg.chat, result, quote=msg.message)
            case ["/timer", duration, *_]:
                result = set_ephemeral_timer(msg.chat, duration)
                reply(msg.chat, result, quote=msg.message)

            case [cmd, *_] if cmd in ("/spam", "/mute"):
                if mute_relay_group(msg.chat):
                    if cmd != "/spam":  # workaround for some other automation
                        reply(msg.chat, "Ignoring chat in the future.", quote=msg.message)
                else:
                    reply(msg.chat, "Chat is already muted.", quote=msg.message)

            case ["/unmute", *_]:
                if unmute_relay_group(msg.chat):
                    reply(msg.chat, "Receiving messages again:", quote=msg.message)
                    resend_missed_messages(msg.chat)
                else:
                    reply(msg.chat, "Chat is not muted anyway.", quote=msg.message)
    elif msg.quote:
        quoted_msg = account.get_message_by_id(msg.quote.message_id).get_snapshot()
        if quoted_msg.sender == account.self_contact:
            log.debug("Forwarding message to outsider")
            forward_to_outside(msg)
        else:
            log.debug("Ignoring message, just the crew chatting")
    else:
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
    if msg.chat.get_basic_snapshot().is_muted:
        log.debug(f"Ignoring message in muted outside chat {msg.chat_id}")
        return
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
        if msg.chat.get_basic_snapshot().is_muted:
            log.debug(f"Ignoring message in muted outside chat {msg.chat_id}")
            return
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
