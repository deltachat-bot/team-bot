import os

import pytest
from deltachat_rpc_client.events import EventType

from team_bot.relay import relayhooks
from team_bot.setup import setuphooks


@pytest.fixture
def bot(acfactory, log, caplog):
    assert os.getenv("CHATMAIL_DOMAIN")
    log.step("Configuring Bot")
    bot = acfactory.new_configured_bot()
    bot.account.set_config("displayname", "Bot from TEST team")
    bot.add_hooks(setuphooks)
    bot.account.start_io()
    bot._process_events(until_event=EventType.IMAP_INBOX_IDLE)
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

    bot._process_events(until_event=EventType.SECUREJOIN_INVITER_PROGRESS)

    log.step("Bot changes hooks")
    for hook, event in setuphooks:
        bot.remove_hook(hook, event)
    bot.add_hooks(relayhooks)

    crew_member.wait_for_incoming_msg()
    for chat in crew_member.get_chatlist(snapshot=True):
        if chat.chat_type == "Group":
            return chat


@pytest.fixture
def outsider(acfactory, log):
    log.step("Configuring Joiner")
    outsider = acfactory.get_online_account()
    outsider.set_config("displayname", "Outsider for TEST team")
    return outsider


def join_chat(user, invite, log):
    user.secure_join(invite)
    user.wait_for_securejoin_joiner_success()
    log.step("Joiner receives member_added message")
    [print(chat.get_full_snapshot().name) for chat in user.get_chatlist()]
    return user.get_chatlist()[0]


@pytest.fixture
def relay_group(crew, bot, outsider, crew_member, log):
    log.step("send message to bot")
    bot_invite = bot.account.get_qr_code()
    outsider_outside_chat = join_chat(outsider, bot_invite, log)
    outsider_outside_chat.send_text("test 1:1 message to bot")

    log.step("bot creates relay group")
    bot._process_events(until_event=EventType.INCOMING_MSG)

    log.step("get relay group")
    group_explanation_message = crew_member.wait_for_incoming_msg().get_snapshot()
    assert "This is a chat with Outsider for TEST team" in group_explanation_message.text
    user_forwarded_message_from_outsider = crew_member.wait_for_incoming_msg().get_snapshot()
    assert user_forwarded_message_from_outsider.text == "test 1:1 message to bot"
    return user_forwarded_message_from_outsider.chat
