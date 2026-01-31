import os.path

import pytest
from deltachat_rpc_client import EventType
from deltachat_rpc_client.const import MessageState

from team_bot.util import get_crew_id_from_account, get_relay_groups, is_relay_group, parse_new_command_args

TIMEOUT = 40
INDEFINITELY = lambda _: False
ALICE_VCARD = """BEGIN:VCARD
VERSION:4.0
EMAIL:alice@example.org
FN:test
KEY:data:application/pgp-keys;base64,xjMEaAVqNxYJKwYBBAHaRw8BAQdAnQ1KcTZYpcfbGyXkgPHJsCJQn/mn2a4F5SH7tccFNF/NHDxhcDNtNWNzNjNAbmluZS50ZXN0cnVuLm9yZz7CjQQQFggANQIZAQUCaAVqNwIbAwQLCQgHBhUICQoLAgMWAgEBJxYhBJCKqRpWzC6rZWWG76Wa27/U0TWBAAoJEKWa27/U0TWBKV8A/RoUFaB7YYc0zLkZWkJr9xTy5jN8T3VsGNJRi2IN1wQTAQDAsLwZkTf4pax2Hu/S0P11e+hsK+7TqF8/YP/toT5zAc44BGgFajcSCisGAQQBl1UBBQEBB0Dw5cbj6CDXHYKJDHvqfCPE1oDcO0194OYjXPf3foYTGAMBCAfCeAQYFggAIAUCaAVqNwIbDBYhBJCKqRpWzC6rZWWG76Wa27/U0TWBAAoJEKWa27/U0TWB2c8BAON7SIbWGpzhCoLP/pKsVycxdH3lc4bAAKwLP2X/cnFyAQCO43AeusNcRYetQJfvtmI9avQkEKWw54QBfFWIiabpDg==
REV:20250420T214624Z
END:VCARD
"""


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
def test_relay_outside_1on1_chats(crew, bot, crew_member, outsider, log):
    log.step("send message to bot")
    bot_invite = bot.account.get_qr_code()
    outsider_outside_chat = join_chat(outsider, bot_invite, log)
    outsider_botcontact = outsider_outside_chat.get_contacts()[0]
    outsider_outside_chat.send_text("test 1:1 message to bot")

    log.step("get outside chat")
    ev = bot._process_events(INDEFINITELY, until_event=EventType.INCOMING_MSG)
    group_msg_from_outsider = bot.account.get_message_by_id(ev.msg_id).get_snapshot()
    bot_outside_chat = group_msg_from_outsider.chat
    assert not is_relay_group(bot_outside_chat)
    assert group_msg_from_outsider.state == MessageState.IN_SEEN

    log.step("get relay group")
    user_forwarded_message_from_outsider = crew_member.wait_for_incoming_msg().get_snapshot()
    user_relay_group = user_forwarded_message_from_outsider.chat
    user_relay_group.send_text("Chatter in relay group")  # send normal reply, not forwarded
    bot_chatter_in_relay_group = bot.account.wait_for_incoming_msg().get_snapshot()
    bot_relay_group = bot_chatter_in_relay_group.chat

    log.step("check if relay group has relay group properties")
    assert bot_relay_group.get_full_snapshot().name.startswith(
        "[%s] " % (bot.account.get_config("addr").split("@")[0],)
    )
    assert bot_relay_group.get_messages()[0].get_snapshot().text == "Messages are end-to-end encrypted."
    assert bot_relay_group.get_messages()[1].get_snapshot().sender == bot.account.self_contact
    crew_members = set(c.get_snapshot().address for c in crew.chat.get_contacts())
    relay_group_members = set(c.get_snapshot().address for c in bot_relay_group.get_contacts())
    assert crew_members == relay_group_members
    assert is_relay_group(bot_relay_group)

    log.step("send direct reply, should be forwarded")
    outside_group_reply = user_relay_group.send_message(
        text="This should be forwarded to the outsider", quoted_msg=user_forwarded_message_from_outsider.message
    )
    bot._process_events(INDEFINITELY, until_event=EventType.INCOMING_MSG)

    log.step("check that direct reply was forwarded to outsider")
    outsider_direct_reply = outsider.wait_for_incoming_msg().get_snapshot()
    assert outsider_direct_reply.text == "This should be forwarded to the outsider"
    assert outsider_direct_reply.chat == outsider_outside_chat
    assert outsider_direct_reply.sender == outsider_botcontact

    log.step("react to user's reply to indicate the message was forwarded")
    bot._process_events(INDEFINITELY, until_event=EventType.MSG_DELIVERED)
    crew_member.wait_for_reactions_changed()
    assert outside_group_reply.get_snapshot().reactions.reactions[0].emoji == "✅"

    log.step("check that normal reply was not forwarded to outsider")
    assert bot_chatter_in_relay_group.text not in [msg.get_snapshot().text for msg in bot_outside_chat.get_messages()]
    assert not bot_chatter_in_relay_group.reactions

    log.step("reply with outsider")
    outsider_outside_chat.send_text("Second message by outsider")
    log.step("forward with bot")
    bot._process_events(INDEFINITELY, until_event=EventType.INCOMING_MSG)

    log.step("check that outsider's reply ends up in the same chat")
    user_second_message_from_outsider = crew_member.wait_for_incoming_msg().get_snapshot()
    assert user_second_message_from_outsider.chat == user_relay_group

    log.step("check that relay group explanation is not forwarded to outsider")
    for chat in outsider.get_chatlist():
        for msg in chat.get_messages():
            assert "This is the relay group for" not in msg.get_snapshot().text


