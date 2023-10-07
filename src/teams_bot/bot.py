import logging
from threading import Event

import deltachat
from deltachat import account_hookimpl


class SetupPlugin:
    def __init__(self, crew_id):
        self.member_added = Event()
        self.crew_id = crew_id
        self.message_sent = Event()
        self.outgoing_messages = 0

    @account_hookimpl
    def ac_member_added(self, chat: deltachat.Chat, contact, actor, message):
        if chat.id == self.crew_id and chat.num_contacts() == 2:
            self.member_added.set()

    @account_hookimpl
    def ac_message_delivered(self, message: deltachat.Message):
        if not message.is_system_message():
            self.outgoing_messages -= 1
            if self.outgoing_messages < 1:
                self.message_sent.set()


class RelayPlugin:
    def __init__(self, account: deltachat.Account):
        self.account = account

    @account_hookimpl
    def ac_incoming_message(self, message: deltachat.Message):
        """This method is called on every incoming message and decides what to do with it."""
        logging.info(
            "New message from %s in chat %s: %s",
            message.get_sender_contact().addr,
            message.chat.get_name(),
            message.text,
        )

        if message.is_system_message():
            logging.debug("This is a system message")
            """:TODO handle chat name changes"""
            return

        if message.chat.id == get_crew_id(self.account):
            if message.text.startswith("/"):
                logging.debug("handling command by %s: %s", message.get_sender_contact().addr, message.text)
                """:TODO handle command"""
            else:
                logging.debug("Ignoring message, just admins chatting")

        elif self.is_relay_group(message.chat):
            if message.quote.get_sender_contact() == self.account.get_self_contact():
                """:TODO forward to original sender"""
            else:
                logging.debug("Ignoring message, just admins chatting")

        else:
            logging.debug("Forwarding message to relay group")
            """:TODO forward message to relay group"""

    def is_relay_group(self, chat: deltachat.Chat) -> bool:
        """Check whether a chat is a relay group."""
        if not chat.get_name().startswith("[%s] " % (self.account.get_config("addr").split("@")[0],)):
            return False  # all relay groups' names begin with a [tag] with the localpart of the teamsbot's address
        if chat.get_messages()[0].get_sender_contact() != self.account.get_self_contact():
            return False  # all relay groups were started by the teamsbot
        if chat.is_protected():
            return False  # relay groups don't need to be protected, so they are not
        for crew_member in self.account.get_chat_by_id(get_crew_id(self.account)).get_contacts():
            if crew_member not in chat.get_contacts():
                return False  # all crew members have to be in any relay group
        return True


def get_crew_id(ac: deltachat.Account, setupplugin: SetupPlugin = None) -> int:
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
