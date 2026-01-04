import logging

from deltachat_rpc_client import Account, Chat, Contact
from deltachat_rpc_client._utils import AttrDict

from .util import get_relay_groups


log = logging.getLogger("root")


def crew_help() -> str:
    """Get the help message for the crew chat

    :return: the help message
    """
    help_text = """
Start a chat:\t/new_message alice@example.org,bob@example.org Chat_Title Hello friends!
Change the bot's name:\t/set_name Name
Change the bot's avatar:\t/set_avatar <attach image>
Generate invite link:\t\t/generate_invite
Show this help text:\t\t/help
Change the help message for outsiders:\t/set_outside_help Hello outsider
    """
    return help_text


def outside_help(account: Account) -> str:
    """Get the help message for outsiders"""
    return account.get_config("ui.outside_help_message")


def set_outside_help(account: Account, help_message: str):
    """Set the help message for outsiders"""
    logging.info("Setting outside_help_message to %s", help_message)
    account.set_config("ui.outside_help_message", help_message)


def set_display_name(account: Account, display_name: str) -> str:
    """Set the display name of the bot.

    :return: a success message
    """
    account.set_config("displayname", display_name)
    return "Display name changed to " + display_name


def set_avatar(account: Account, message: AttrDict, crew: Chat) -> str:
    """Set the avatar of the bot.

    :return: a success/failure message
    """
    if not message.view_type == "Image":
        return "Please attach an image so the avatar can be changed."
    account.set_avatar(message.file)
    crew.set_image(message.file)
    return "Avatar changed to this image."


def start_chat(
    ac: Account,
    command: AttrDict,
) -> (Chat, str):
    """Start a chat with one or more outsiders.

    :param ac: the account object of the bot
    :param command: the message with the command
    :return: the outside chat and a success/failure message
    """
    arguments = command.text.split(" ")
    recipients = arguments[1].split(",")
    title = arguments[2].replace("_", " ")
    words = arguments[3:]
    text = " ".join(words)

    contacts = []
    contact_ids = []
    failed_contacts = []
    encrypted = "encrypted"
    for rec in recipients:
        contact = ac.get_contact_by_addr(rec)
        if contact:
            contacts.append(contact)
            contact_ids.append(str(contact.id))
            if not contact.get_snapshot().is_key_contact:
                encrypted = ""
        else:
            log.error(f"Couldn't find valid contact for {rec}")
            failed_contacts.append(rec)
    if failed_contacts:
        return None, "failed to create contacts for " + ", ".join(rec)
    log.info(f"Sending {encrypted} message to {', '.join(contact_ids)} with subject {title}: {text}")

    if not encrypted:
        chat = Chat(ac, ac._rpc.create_group_chat_unencrypted(ac.id, title))
        for contact in contacts:
            chat.add_contact(contact)
    elif len(contacts) == 1:
        chat = contacts[0].create_chat()
        text = f"{title} {text}"
    else:
        chat = ac.create_group(title)
        for contact in contacts:
            chat.add_contact(contact)

    attachment = command.file if command.file else None
    view_type = command.view_type
    log.debug(f"Message has view_type {view_type} with the attachment {attachment}")
    chat.send_message(text=text, viewtype=view_type, file=attachment)
    return chat, "success"


def offboard(msg: AttrDict, ex_admin: Contact) -> None:
    """Remove a former crew member from all relay groups they are part of.

    :param msg: the AttrDict of the message causing the member removal.
    :param ex_admin: a contact which just got removed from the crew.
    """
    account = msg.chat.account
    for mapping in get_relay_groups(account):
        relay_group = account.get_chat_by_id(mapping[1])
        if ex_admin in relay_group.get_contacts():
            relay_group.remove_contact(ex_admin)