@pytest.mark.timeout(TIMEOUT)
def test_relay_outside_group(crew, bot, crew_member, outsider, log):
    log.step("send message to bot")
    bot_invite = bot.account.get_qr_code()
    outsider_outside_chat = join_chat(outsider, bot_invite, log)
    outsider_botcontact = outsider_outside_chat.get_contacts()[0]

    log.step("test relaying out of and into groups")
    group_title = "Fancy group"
    outsider_outside_group = outsider.create_group(group_title)
    outsider_outside_group.add_contact(outsider_botcontact)
    outsider_outside_group.send_text("Group message by outsider")
    log.step("receive group message with bot, create relay group")
    ev = bot._process_events(INDEFINITELY, until_event=EventType.INCOMING_MSG)
    group_msg_from_outsider = bot.account.get_message_by_id(ev.msg_id).get_snapshot()
    bot_outside_chat = group_msg_from_outsider.chat
    assert not is_relay_group(bot_outside_chat)

    log.step("receive group message in relay group")
    user_forwarded_message_from_outsider = crew_member.wait_for_incoming_msg().get_snapshot()
    user_relay_group = user_forwarded_message_from_outsider.chat
    log.step("check if relay group has relay group properties")
    assert user_relay_group.get_full_snapshot().name.startswith(
        "[%s] %s" % (bot.account.get_config("addr").split("@")[0], group_title)
    )
    assert user_relay_group.get_messages()[0].get_snapshot().text == "Messages are end-to-end encrypted."
    crew_members = set(c.get_snapshot().address for c in crew.chat.get_contacts())
    relay_group_members = set(c.get_snapshot().address for c in user_relay_group.get_contacts())
    assert crew_members == relay_group_members

    log.step("send direct reply, should be forwarded")
    outside_group_reply = user_relay_group.send_message(
        text="This should be forwarded to the outsider", quoted_msg=user_forwarded_message_from_outsider.message
    )
    bot._process_events(INDEFINITELY, until_event=EventType.INCOMING_MSG)

    log.step("react to indicate successful forward to group")
    bot._process_events(INDEFINITELY, until_event=EventType.MSG_DELIVERED)
    crew_member.wait_for_reactions_changed()
    assert outside_group_reply.get_snapshot().reactions.reactions[0].emoji == "✅"

    log.step("check that direct reply was forwarded to outsider")
    outsider_direct_reply = outsider.wait_for_incoming_msg().get_snapshot()
    assert outsider_direct_reply.text == "This should be forwarded to the outsider"
    assert outsider_direct_reply.chat == outsider_outside_group
    assert outsider_direct_reply.sender == outsider_botcontact

    log.step("Send failing message to the outside")
    alice_contact = bot.account.import_vcard(ALICE_VCARD)[0]
    group_msg_from_outsider.chat.add_contact(alice_contact)
    bot._process_events(INDEFINITELY, until_event=EventType.MSG_FAILED)
    failing_reply = user_relay_group.send_message(
        text="This message will fail to be forwarded", quoted_msg=user_forwarded_message_from_outsider.message
    )
    bot._process_events(INDEFINITELY, until_event=EventType.INCOMING_MSG)

    log.step("react to user's reply to indicate forwarding the message failed")
    bot._process_events(INDEFINITELY, until_event=EventType.MSG_FAILED)
    error_msg = crew_member.wait_for_incoming_msg().get_snapshot()
    assert "Delivery failed" in error_msg.text
    crew_member.wait_for_reactions_changed()
    assert failing_reply.get_snapshot().reactions.reactions[0].emoji == "❌"


