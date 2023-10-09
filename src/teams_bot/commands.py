import logging

import deltachat
from deltachat.capi import lib as dclib


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
    recipients: [],
    title: str,
    text: str,
    attachment: str,
    view_type: str,
) -> (deltachat.Chat, str):
    """Start a chat with one or more outsiders.

    :param ac: the account object of the bot
    :param recipients: A list with email addresses to be added to the group
    :param title: The title of the group
    :param text: The test of the first message
    :param attachment: (optional) an attachment, can be empty string
    :param view_type: the view_type of the message
    :return: the outside chat and a success/failure message
    """
    logging.info(
        "Sending message to %s with subject '%s': %s",
        ", ".join(recipients),
        title,
        text,
    )
    chat = ac.create_group_chat(title, recipients)
    msg = deltachat.Message.new_empty(ac, view_type=view_type)
    msg.set_text(text)
    if attachment:
        logging.info("Message has a %s attachment with path %s", view_type, attachment)
        msg.set_file(attachment, view_type)
    sent_id = dclib.dc_send_msg(ac._dc_context, chat.id, msg._dc_msg)
    if sent_id == msg.id:
        return chat, "Chat successfully created."
    else:
        logging.error("Can't send message. sent_id: %s, msg.id: %s", sent_id, msg.id)
        return chat, "Something went wrong...\n\n" + help_message()
