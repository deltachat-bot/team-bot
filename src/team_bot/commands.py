import json
import logging
import os

import pickledb
from deltachat_rpc_client import Account, Chat, DeltaChat, Message, Rpc
from deltachat_rpc_client._utils import AttrDict
from deltachat_rpc_client.rpc import JsonRpcError

from .forwarding import forward_to_relay_group
from .util import get_outside_chat, get_prefix, get_relay_groups, parse_new_command_args, set_relay_groups

log = logging.getLogger("root")


def migrate_from_cffi(accounts_dir: str, **kwargs):
    """Migrate the data from an old pickle DB to the new account's config sqlite table."""
    migration_dir = os.path.normpath(accounts_dir) + ".migrating"
    log.warning(f"Storing debug in {migration_dir} intermittently...")

    with Rpc(accounts_dir=migration_dir, **kwargs) as rpc:
        deltachat = DeltaChat(rpc)
        deltachat.add_account()

        old_db_files = [f.name for f in os.scandir(accounts_dir) if "delta.sqlite" in f.name]
        db_subdir = [f.path for f in os.scandir(migration_dir) if f.is_dir()][0]

        for file in old_db_files:
            new_filename = file.replace("delta.sqlite", "dc.db")
            os.rename(os.path.join(accounts_dir, file), os.path.join(db_subdir, new_filename))

    pickle_path = os.path.join(accounts_dir, "pickle.db")
    kvstore = pickledb.load(pickle_path, True)
    log.warning(f"Migrating data from {pickle_path} to {db_subdir}/dc.db's config table:")
    with Rpc(accounts_dir=migration_dir, **kwargs) as rpc:
        deltachat = DeltaChat(rpc)
        accounts = deltachat.get_all_accounts()
        account = accounts[0] if accounts else deltachat.add_account()

        crew_id = kvstore.get("crew_id")
        log.warning(f"Migrating crew_id: {crew_id}")
        account.set_config("ui.crew_id", str(crew_id))

        relays = kvstore.get("relays")
        log.warning(f"Migrating relays: {json.dumps(relays)}")
        set_relay_groups(account, relays)

        outside_help_message = kvstore.get("outside_help_message")
        if isinstance(outside_help_message, str):
            log.warning(f"Migrating outside_help_message: {outside_help_message}")
            set_outside_help(account, outside_help_message)

    log.warning(f"Data migrated, removing {pickle_path}...")
    os.remove(pickle_path)
    os.rename(migration_dir, accounts_dir)
    log.warning("Migration to new data format successful.")


def crew_help() -> str:
    """Get the help message for the crew chat

    :return: the help message
    """
    help_text = """
Start a chat:\t/new_message alice@example.org,bob@example.org Chat_Title Hello friends!
Add a contact:\t\t\t/add_contact <attach contact>
Change the bot's name:\t/set_name Name
Change the bot's avatar:\t/set_avatar <attach image>
Generate invite link:\t\t/generate_invite
Set relay group prefix:\t\t/set_prefix [example]
Show this help text:\t\t/help
Change the help message for outsiders:\t/set_outside_help Hello outsider
    """
    return help_text


def relay_group_help():
    """Get the help message for relay groups"""
    help_text = """
Ignore future messages:\t/mute
Get messages again:\t\t/unmute
Show this help text:\t\t/help
    """
    return help_text


def outside_help(account: Account) -> str:
    """Get the help message for outsiders"""
    return account.get_config("ui.outside_help_message")


def set_outside_help(account: Account, help_message: str):
    """Set the help message for outsiders"""
    logging.info("Setting outside_help_message to %s", help_message)
    account.set_config("ui.outside_help_message", help_message)


def mute_relay_group(relay_group: Chat) -> bool:
    """Mute the outside chat of a relay group, so future messages from the outside will not be forwarded.

    :return: whether the command made a difference
    """
    outside_chat = get_outside_chat(relay_group)
    if not outside_chat.get_basic_snapshot().is_muted:
        outside_chat.mute()
        return True
    else:
        return False


def unmute_relay_group(relay_group: Chat) -> bool:
    """Unmute the outside chat of this relay group again.

    :return: whether the command made a difference
    """
    outside_chat = get_outside_chat(relay_group)
    if outside_chat.get_basic_snapshot().is_muted:
        outside_chat.unmute()
        return True
    else:
        return False


def resend_missed_messages(relay_group: Chat):
    """Forward messages to the relay group which were not forwarded yet."""
    existing_relay_group_messages = [msg.get_snapshot().text for msg in relay_group.get_messages()]
    for msg in get_outside_chat(relay_group).get_messages():
        if msg.get_snapshot().text not in existing_relay_group_messages:
            forward_to_relay_group(msg.get_snapshot())


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


