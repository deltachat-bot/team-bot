import logging
import os
import time

import pytest
from deltachat_rpc_client.events import EventType
from deltachat_rpc_client._utils import AttrDict

from team_bot.relay import relayhooks
from team_bot.setup import setuphooks
from team_bot.util import get_crew_id_from_account


@pytest.fixture
def bot(acfactory, log):
    assert os.getenv("CHATMAIL_DOMAIN")
    log.step("Configuring Bot")
    bot = acfactory.new_configured_bot()
    bot.account.set_config("displayname", "Bot from TEST team")
    bot.add_hooks(setuphooks)
    bot.logger = logging.getLogger("root")
    bot.account.bring_online()
    event = AttrDict()
    event["kind"] = EventType.IMAP_CONNECTED
    event["account"] = bot.account
    bot._on_event(event)
    return bot


@pytest.fixture
def crew_member(log, acfactory):
    log.step("Configuring Crew member")
    crew_member = acfactory.get_online_account()
    crew_member.set_config("displayname", "Crew member from TEST team")
    return crew_member


@pytest.fixture
def crew(crew_member, bot, log, caplog):
    #caplog.set_level(logging.DEBUG, logger="root")
    log.step("Crew member joins crew")
    bot_invite = bot.account.get_qr_code()
    bot_contact = crew_member.secure_join(bot_invite)

    event = bot.account.wait_for_event(event_type=EventType.SECUREJOIN_INVITER_PROGRESS)
    event["kind"] = EventType.SECUREJOIN_INVITER_PROGRESS
    event["account"] = bot.account
    bot._on_event(event)
    while not get_crew_id_from_account(bot.account):
        time.sleep(0.1)

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
