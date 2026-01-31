import os.path
import time

import pytest
from deltachat_rpc_client import EventType
from deltachat_rpc_client.const import MessageState

from team_bot.util import is_relay_group

TIMEOUT = 40
INDEFINITELY = lambda _: False


def join_chat(user, invite, log):
    user.secure_join(invite)
    user.wait_for_securejoin_joiner_success()
    log.step("Joiner receives member_added message")
    [print(chat.get_full_snapshot().name) for chat in user.get_chatlist()]
    return user.get_chatlist()[0]


@pytest.mark.timeout(TIMEOUT)
def test_not_relay_groups(crew, bot, crew_member, outsider, log):
    def find_msg(ac, text):
        for chat in ac.get_chatlist():
            for msg in chat.get_messages():
                if text in msg.get_snapshot().text:
                    return msg.get_snapshot()
                else:
                    print(msg.get_snapshot().text)

    text = "outsider -> bot 1:1 chat"
    log.step(text)
    bot_invite = bot.account.get_qr_code()
    outsider_outside_chat = join_chat(outsider, bot_invite, log)
    outsider_botcontact = outsider_outside_chat.get_contacts()[0]
    outsider_outside_chat.send_text(text)
    log.step("receiving message from outsider in 1:1 chat")
    message_event = bot._process_events(INDEFINITELY, until_event=EventType.INCOMING_MSG)
    bot_message_from_outsider = bot.account.get_message_by_id(message_event.msg_id).get_snapshot()
    log.step("reveiced message from outsider in 1:1 chat")
    bot_outside_chat = bot_message_from_outsider.chat
    assert bot_message_from_outsider.text == text
    assert bot_outside_chat
    assert not is_relay_group(bot_outside_chat)

    log.step("leave relay group with crew member")
    relayed_msg = crew_member.wait_for_incoming_msg().get_snapshot()
    relayed_msg.chat.remove_contact(crew_member.self_contact)
    log.step("bot receives leave message")
    leave_event = bot._process_events(INDEFINITELY, until_event=EventType.CHAT_MODIFIED)
    bot_relay_group = bot.account.get_chat_by_id(leave_event.chat_id)
    assert is_relay_group(bot_relay_group)

    text = "outsider -> bot group chat"
    log.step(text)
    outsider_bot_group = outsider.create_group("test with outsider")
    outsider_bot_group.add_contact(outsider_botcontact)
    outsider_bot_group.send_text(text)
    log.step("receiving message from outsider in group chat")
    bot_message_from_outsider = bot.account.wait_for_incoming_msg().get_snapshot()
    assert bot_message_from_outsider.text == text
    assert not is_relay_group(bot_message_from_outsider.chat)

    text = "user -> bot 1:1 chat"
    log.step(text)
    user_botcontact = crew_member.create_contact(bot.account)
    user_to_bot = user_botcontact.create_chat()
    assert user_to_bot.get_full_snapshot().chat_type == "Single"
    user_to_bot.send_text(text)
    log.step("receiving message from user in 1:1 chat")

    message_event = bot._process_events(INDEFINITELY, until_event=EventType.INCOMING_MSG)
    bot_message_from_user = bot.account.get_message_by_id(message_event.msg_id).get_snapshot()
    assert bot_message_from_user.text == text
    assert not is_relay_group(bot_message_from_user.chat)

    text = "user -> bot group chat"
    log.step(text)
    user_group = crew_member.create_group("test with user")
    user_group.add_contact(user_botcontact)
    user_group.send_text(text)
    log.step("receiving message from user in group chat")
    bot_message_from_user = bot.account.wait_for_incoming_msg().get_snapshot()
    assert bot_message_from_user.text == text
    assert not is_relay_group(bot_message_from_user.chat)