def set_prefix(account: Account, arguments: [str]) -> str:
    """Set the prefix for relay groups.

    :param account: the account object of the bot
    :param arguments: the arguments of the original command
    :return: a success/failure message
    """
    old_prefix = get_prefix(account)
    arguments.pop(0)
    new_prefix = " ".join(arguments)
    account.set_config("ui.prefix", new_prefix)
    changed_titles = 0
    for _, relay_group_id in get_relay_groups(account):
        relay_group = account.get_chat_by_id(relay_group_id)
        if get_outside_chat(relay_group).get_basic_snapshot().is_muted:
            continue
        old_title = relay_group.get_basic_snapshot().name
        if old_title.startswith(old_prefix):
            new_title = new_prefix + " " + old_title[len(old_prefix) :].strip()
        else:
            log.warning(f"Setting prefix: {old_title} does not start with {old_prefix}")
            new_title = new_prefix + " " + old_title.strip()
        relay_group.set_name(new_title.strip())
        changed_titles += 1
    if new_prefix:
        changed_prefix = f"Set prefix to {new_prefix}"
    else:
        changed_prefix = "Removed prefix"
    ending = "s" if changed_titles > 1 else ""
    return f"{changed_prefix}, changed {changed_titles} relay group name{ending}."


def start_chat(
    ac: Account,
    command: AttrDict,
) -> (Message, str):
    """Start a chat with one or more outsiders.

    :param ac: the account object of the bot
    :param command: the message with the command
    :return: the sent message and a success/failure message
    """
    recipients, title, text = parse_new_command_args(command.text)

    contacts = []
    contact_ids = []
    failed_contacts = []
    encryption = "encrypted"
    for rec in recipients:
        contact = ac.get_contact_by_addr(rec)
        if not contact:
            log.error(f"Couldn't find valid PGP contact for {rec}")
            if ac.get_config("is_chatmail") == "1":
                failed_contacts.append(f"{rec}: no encryption available, use /add_contact first")
                continue
            try:
                contact = ac.create_contact(rec)
            except JsonRpcError as e:
                failed_contacts.append(f"{rec}: {e.args[0].get('message')}")
                continue
        contacts.append(contact)
        contact_ids.append(str(contact.id))
        if not contact.get_snapshot().is_key_contact:
            encryption = "unencrypted"
    if failed_contacts:
        return None, "failed to create contacts for " + ", ".join(failed_contacts)
    log.info(f"Sending {encryption} message to {', '.join(contact_ids)} with subject {title}: {text}")

    if encryption == "unencrypted":
        chat = Chat(ac, ac._rpc.create_group_chat_unencrypted(ac.id, title))
        for contact in contacts:
            contact_to_add = contact
            if contact.get_encryption_info() != "No encryption":
                contact_to_add = ac.create_contact(contact.get_snapshot().address)
            chat.add_contact(contact_to_add)
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
    message = chat.send_message(text=text, viewtype=view_type, file=attachment)
    return message, "Message successfully sent."


def add_contact(account: Account, command: AttrDict) -> str:
    """Import a contact from an attached vCard, to allow sending an encrypted message.

    :param account: the bot's account object
    :param command: the AttrDict of the message which called this function
    """
    with open(command.file, "r") as f:
        contacts = account.import_vcard(f.read())
    possible_recipients = ",".join([c.get_snapshot().address for c in contacts])
    return "Contact imported. You can now write them with: /new_message " + possible_recipients


def offboard(msg: AttrDict, displayname: str) -> None:
    """Remove a former crew member from all relay groups they are part of.

    :param msg: the AttrDict of the message causing the member removal.
    :param displayname: the display name of a contact which just got removed from the crew.
    """
    account = msg.chat.account
    ex_member = None
    for contact in [account.get_contact_by_id(past_id) for past_id in msg.chat.get_full_snapshot().past_contact_ids]:
        if contact.get_snapshot().display_name.lower() == displayname:
            ex_member = contact
    if not ex_member:
        log.error(f"Could not find contact for {displayname} in past crew members")

    else:
        for mapping in get_relay_groups(account):
            relay_group = account.get_chat_by_id(mapping[1])
            if ex_member in relay_group.get_contacts():
                log.info(f"{relay_group.get_full_snapshot().name}: removing {ex_member.get_snapshot().display_name}")
                relay_group.remove_contact(ex_member)
        return
