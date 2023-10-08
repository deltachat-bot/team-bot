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


def set_avatar(account: deltachat.Account, message: deltachat.Message) -> str:
    """Set the avatar of the bot.

    :return: a success/failure message
    """
    if not message.is_image():
        return "Please attach an image so the avatar can be changed."
    logging.debug("Found file with MIMEtype %s", message.filemime)
    account.set_avatar(message.filename)
    crew = account.get_chat_by_id(get_crew_id(account))
    crew.set_profile_image(message.filename)
    return "Avatar changed to this image."


def get_crew_id(ac: deltachat.Account, setupplugin=None) -> int:
    """Get the group ID of the crew group if it exists; warn old crews if they might still believe they are the crew.

    :param ac: the account object of the bot.
    :param setupplugin: only if this function is run during `teams-bot init`.
    :return: the chat ID of the crew group, if there is none, return 0.
    """
    crew_id = 0
    for chat in reversed(ac.get_chats()):
        if (
            chat.is_protected()
            and chat.num_contacts() > 1
            and chat.get_name() == f"Team: {ac.get_config('addr')}"
        ):
            logging.debug(
                "Chat with ID %s and title %s could be a crew", chat.id, chat.get_name()
            )
            if crew_id > 0:
                old_crew = ac.get_chat_by_id(crew_id)
                old_crew.set_name(f"Old Team: {ac.get_config('addr')}")
                new_crew = [contact.addr for contact in chat.get_contacts()]
                new_crew_emails = " or ".join(new_crew)
                quit_message = f"There is a new Group for the Team now; you can ask {new_crew_emails} to add you to it."
                logging.debug(
                    "Sending quit message to old crew with ID %s: %s",
                    old_crew.id,
                    quit_message,
                )
                old_crew.send_text(quit_message)
                if setupplugin:
                    setupplugin.outgoing_messages += 1
                old_crew.remove_contact(ac.get_self_contact())
            crew_id = chat.id
        else:
            logging.debug(
                "Chat with ID %s and title %s is not a crew.", chat.id, chat.get_name()
            )
    if crew_id:
        crew_members = [
            contact.addr for contact in ac.get_chat_by_id(crew_id).get_contacts()
        ]
        crew_emails = " or ".join(crew_members)
        logging.debug("The current crew has ID %s and members %s", crew_id, crew_emails)
    else:
        logging.debug("Currently there is no crew")
    return crew_id
