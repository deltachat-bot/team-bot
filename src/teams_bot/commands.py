import deltachat


def help_message() -> str:
    """Get the help message

    :return: the help message
    """
    help_text = """
Change the bot's name:\t/set_name <name>
Show this help text:\t\t/help
    """
    return help_text


def set_display_name(account: deltachat.Account, display_name: str) -> str:
    """Set the display name of the bot.

    :return: a success message
    """
    account.set_config("displayname", display_name)
    return "Display name changed to " + display_name
