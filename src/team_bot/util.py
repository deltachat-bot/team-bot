import json
import logging
from typing import Optional

from deltachat_rpc_client import Account, Chat
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