@pytest.mark.timeout(TIMEOUT)
def test_offboarding(crew, bot, crew_member, outsider, log):
    outsider_name = outsider.get_config("displayname")
    log.step("outsider sends message to team-bot")
    bot_invite = bot.account.get_qr_code()
    outsider_outside_chat = join_chat(outsider, bot_invite, log)
    orig_text = "test 1:1 message to bot"
    outsider_outside_chat.send_text(orig_text)
    log.step("bot creates relay group")
    bot._process_events(INDEFINITELY, until_event=EventType.INCOMING_MSG)
    log.step("user gets added to relay group")
    user_relay_group = crew_member.wait_for_incoming_msg().get_snapshot().chat
    assert crew_member.wait_for_incoming_msg().get_snapshot().text == orig_text
    bot_relay_group = bot.account.get_chat_by_id(get_relay_groups(bot.account)[0][1])
    assert is_relay_group(bot_relay_group)

    log.step("user adds outsider to crew")
    qr = crew.chat.get_qr_code()
    outsider.secure_join(qr)
    outsider.wait_for_securejoin_joiner_success()
    assert "Member Outsider for TEST team added" in bot.account.wait_for_incoming_msg().get_snapshot().text

    log.step("user kicks outsider from crew")
    crew.chat.remove_contact(crew_member.create_contact(outsider))
    outsider_removed = bot._process_events(INDEFINITELY, until_event=EventType.INCOMING_MSG)
    assert f"{outsider_name} removed by" in bot.account.get_message_by_id(outsider_removed.msg_id).get_snapshot().text

    log.step("user leaves crew")
    crew.chat.remove_contact(crew_member)
    log.step("user gets offboarded from relay group")
    user_leaves = bot._process_events(INDEFINITELY, until_event=EventType.CHAT_MODIFIED)
    assert user_leaves.chat_id == get_crew_id_from_account(bot.account)
    bot._process_messages()
    for contact in bot_relay_group.get_contacts():
        assert crew_member.get_config("addr") != contact.get_snapshot().address

    log.step("user receives removal notice")
    assert "Member Me removed by Bot" in crew_member.wait_for_incoming_msg().get_snapshot().text

    log.step("make sure there is no message in relay group that outsider was kicked")
    for msg in user_relay_group.get_messages():
        print(msg.get_snapshot().text)
        assert outsider.get_config("displayname") + " removed by " not in msg.get_snapshot().text

    log.step("make sure there is no message in outside chat that user was kicked")
    for msg in outsider_outside_chat.get_messages():
        print(msg.get_snapshot().text)
        assert crew_member.get_config("displayname") + " removed by " not in msg.get_snapshot().text


@pytest.mark.timeout(TIMEOUT)
def test_default_outside_help(crew, bot, crew_member, outsider, log):
    log.step("create outside chat")
    bot_invite = bot.account.get_qr_code()
    outsider_outside_chat = join_chat(outsider, bot_invite, log)
    outsider_outside_chat.send_text("/help")

    log.step("get response")
    bot._process_events(INDEFINITELY, until_event=EventType.INCOMING_MSG)
    outside_help_message = outsider.wait_for_incoming_msg().get_snapshot()
    assert "I forward messages to the " in outside_help_message.text

    log.step("assert no relay group was created")
    assert len(bot.account.get_chatlist()) == 3
    assert len(crew_member.get_chatlist()) == 4


