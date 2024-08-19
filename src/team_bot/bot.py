import logging
import time
from threading import Event

import pickledb
import deltachat
from deltachat import account_hookimpl
from deltachat.capi import lib as dclib

from .commands import (
    crew_help,
    set_display_name,
    set_avatar,
    generate_invite,
    start_chat,
    outside_help,
    set_outside_help,
)


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
    def __init__(self, account: deltachat.Account, kvstore: pickledb.PickleDB):
        self.account = account
        self.account.set_config("bcc_self", "1")
        self.kvstore = kvstore
        self.crew = account.get_chat_by_id(kvstore.get("crew_id"))
        if not kvstore.get("relays"):
            kvstore.set("relays", list())

    @account_hookimpl
    def ac_outgoing_message(self, message: deltachat.Message):
        while not message.is_out_delivered():
            time.sleep(0.1)
            if message.is_out_failed():
                break
        begin = int(time.time())
        while not message.is_out_failed():
            time.sleep(0.1)
            if int(time.time()) < begin + 10:
                break  # it probably just worked.
        else:
            error = message.get_message_info()
            logging.warning(
                "Outgoing message failed. Forwarding error to relay group: %s", error
            )
            relay_group = self.get_relay_group(message.chat.id)
            relay_group.send_text(f"Sending Message failed:\n\n{error}")

    @account_hookimpl
    def ac_incoming_message(self, message: deltachat.Message):
        """This method is called on every incoming message and decides what to do with it."""

        if message.is_system_message():
            if message.chat.id == self.crew.id:
                return
            if self.is_relay_group(message.chat):
                logging.debug("This is a system message in a relay group.")
            else:
                logging.debug("This is a system message in an outside group.")
                relay_group = self.get_relay_group(message.chat.id)
                if "image changed by" in message.text:
                    relay_group.set_profile_image(message.chat.get_profile_image())
                if "name changed from" in message.text:
                    group_name = "[%s] %s" % (
                        self.account.get_config("addr").split("@")[0],
                        message.chat.get_name(),
                    )
                    relay_group.set_name(group_name)
            return

        if message.chat.id == self.crew.id:
            if message.text.startswith("/"):
                logging.debug(
                    "handling command by %s: %s",
                    message.get_sender_contact().addr,
                    message.text,
                )
                arguments = message.text.split(" ")
                if arguments[0] == "/help":
                    self.reply(message.chat, crew_help(), quote=message)
                if arguments[0] == "/set_name":
                    self.reply(
                        message.chat,
                        set_display_name(
                            self.account, message.text.split("/set_name ")[1]
                        ),
                        quote=message,
                    )
                if arguments[0] == "/set_avatar":
                    result = set_avatar(self.account, message, self.crew)
                    self.reply(message.chat, result, quote=message)
                if arguments[0] == "/generate-invite":
                    text = generate_invite(self.account)
                    self.reply(message.chat, text, quote=message)
                if arguments[0] == "/start_chat":
                    outside_chat, result = start_chat(
                        self.account,
                        message,
                    )
                    if "success" in result:
                        for msg in outside_chat.get_messages():
                            self.forward_to_relay_group(msg, started_by_crew=True)
                    self.reply(message.chat, result, quote=message)
                if arguments[0] == "/set_outside_help":
                    try:
                        help_message = message.text.split("/set_outside_help ")[1]
                    except IndexError:
                        set_outside_help(self.kvstore, "")
                        return self.reply(
                            message.chat,
                            "Removed help message for outsiders",
                            quote=message,
                        )
                    set_outside_help(self.kvstore, help_message)
                    self.reply(
                        message.chat,
                        f"Set help message for outsiders to {help_message}",
                        quote=message,
                    )
            else:
                logging.debug("Ignoring message, just the crew chatting")

        elif self.is_relay_group(message.chat):
            if message.quote:
                if (
                    message.quote.get_sender_contact()
                    == self.account.get_self_contact()
                ):
                    logging.debug("Forwarding message to outsider")
                    self.forward_to_outside(message)
                else:
                    logging.debug("Ignoring message, just the crew chatting")
            else:
                logging.debug("Ignoring message, just the crew chatting")

        else:
            if message.text.startswith("/help"):
                logging.info(
                    "Outsider %s asked for help", message.get_sender_contact().addr
                )
                help_message = outside_help(self.kvstore)
                if help_message is False:
                    help_message = f"I forward messages to the {self.account.get_config('displayname')} team."
                if help_message == "":
                    logging.debug(
                        "Help message empty, forwarding message to relay group"
                    )
                else:
                    logging.info(
                        "Sending help text to %s: %s",
                        message.get_sender_contact().addr,
                        help_message,
                    )
                    return self.reply(message.chat, help_message, quote=message)
            logging.debug("Forwarding message to relay group")
            self.forward_to_relay_group(message)

    def reply(self, chat: deltachat.Chat, text: str, quote: deltachat.Message = None):
        """Send a reply to a chat, with optional quote."""
        msg = deltachat.Message.new_empty(self.account, view_type="text")
        msg.set_text(text)
        msg.quote = quote
        sent_id = dclib.dc_send_msg(self.account._dc_context, chat.id, msg._dc_msg)
        assert sent_id == msg.id

    def forward_to_outside(self, message: deltachat.Message):
        """forward an answer to an outsider."""
        outside_chat = self.get_outside_chat(message.chat.id)
        if not outside_chat:
            logging.error(
                "Couldn't find the corresponding outside chat for relay group %s",
                message.chat.id,
            )
            return
        """:TODO don't forward if message is the explanation message"""
        try:
            outside_chat.send_msg(message)
        except Exception as e:
            self.reply(message.chat, "Sending message failed.", quote=message)
            raise e

    def forward_to_relay_group(self, message: deltachat.Message, started_by_crew=False):
        """forward a request to a relay group; create one if it doesn't exist yet."""
        outsider = message.get_sender_contact().addr
        crew_members = self.crew.get_contacts()
        crew_members.remove(self.account.get_self_contact())
        relay_group = self.get_relay_group(message.chat.id)

        if not relay_group:
            group_name = "[%s] %s" % (
                self.account.get_config("addr").split("@")[0],
                message.chat.get_name(),
            )
            logging.info("creating new relay group: '%s'", group_name)
            relay_group = self.account.create_group_chat(
                group_name, crew_members, verified=False
            )
            if message.chat.get_profile_image():
                relay_group.set_profile_image(message.chat.get_profile_image())
            if started_by_crew:
                explanation = f"We started a chat with {message.chat.get_name()}. This was our first message:"
            else:
                explanation = (
                    f"This is the relay group for {message.chat.get_name()}; "
                    "I'll only forward 'direct replies' to the outside."
                )
            relay_group.send_text(explanation)
            relay_mappings = self.kvstore.get("relays")
            relay_mappings.append(tuple([message.chat.id, relay_group.id]))
            self.kvstore.set("relays", relay_mappings)

        message.set_override_sender_name(outsider)
        relay_group.send_msg(message)

    def is_relay_group(self, chat: deltachat.Chat) -> bool:
        """Check whether a chat is a relay group."""
        for mapping in self.kvstore.get("relays"):
            if mapping[1] == chat.id:
                return True
        return False

    def get_outside_chat(self, relay_group_id: int) -> deltachat.Chat:
        """Get the corresponding outside chat for the ID of a relay group.

        :param relay_group_id: the chat.id of the relay group
        :return: the outside chat
        """
        relay_mappings = self.kvstore.get("relays")
        for mapping in relay_mappings:
            if mapping[1] == relay_group_id:
                return self.account.get_chat_by_id(mapping[0])
        return None

    def get_relay_group(self, outside_id: int) -> deltachat.Chat:
        """Get the corresponding relay group for the ID of the outside chat.

        :param outside_id: the chat.id of the outside chat
        :return: the relay group
        """
        relay_mappings = self.kvstore.get("relays")
        for mapping in relay_mappings:
            if mapping[0] == outside_id:
                return self.account.get_chat_by_id(mapping[1])
        return None
