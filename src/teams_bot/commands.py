import logging

import deltachat


def help_message() -> str:
    """Get the help message

    :return: the help message
    """
    help_text = """
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
