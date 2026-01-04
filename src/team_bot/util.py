import json
from typing import Optional

from deltachat_rpc_client import Account, Chat, Message
from deltachat_rpc_client._utils import AttrDict


def get_crew_id(event: AttrDict) -> Optional[int]:
    ac = event.account
    crew_id = ac.get_config("ui.crew_id")
    if crew_id:
        return int(crew_id)


def get_crew_invite(account: Account) -> str:
    """Return crew invite and store it in the account object"""
    crew_invite = account.get_config("ui.crew_invite")
    if not crew_invite:
        crew_invite = account.get_qr_code()
        account.crew_invite = crew_invite
    return crew_invite


def get_relay_groups(account: Account) -> [(int, int)]:
    """Get a list of all relay groups"""
    relay_json = account.get_config("ui.relay_groups")
    return json.loads(relay_json)


def get_relay_group(outside_chat: Chat) -> Chat:
    """Return Relay group for an outside chat, return None if there is none."""
    for mapping in get_relay_groups(outside_chat.account):
        if mapping[0] == outside_chat.id:
            return outside_chat.account.get_chat_by_id(mapping[1])


def reply(chat: Chat, text: str, attachment: str = None, quote: Message = None):
    """Reply to a chat, with a text, optionally including an attachment or quoting a message."""
    chat.send_message(
        text=text,
        file=attachment,
        quoted_msg=quote,
    )
