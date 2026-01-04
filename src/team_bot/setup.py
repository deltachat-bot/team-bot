import os

from deltachat_rpc_client import events, EventType

from .util import get_crew_id, get_crew_invite

setuphooks = events.HookCollection()


@setuphooks.on(events.RawEvent)
def catch_events(event):
    """This is called on every raw event and can be used for any kind of event handling.
    Unfortunately deltachat-rpc-client doesn't offer high-level events for MSG_DELIVERED or SECUREJOIN_INVITER_PROGRESS
    yet, so this needs to be done with raw events.

    :param event: the event object
    """
    if os.getenv("DEBUG") == "true":
        print(event)

    if event.kind == EventType.IMAP_CONNECTED:
        crew_id = get_crew_id(event)

        event.account.set_config("bcc_self", "1")

        if not crew_id:
            user_invite = os.getenv("TEAMS_USER_INVITE")
            if user_invite:
                user_chat = event.account.secure_join(user_invite)
            else:
                try:
                    assert event.account.crew_invite
                except AttributeError:
                    print(f"JOIN THE TEAM WITH THIS INVITE LINK: {get_crew_invite(event.account)}")


    if event.kind == EventType.SECUREJOIN_INVITER_PROGRESS:
        if event.progress == 1000:
            # :todo if invite was a user_invite, add the inviter to the crew
            bot_addr = event.account.get_config("addr")
            crew = event.account.create_group(f"Team: {bot_addr}")
            user_contact = event.account.get_contact_by_id(event.contact_id)
            crew.add_contact(user_contact)
            welcome_msg = crew.send_text("Welcome to the team! Type /help to see the existing commands.")
            welcome_msg.wait_until_delivered()
            event.account.set_config("ui.crew_id", str(crew.id))
