import json
import logging
import os
import random
import string
from typing import Optional

import qrcode
from deltachat_rpc_client import Account, EventType, events

from .util import get_crew_invite, has_crew

log = logging.getLogger("root")
setuphooks = events.HookCollection()
setuphooks.__name__ = "Setup hooks"
ALPHANUMERIC = string.ascii_lowercase + string.digits


@setuphooks.on(events.RawEvent)
def catch_events(event):
    """This is called on every raw event and can be used for any kind of event handling.
    Unfortunately deltachat-rpc-client doesn't offer high-level events for MSG_DELIVERED or SECUREJOIN_INVITER_PROGRESS
    yet, so this needs to be done with raw events.

    :param event: the event object
    """
    log.debug(event)

    if event.kind == EventType.IMAP_CONNECTED:
        event.account.set_config("bcc_self", "1")

        if not has_crew(event):
            user_invite = os.getenv("TEAMS_USER_INVITE")
            if user_invite:
                try:
                    log.debug(f"User invite already used: {event.account.user_invite}")
                except AttributeError:
                    log.info(f"Using user-specified invite link: {user_invite}")
                    event.account.secure_join(user_invite)
                    event.account.user_invite = user_invite
            else:
                try:
                    log.debug(f"Crew invite already created: {event.account.crew_invite}")
                except AttributeError:
                    invite_link = get_crew_invite(event.account)
                    qr = qrcode.QRCode()
                    qr.add_data(invite_link)
                    print("\nPlease scan this qr code with Delta Chat to verify the bot:\n\n")
                    qr.print_ascii(invert=True)
                    print(f"\nOr click this invite link: {invite_link}")

        if not event.account.get_config("ui.relay_groups"):
            empty_list_json = json.dumps([])
            event.account.set_config("ui.relay_groups", empty_list_json)
            log.info("Initialized empty list of relay groups")

    if event.kind == EventType.SECUREJOIN_INVITER_PROGRESS or event.kind == EventType.SECUREJOIN_JOINER_PROGRESS:
        if event.progress == 1000:
            bot_addr = event.account.get_config("addr")
            crew = event.account.create_group(f"Team: {bot_addr}")
            user_contact = event.account.get_contact_by_id(event.contact_id)
            crew.add_contact(user_contact)
            welcome_msg = crew.send_text("Welcome to the team! Type /help to see the existing commands.")
            welcome_msg.wait_until_delivered()
            event.account.set_config("ui.crew_id", str(crew.id))
            log.debug(f"Saved crew ID: {crew.id}")


def configure_email(email: Optional[str], prev_email: Optional[str]) -> (bool, str):
    """Configure an account with given email and password, generate if necessary.

    :param email: the email as passed by the CLI
    :param prev_email: the email as configured already
    :return: whether to reconfigure the account, and the email address to configure it with
    """
    reconfigure = False
    if not prev_email:
        log.debug("Setting email address...")
        reconfigure = True
        if not email:
            email = "".join(random.choices(ALPHANUMERIC, k=9)) + "@nine.testrun.org"
            log.warning(f"No email specified, creating new chatmail address: {email}")
    elif email and prev_email != email:
        log.info("Changing email address as specified...")
        reconfigure = True
    else:
        email = prev_email
        log.debug("Email address already set, no changes necessary")
    return reconfigure, email


def configure_password(password: Optional[str], prev_pass: Optional[str]) -> (bool, str, str):
    """Configure an account with given email and password, generate if necessary.

    :param password: the password as passed by the CLI
    :param prev_pass: the password as configured already
    :return: whether to reconfigure the account, and the password to configure it with
    """
    reconfigure = False
    if not prev_pass:
        log.debug("Setting email password...")
        reconfigure = True
        if not password:
            password = "".join(random.choices(ALPHANUMERIC, k=20))
            log.warning("No email password specified, trying with random password")
    elif password and prev_pass != password:
        log.info("Changing email password as specified...")
        reconfigure = True
    else:
        password = prev_pass
        log.debug("Email password already set, no changes necessary")
    return reconfigure, password


def configure_proxy(proxy_url: Optional[str], account: Account) -> bool:
    """Configure a proxy for a given account

    :param proxy_url: the URL for the proxy
    :param account: the Delta Chat account object
    :return: whether to reconfigure the account
    """
    prev_enabled = True if account.get_config("proxy_enabled") == "1" else False
    prev_proxy = account.get_config("proxy_url")
    reconfigure = False
    if proxy_url:
        account.set_config("proxy_url", proxy_url)
        account.set_config("proxy_enabled", "1")
        if not prev_enabled or proxy_url != prev_proxy:
            reconfigure = True
    else:
        account.set_config("proxy_enabled", "0")
        if prev_enabled:
            reconfigure = True
    return reconfigure