@pytest.mark.timeout(TIMEOUT)
def test_empty_outside_help(crew, bot, crew_member, outsider, log):
    log.step("set outside_help_message empty")
    assert crew.chat.get_basic_snapshot().name.startswith("Team")
    crew.chat.send_text("/set_outside_help")

    log.step("ensure /set_outside_help arrives before sending /help")
    bot._process_events(INDEFINITELY, until_event=EventType.INCOMING_MSG)

    log.step("create outside chat")
    bot_invite = bot.account.get_qr_code()
    outsider_outside_chat = join_chat(outsider, bot_invite, log)
    outsider_outside_chat.send_text("/help")

    log.step("Bot receives /help")
    bot._process_events(INDEFINITELY, until_event=EventType.INCOMING_MSG)

    log.step("get forwarded /help message")
    crew_member.wait_for_incoming_msg()  # "Removed help message for outsiders"
    crew_member.wait_for_incoming_msg()  # explanation message
    user_forwarded_message_from_outsider = crew_member.wait_for_incoming_msg().get_snapshot()
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
    bot._process_events(INDEFINITELY, until_event=EventType.INCOMING_MSG)

    log.step("create outside chat")
    bot_invite = bot.account.get_qr_code()
    outsider_outside_chat = join_chat(outsider, bot_invite, log)
    outsider_outside_chat.send_text("/help")

    log.step("Bot processes /help")
    bot._process_events(INDEFINITELY, until_event=EventType.INCOMING_MSG)

    log.step("get response")
    outside_help_message = outsider.wait_for_incoming_msg().get_snapshot()
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
def test_new_message_errors(crew, bot, crew_member, log, tmpdir):
    log.step("Send /new_message command")
    rec = "alice@example.org"
    new_message_command = f"/new_message {rec} This_Message_will_fail test"
    first_command = crew.chat.send_text(new_message_command)

    log.step("Let bot receive and process it")
    bot._process_events(INDEFINITELY, until_event=EventType.INCOMING_MSG)
    assert new_message_command in [msg.get_snapshot().text for msg in bot.account.get_chatlist()[0].get_messages()]

    log.step("User receives error message")
    error_msg = crew_member.wait_for_incoming_msg().get_snapshot()
    assert error_msg.text == f"failed to create contacts for {rec}: no encryption available, use /add_contact first"

    log.step("User sends /add_contact")
    vcf_file = tmpdir / "alice.vcf"
    with open(vcf_file, "w") as f:
        f.write(ALICE_VCARD)
    crew.chat.send_message(text="/add_contact", file=str(vcf_file))
    log.step("Bot process /add_contact command")
    bot._process_events(INDEFINITELY, until_event=EventType.INCOMING_MSG)
    log.step("User receives confirmation")
    bot_reply = crew_member.wait_for_incoming_msg().get_snapshot()
    assert bot_reply.text == "Contact imported. You can now write them with: /new_message alice@example.org"

    log.step("Try /new_message command again")
    second_command = crew.chat.send_text(new_message_command)
    log.step("Let bot receive and process it")
    command_event = bot._process_events(INDEFINITELY, until_event=EventType.INCOMING_MSG)
    bot_command = bot.account.get_message_by_id(command_event.msg_id).get_snapshot()
    assert bot_command.text == new_message_command

    log.step("User receives confirmation")
    relay_group_init = crew_member.wait_for_incoming_msg().get_snapshot()
    assert relay_group_init.text == "We sent a message to test (alice@example.org).\n\nThis was our first message:"
    own_msg = crew_member.wait_for_incoming_msg().get_snapshot()
    assert own_msg.text == "This Message will fail test"
    log.step("Bot receives MSG_FAILED")
    success_msg = crew_member.wait_for_incoming_msg().get_snapshot()
    assert "Message successfully sent" in success_msg.text
    bot._process_events(INDEFINITELY, until_event=EventType.MSG_FAILED)
    log.step("User receives failure notice")
    error_msg = crew_member.wait_for_incoming_msg().get_snapshot()
    assert "Delivery failed" in error_msg.text
    assert error_msg.chat == second_command.get_snapshot().chat
    crew_member.wait_for_reactions_changed()
    assert second_command.get_reactions().reactions[0].emoji == "❌"
    assert not first_command.get_reactions()


@pytest.mark.timeout(TIMEOUT)
def test_new_message_success(crew, bot, crew_member, log, tmpdir, outsider):
    log.step("User adds outsider contact")
    outsider_invite = outsider.get_qr_code()
    user_outsider_chat = join_chat(crew_member, outsider_invite, log)
    user_outsider_contact = user_outsider_chat.get_contacts()[0]
    assert outsider.get_config("addr") == user_outsider_contact.get_snapshot().address
    outsider_vcard = crew_member.make_vcard([user_outsider_contact])
    vcf_file = tmpdir / "outsider.vcf"
    with open(vcf_file, "w") as f:
        f.write(outsider_vcard)
    crew.chat.send_message(text="/add_contact", file=str(vcf_file))
    log.step("Bot process /add_contact command")
    bot._process_events(INDEFINITELY, until_event=EventType.INCOMING_MSG)
    assert len(bot.account.get_contacts()) > 1
    for contact in bot.account.get_contacts():
        if contact.get_snapshot().address == user_outsider_contact.get_snapshot().address:
            if contact.get_snapshot().e2ee_avail:
                bot_outsidercontact = contact
    assert bot_outsidercontact
    log.step("User receives confirmation")
    bot_reply = crew_member.wait_for_incoming_msg().get_snapshot()
    assert "Contact imported. You can now write them with: /new_message " in bot_reply.text

    log.step("User sends /new_message command")
    new_message_command = f"/new_message {user_outsider_contact.get_snapshot().address} This_should_work test"
    crew.chat.send_text(new_message_command)
    log.step("Let bot receive and process it")
    command_event = bot._process_events(INDEFINITELY, until_event=EventType.INCOMING_MSG)
    bot_command = bot.account.get_message_by_id(command_event.msg_id).get_snapshot()
    assert bot_command.text == new_message_command

    outsider_new_msg = outsider.wait_for_incoming_msg().get_snapshot()
    recipients, title, text = parse_new_command_args(new_message_command)
    assert outsider_new_msg.text == f"{title} {text}"


@pytest.mark.timeout(TIMEOUT)
def test_public_invite(crew, bot, crew_member, outsider):
    crew.chat.send_text("/generate-invite")
    bot._process_events(INDEFINITELY, until_event=EventType.INCOMING_MSG)
    result = crew_member.wait_for_incoming_msg().get_snapshot()
    assert result.text.startswith("https://i.delta.chat")

    outsider.secure_join(result.text)
    outsider.wait_for_securejoin_joiner_success()