@pytest.mark.timeout(TIMEOUT)
def test_relay_group_forwarding(crew, bot, crew_member, outsider, log):
    log.step("create outside chat")
    bot_invite = bot.account.get_qr_code()
    outsider_outside_chat = join_chat(outsider, bot_invite, log)
    outsider_botcontact = outsider_outside_chat.get_contacts()[0]
    outsider_outside_chat.send_text("test 1:1 message to bot")

    log.step("get outside chat")
    ev = bot._process_events(INDEFINITELY, until_event=EventType.INCOMING_MSG)
    message_from_outsider = bot.account.get_message_by_id(ev.msg_id).get_snapshot()
    bot_outside_chat = message_from_outsider.chat
    assert not is_relay_group(bot_outside_chat)
    assert message_from_outsider.state == MessageState.IN_FRESH

    log.step("get relay group")
    user_forwarded_message_from_outsider = crew_member.wait_for_incoming_msg()
    user_relay_group = user_forwarded_message_from_outsider.create_chat()
    user_relay_group.send_text("Chatter in relay group")  # send normal reply, not forwarded
    bot_chatter_in_relay_group = bot.account.wait_for_incoming_msg().get_snapshot()
    bot_relay_group = bot_chatter_in_relay_group.chat

    log.step("check if relay group has relay group properties")
    assert bot_relay_group.get_full_snapshot().name.startswith(
        "[%s] " % (bot.account.get_config("addr").split("@")[0],)
    )
    assert bot_relay_group.get_messages()[0].sender == bot.account.self_contact
    assert crew.chat.get_contacts() == bot_relay_group.get_contacts()
    assert is_relay_group(bot_relay_group)

    log.step("send direct reply, should be forwarded")
    user_relay_group.send_msg(
        text="This should be forwarded to the outsider", quote=user_forwarded_message_from_outsider
    )
    bot._process_events(INDEFINITELY, until_event=EventType.INCOMING_MSG)
    assert message_from_outsider.state == MessageState.IN_SEEN

    log.step("check that direct reply was forwarded to outsider")
    outsider_direct_reply = outsider.wait_for_incoming_msg().get_snapshot()
    assert outsider_direct_reply.text == "This should be forwarded to the outsider"
    assert outsider_direct_reply.chat == outsider_outside_chat
    assert outsider_direct_reply.sender == outsider_botcontact

    log.step("check that normal reply was not forwarded to outsider")
    assert bot_chatter_in_relay_group.text not in [msg.get_snapshot().text for msg in bot_outside_chat.get_messages()]

    log.step("reply with outsider")
    outsider_outside_chat.send_text("Second message by outsider")

    log.step("check that outsider's reply ends up in the same chat")
    user_second_message_from_outsider = crew_member.wait_for_incoming_msg().get_snapshot()
    assert user_second_message_from_outsider.chat == user_relay_group

    log.step("check that relay group explanation is not forwarded to outsider")
    for chat in outsider.get_chatlist():
        for msg in chat.get_messages():
            assert "This is the relay group for" not in msg.get_snapshot().text


@pytest.mark.timeout(TIMEOUT)
def test_offboarding(crew, bot, crew_member, outsider, log):
    log.step("outsider sends message, creates relay group")
    bot_invite = bot.account.get_qr_code()
    outsider_outside_chat = join_chat(outsider, bot_invite, log)
    outsider_outside_chat.send_text("test 1:1 message to bot")

    log.step("get relay group")
    bot._process_events(INDEFINITELY, until_event=EventType.INCOMING_MSG)
    user_relay_group = crew_member.wait_for_incoming_msg().get_snapshot().chat
    bot_relay_group = bot.account.get_chatlist()[-1]

    log.step("outsider gets added to crew")
    qr = crew.chat.get_qr_code()
    outsider.secure_join(qr)
    outsider.wait_for_securejoin_joiner_success()

    log.step("user kicks outsider from crew")
    crew.remove_contact(crew_member.create_contact(outsider))
    bot._process_events(INDEFINITELY, until_event=EventType.INCOMING_MSG)

    log.step("user leaves crew")
    crew.remove_contact(crew_member)
    log.step("make sure they are also offboarded from relay group")
    bot.account.wait_for_incoming_msg()
    crew_member.wait_for_incoming_msg()
    crew_member.wait_for_incoming_msg()
    crew_member.wait_for_incoming_msg()
    for contact in bot_relay_group.get_contacts():
        assert crew_member.get_config("addr") != contact.get_snapshot().address

    log.step("make sure there is no message in relay group that outsider was kicked")
    for msg in user_relay_group.get_messages():
        print(msg.text)
        assert outsider.get_config("addr") + " removed by " not in msg.text


@pytest.mark.timeout(TIMEOUT)
def test_default_outside_help(crew, bot, crew_member, outsider, log):
    log.step("create outside chat")
    bot_invite = bot.account.get_qr_code()
    outsider_outside_chat = join_chat(outsider, bot_invite, log)
    outsider_outside_chat.send_text("/help")

    log.step("get response")
    bot._process_events(INDEFINITELY, until_event=EventType.INCOMING_MSG)
    outside_help_message = outsider.wait_for_incoming_msg()
    assert "I forward messages to the " in outside_help_message.get_snapshot().text

    log.step("assert no relay group was created")
    assert len(bot.account.get_chatlist()) == 3
    assert len(crew_member.get_chatlist()) == 4


