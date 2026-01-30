import logging

from deltachat_rpc_client import Chat, Message
from deltachat_rpc_client._utils import AttrDict

from .util import get_crew_id_from_account, get_outside_chat, get_relay_group, get_relay_groups, set_relay_groups

log = logging.getLogger("root")


def reply(chat: Chat, text: str, attachment: str = None, quote: Message = None):
    """Reply to a chat, with a text, optionally including an attachment or quoting a message."""
    chat.send_message(
        text=text,
        file=attachment,
        quoted_msg=quote,
    )


def forward_to_outside(msg: AttrDict):
    """Forward an answer to the corresponding outside chat"""
    outside_chat = get_outside_chat(msg.chat)
    if not outside_chat:
        log.error(
            "Couldn't find the corresponding outside chat for relay group %s",
            msg.chat.id,
        )
        return
    try:
        if msg.quote:
            quoted_msg = msg.quote.message_id
        else:
            quoted_msg = None
        if not msg.has_html:
            msg.html = None
        outside_chat.send_message(
            html=msg.html,
            text=msg.text,
            viewtype=msg.view_type,
            file=msg.file,
            filename=msg.file_name,
            quoted_msg=quoted_msg,
        )

    except Exception as e:
        reply(msg.chat, "Sending message failed.", quote=msg.message)
        raise e


def forward_to_relay_group(msg: AttrDict, started_by_crew: bool = False):
    """Forward a message to a relay group, create it if it doesn't yet exist."""
    account = msg.chat.account
    crew_id = get_crew_id_from_account(account)
    crew = account.get_chat_by_id(crew_id)
    crew_members = crew.get_contacts()
    crew_members.remove(account.self_contact)

    relay_group = get_relay_group(msg.chat)
    if not relay_group:
        group_name = "[%s] %s" % (
            account.get_config("addr").split("@")[0],
            msg.chat.get_full_snapshot().name,
        )
        log.info(f"Creating new relay group: {group_name}")
        relay_group = account.create_group(group_name)
        for member in crew_members:
            relay_group.add_contact(member)
        relay_group.set_image(msg.chat.get_full_snapshot().profile_image)

        outside_chat = msg.chat
        if outside_chat.get_basic_snapshot().chat_type == "Group":
            outside_members = outside_chat.get_contacts()
            outside_members.remove(account.self_contact)
            recipients = ", ".join([member.get_snapshot().display_name for member in outside_members])
            recipients = " and ".join(recipients.rsplit(", ", 1))
        else:
            recipients = outside_chat.get_contacts()[0].get_snapshot().name_and_addr
        if started_by_crew:
            explanation = f"We sent a message to {recipients}.\n\nThis was our first message:"
        else:
            explanation = f"This is a chat with {recipients}; Only *replies* will be visible to the outside."
        relay_group.send_text(explanation)
        relay_mappings = get_relay_groups(account)
        relay_mappings.append(tuple([msg.chat.id, relay_group.id]))
        set_relay_groups(account, relay_mappings)

    if msg.quote:
        quoted_msg = msg.quote.message_id
    else:
        quoted_msg = None
    relay_group.send_message(
        override_sender_name=msg.sender.get_snapshot().name_and_addr,
        html=msg.html if msg.has_html else None,
        text=msg.text,
        viewtype=msg.view_type,
        file=msg.file,
        filename=msg.file_name,
        quoted_msg=quoted_msg,
    )
