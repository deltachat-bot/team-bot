import json
import logging
import re
from typing import Optional

from deltachat_rpc_client import Account, Chat, Message
from deltachat_rpc_client._utils import AttrDict

log = logging.getLogger("root")


def has_crew(event: AttrDict) -> Optional[bool]:
    account = event.account
    return bool(get_crew_id_from_account(account))


def get_crew_id_from_account(account: Account) -> Optional[int]:
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
    """Get a list of all relay groups"""
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


def mark_seen(relay_group: Chat):
    """For a relay group, mark the last messages in its outside chat as seen."""
    outside_chat = get_outside_chat(relay_group)
    for msg in outside_chat.get_messages():
        msg.mark_seen()


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
