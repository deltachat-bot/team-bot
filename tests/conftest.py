import logging
import os

import pytest
from deltachat_rpc_client._utils import AttrDict
from deltachat_rpc_client.events import EventType

from team_bot.relay import relayhooks
from team_bot.setup import setuphooks


@pytest.fixture
def bot(acfactory, log):
    assert os.getenv("CHATMAIL_DOMAIN")
    log.step("Configuring Bot")
    bot = acfactory.new_configured_bot()
    bot.account.set_config("displayname", "Bot from TEST team")
    bot.add_hooks(setuphooks)
    bot.logger = logging.getLogger("root")

    def process_events(bot, until: EventType) -> AttrDict:
        while True:
            event = bot.account.wait_for_event()
            if event.get("msg"):
                print(event.get("msg"))
            event["kind"] = EventType(event.kind)
            event["account"] = bot.account
            bot._on_event(event)
            if event.kind == EventType.INCOMING_MSG:
                bot._process_messages()
                return bot.account.get_message_by_id(event.msg_id).get_snapshot()
            if until == event.kind:
                return event

    bot.process_events = process_events
    bot.account.start_io()
    bot.process_events(bot, EventType.IMAP_INBOX_IDLE)
    return bot


@pytest.fixture
def crew_member(log, acfactory):
    log.step("Configuring Crew member")
    crew_member = acfactory.get_online_account()
    crew_member.set_config("displayname", "Crew member from TEST team")
    return crew_member


@pytest.fixture
def crew(crew_member, bot, log, caplog):
    # caplog.set_level(logging.DEBUG, logger="root")
    log.step("Crew member joins crew")
    bot_invite = bot.account.get_qr_code()
    crew_member.secure_join(bot_invite)

    bot.process_events(bot, EventType.SECUREJOIN_INVITER_PROGRESS)

    log.step("Bot changes hooks")
    for hook, event in setuphooks:
        bot.remove_hook(hook, event)
    bot.add_hooks(relayhooks)

    for chat in crew_member.get_chatlist(snapshot=True):
        if chat.chat_type == "Group":
            return chat


@pytest.fixture
def outsider(acfactory, log):
    log.step("Configuring Joiner")
    outsider = acfactory.get_online_account()
    outsider.set_config("displayname", "Outsider for TEST team")
    return outsider
