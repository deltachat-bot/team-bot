import logging

import deltachat
from deltachat.capi import lib as dclib
from deltachat.message import _view_type_mapping


def help_message() -> str:
    """Get the help message

    :return: the help message
    """
    help_text = """
Start a chat:\t/start_chat alice@example.org,bob@example.org Chat_Title Hello friends!
Change the bot's name:\t/set_name <name>
Change the bot's avatar:\t/set_avatar (attach image)
Show this help text:\t\t/help
    """
    return help_text


def set_display_name(account: deltachat.Account, display_name: str) -> str:
    """Set the display name of the bot.

    :return: a success message
    """
    account.set_config("displayname", display_name)
    return "Display name changed to " + display_name


def set_avatar(
    account: deltachat.Account, message: deltachat.Message, crew: deltachat.Chat
) -> str:
    """Set the avatar of the bot.

    :return: a success/failure message
    """
    if not message.is_image():
        return "Please attach an image so the avatar can be changed."
    logging.debug("Found file with MIMEtype %s", message.filemime)
    account.set_avatar(message.filename)
    crew.set_profile_image(message.filename)
    return "Avatar changed to this image."


def start_chat(
    ac: deltachat.Account,
    command: deltachat.Message,
) -> (deltachat.Chat, str):
    """Start a chat with one or more outsiders.

    :param ac: the account object of the bot
    :param command: the message with the command
    :return: the outside chat and a success/failure message
    """
    arguments = command.text.split(" ")
    recipients = arguments[1].split(",")
    title = arguments[2].replace("_", " ")
    words = []
    for i in range(3, len(arguments)):
        words.append(arguments[i])
    text = " ".join(words)
    attachment = command.filename if command.filename else ""
    view_type = get_message_view_type(command)

    logging.info(
        "Sending %s message to %s with subject '%s': %s",
        view_type,
        ", ".join(recipients),
        title,
        text,
    )
    chat = ac.create_group_chat(title, recipients)
    msg = deltachat.Message.new_empty(ac, view_type)
    msg.set_text(text)
    if attachment:
        logging.info("Message has a %s attachment with path %s", view_type, attachment)
        msg.set_file(attachment)
    sent_id = dclib.dc_send_msg(ac._dc_context, chat.id, msg._dc_msg)
    if sent_id == msg.id:
        return chat, "Chat successfully created."
    else:
        logging.error("Can't send message. sent_id: %s, msg.id: %s", sent_id, msg.id)
        return chat, "Something went wrong...\n\n" + help_message()


def get_message_view_type(message: deltachat.Message) -> str:
    """Get the view_type of a Message."""
    for view_name, view_code in _view_type_mapping.items():
        if view_code == message._view_type:
            return view_name
