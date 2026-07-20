import json
import logging
import re

from deltachat_rpc_client import Account, Chat, Message
from deltachat_rpc_client._utils import AttrDict

log = logging.getLogger("root")


def has_crew(event: AttrDict) -> bool | None:
    account = event.account
    return bool(get_crew_id_from_account(account))


def get_crew_id_from_account(account: Account) -> int | None:
    crew_id = account.get_config("ui.crew_id")
    if crew_id:
        return int(crew_id)


def get_crew_invite(account: Account) -> str:
    """Return crew invite and store it in the account object"""
    crew_invite = account.get_config("ui.crew_invite")
    if not crew_invite:
        crew_invite = account.get_qr_code()
        account.crew_invite = crew_invite
    return crew_invite


def set_relay_groups(account: Account, mappings: [(int, int)]):
    """Store the relay mappings list in the account's database"""
    relay_json = json.dumps(mappings)
    account.set_config("ui.relay_groups", relay_json)


def get_relay_groups(account: Account) -> [(int, int)]:
    """Get a list of all (outside chat, relay group) mappings"""
    relay_json = account.get_config("ui.relay_groups")
    return json.loads(relay_json)


def is_relay_group(chat: Chat) -> bool:
    if chat.id == get_crew_id_from_account(chat.account):
        return False  # it is the crew chat
    if get_relay_group(chat):
        return False  # if it has a relay group, it is an outside chat
    if get_outside_chat(chat):
        return True  # if it has an outside chat, it is a relay group


def get_relay_group(outside_chat: Chat) -> Chat:
    """Return Relay group for an outside chat, return None if it isn't an outside group."""
    for mapping in get_relay_groups(outside_chat.account):
        if mapping[0] == outside_chat.id:
            return outside_chat.account.get_chat_by_id(mapping[1])


def get_outside_chat(relay_group: Chat) -> Chat:
    """Return Outside group for a relay group, return None if it isn't a relay group."""
    for mapping in get_relay_groups(relay_group.account):
        if mapping[1] == relay_group.id:
            return relay_group.account.get_chat_by_id(mapping[0])


def get_group_creation_msg(relay_group: Chat) -> Message | None:
    """For a relay group, return the snapshot of the group creation message."""
    beginnings = ("This is a chat with ", "We sent a message to ", "This is the relay group for ")
    if is_relay_group(relay_group):
        for msg in relay_group.get_messages()[:3]:
            if msg.get_snapshot().text.startswith(beginnings):
                return msg


def get_prefix(account: Account) -> str:
    prefix = account.get_config("ui.prefix")
    if prefix is None:
        prefix = f"[{account.get_config('addr').split('@')[0]}]"
    return prefix


def parse_duration(human_readable: str) -> int:
    """Parse a human readable duration.

    :param: human_readable: the duration with a unit: e.g. 7d, 3w, 30m, 10s
    :return: how many seconds the duration lasts.
    """
    match human_readable[-1]:
        case "w":
            seconds = int(human_readable.rstrip("w")) * 60 * 60 * 24 * 7
        case "d":
            seconds = int(human_readable.rstrip("d")) * 60 * 60 * 24
        case "h":
            seconds = int(human_readable.rstrip("h")) * 60 * 60
        case "m":
            seconds = int(human_readable.rstrip("m")) * 60
        case "s":
            seconds = int(human_readable.rstrip("s"))
        case _:
            seconds = int(human_readable)
    if seconds < 0:
        raise ValueError
    return seconds


def parse_new_command_args(command_text: str) -> ([str], str, str):
    """Parse a /new_command message to get recipients, title, and text out of it.

    :param command_text the text of the command
    :return: a list of recipients as email addresses, a subject/group title, and the text.
    """
    arguments = re.split(" |\n", command_text, maxsplit=3)
    recipients = arguments[1].split(",")
    title = arguments[2].replace("_", " ")
    text = arguments[3]
    return recipients, title, text


def find_original_message(sent_message: Message, account: Account) -> (Chat, Message):
    """For a message the bot sent, find the original message by the crew member.

    :param sent_message: the bot's message
    :param account: the bot's account object
    :return: the chat the original message was sent in, and the original message.
    """
    relay_group = get_relay_group(sent_message.get_snapshot().chat)
    sent_msg = sent_message.get_snapshot()
    for message in relay_group.get_messages().__reversed__():
        msg = message.get_snapshot()
        if msg.text == sent_msg.text and msg.file == sent_msg.file:
            if msg.quote:
                log.debug("Reporting delivery error to relay group.")
                return relay_group, msg.message
            else:
                log.debug("Found message, but it was sent with /new_message. Let's look in the crew chat")
                break

    crew = account.get_chat_by_id(get_crew_id_from_account(account))
    for crew_message in crew.get_messages().__reversed__():
        crew_msg = crew_message.get_snapshot()
        log.debug(f"Looking at crew msg: {crew_msg.text}")
        try:
            recipients, title, text = parse_new_command_args(crew_msg.text)
        except IndexError:
            continue  # not a (valid) /new_message command
        outside_chat = get_outside_chat(relay_group)
        outside_contacts = set(c.get_snapshot().address for c in outside_chat.get_contacts())
        if outside_contacts != set(recipients):
            continue
        if crew_msg.text.startswith("/new_message"):
            if sent_msg.text in text or sent_msg.text in f"{title} {text}":
                return crew, crew_msg.message
    log.debug(f"Original message not found for message: {sent_msg.text}")
    return None, None
