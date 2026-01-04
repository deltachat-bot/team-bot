import logging
import qrcode
import os

from deltachat_rpc_client import events, EventType

from .util import get_crew_id, get_crew_invite

log = logging.getLogger("root")
setuphooks = events.HookCollection()


@setuphooks.on(events.RawEvent)
def catch_events(event):
    """This is called on every raw event and can be used for any kind of event handling.
    Unfortunately deltachat-rpc-client doesn't offer high-level events for MSG_DELIVERED or SECUREJOIN_INVITER_PROGRESS
    yet, so this needs to be done with raw events.

    :param event: the event object
    """
    log.debug(event)

    if event.kind == EventType.IMAP_CONNECTED:
        crew_id = get_crew_id(event)

        event.account.set_config("bcc_self", "1")

        if not crew_id:
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