@pytest.mark.timeout(TIMEOUT)
def test_empty_outside_help(crew, bot, crew_member, outsider, log):
    log.step("set outside_help_message empty")
    assert crew.chat.get_basic_snapshot().name.startswith("Team")
    crew.chat.send_text("/set_outside_help")

    log.step("ensure /set_outside_help arrives before sending /help")
    bot.account.wait_for_incoming_msg()

    log.step("create outside chat")
    outsider_botcontact = outsider.create_contact(bot.account.get_config("addr"))
    outsider_outside_chat = outsider.create_chat(outsider_botcontact)
    outsider_outside_chat.send_text("/help")

    log.step("Bot receives /help")
    bot._process_events(INDEFINITELY, until_event=EventType.INCOMING_MSG)

    log.step("get forwarded /help message")
    crew_member.wait_for_incoming_msg()  # "Removed help message for outsiders"
    crew_member.wait_for_incoming_msg()  # explanation message
    user_forwarded_message_from_outsider = crew_member.wait_for_incoming_msg()
    assert user_forwarded_message_from_outsider.text == "/help"


@pytest.mark.timeout(TIMEOUT)
def test_changed_outside_help(crew, bot, crew_member, outsider, log):
    log.step("set outside_help_message empty")
    for chat in crew_member.get_chatlist():
        print(chat.id, chat.get_basic_snapshot().name)
    assert crew.chat.get_basic_snapshot().name.startswith("Team")
    outside_help_text = "Hi friend :) send me messages to chat with the team"
    crew.chat.send_text("/set_outside_help " + outside_help_text)
    log.step("ensure /set_outside_help arrives before sending /help")
    bot.account.wait_for_incoming_msg()

    log.step("create outside chat")
    outsider_botcontact = outsider.create_contact(bot.account.get_config("addr"))
    outsider_outside_chat = outsider.create_chat(outsider_botcontact)
    outsider_outside_chat.send_text("/help")

    log.step("Bot processes /help")
    bot._process_events(INDEFINITELY, until_event=EventType.INCOMING_MSG)

    log.step("get response")
    outside_help_message = outsider.wait_for_incoming_msg()
    assert outside_help_message.text == outside_help_text

    log.step("assert no relay group was created")
    assert len(bot.account.get_chatlist()) == 3
    assert len(crew_member.get_chatlist()) == 4


@pytest.mark.timeout(TIMEOUT)
def test_change_avatar(crew, bot, crew_member, log):
    for contact in crew_member.get_contacts():
        if contact.get_snapshot().address == bot.account.get_config("addr"):
            botcontact = contact
            assert not botcontact.get_snapshot().profile_image
            break
    else:
        pytest.fail("bot contact not found")

    example_png_path = "/usr/share/pixmaps/debian-logo.png"
    if not os.path.exists(example_png_path):
        pytest.skip(f"example image not available: {example_png_path}")

    log.step("set avatar to example image")
    crew.chat.send_message(text="/set_avatar", file=example_png_path)
    bot._process_events(INDEFINITELY, until_event=EventType.INCOMING_MSG)
    group_avatar_changed_msg = crew_member.wait_for_incoming_msg().get_snapshot()
    assert "Group image changed" in group_avatar_changed_msg.text
    assert crew.chat.get_full_snapshot().profile_image

    confirmation_msg = crew_member.wait_for_incoming_msg().get_snapshot()
    assert confirmation_msg.text == "Avatar changed to this image."
    assert botcontact.get_snapshot().profile_image


@pytest.mark.timeout(TIMEOUT)
def test_new_message_error(crew, bot, crew_member, log):
    log.step("Send /new_message command")
    rec = "alice@example.org"
    command = f"/new_message {rec} This_Message_will_fail test"
    crew.chat.send_text(command)

    log.step("Let bot receive and process it")
    bot._process_events(INDEFINITELY, until_event=EventType.INCOMING_MSG)
    assert command in [msg.get_snapshot().text for msg in bot.account.get_chatlist()[0].get_messages()]

    log.step("User receives error message")
    error_msg = crew_member.wait_for_incoming_msg().get_snapshot()
    assert error_msg.text == f"failed to create contacts for {rec}: no encryption available, use /add_contact first"
    # XXX test /add_contact fails as well


@pytest.mark.timeout(TIMEOUT)
def test_public_invite(crew, bot, crew_member, outsider):
    crew.chat.send_text("/generate-invite")
    bot._process_events(INDEFINITELY, until_event=EventType.INCOMING_MSG)
    result = crew_member.wait_for_incoming_msg().get_snapshot()
    assert result.text.startswith("https://i.delta.chat")

    outsider.secure_join(result.text)
    outsider.wait_for_securejoin_joiner_success()
