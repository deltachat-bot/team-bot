import os.path
import time

import deltachat
import pytest
from deltachat.capi import lib as dclib


TIMEOUT = 40


def get_user_crew(crewuser: deltachat.Account, id=11) -> deltachat.Chat:
    """Get the Team chat from the team member's point of view.

    :param crewuser: the account object of the team member
    :return: the chat object of the team chat
    """
    for chat in crewuser.get_chats():
        print(chat.id, chat.get_name())
    user_crew = crewuser.get_chat_by_id(id)
    assert user_crew.get_name().startswith("Team")
    return user_crew


@pytest.mark.timeout(TIMEOUT)
def test_not_relay_groups(relaycrew, outsider, lp):
    bot = relaycrew.bot
    user = relaycrew.user

    def find_msg(ac, text):
        for chat in ac.get_chats():
            for msg in chat.get_messages():
                if msg.text == text:
                    return msg

    text = "outsider -> bot 1:1 chat"
    lp.sec(text)
    outsider_botcontact = outsider.create_contact(bot.get_config("addr"))
    outsider_outside_chat = outsider.create_chat(outsider_botcontact)
    outsider_outside_chat.send_text(text)
    lp.sec("receiving message from outsider in 1:1 chat")
    bot_message_from_outsider = bot._evtracker.wait_next_incoming_message()
    bot_outside_chat = bot_message_from_outsider.chat
    assert bot_message_from_outsider.text == text
    assert not bot.relayplugin.is_relay_group(bot_outside_chat)

    lp.sec("leave relay group with user")
    relayed_msg = find_msg(user, text)
    if not relayed_msg:
        relayed_msg = user._evtracker.wait_next_incoming_message()
    relayed_msg.chat.remove_contact(user.get_config("addr"))
    leave_msg = bot._evtracker.wait_next_incoming_message()
    assert bot.relayplugin.is_relay_group(leave_msg.chat)

    text = "outsider -> bot group chat"
    lp.sec(text)
    outsider_bot_group = outsider.create_group_chat(
        "test with outsider", contacts=[outsider_botcontact]
    )
    outsider_bot_group.send_text(text)
    lp.sec("receiving message from outsider in group chat")
    bot_message_from_outsider = bot._evtracker.wait_next_incoming_message()
    assert bot_message_from_outsider.text == text
    assert not bot.relayplugin.is_relay_group(bot_message_from_outsider.chat)

    text = "user -> bot 1:1 chat"
    lp.sec(text)
    user_botcontact = user.create_contact(bot.get_config("addr"))
    user_to_bot = user.create_chat(user_botcontact)
    user_to_bot.send_text(text)
    lp.sec("receiving message from user in 1:1 chat")

    # somehow the message doesn't trigger DC_EVENT_INCOMING_MSG
    # bot._evtracker.wait_next_incoming_message()
    bot_message_from_user = find_msg(bot, text)
    while not bot_message_from_user:
        bot_message_from_user = find_msg(bot, text)
        time.sleep(1)
    assert bot_message_from_user.text == text
    assert not bot.relayplugin.is_relay_group(bot_message_from_user.chat)

    text = "user -> bot group chat"
    lp.sec(text)
    user_group = user.create_group_chat("test with user", contacts=[user_botcontact])
    user_group.send_text(text)
    lp.sec("receiving message from user in group chat")
    bot_message_from_user = bot._evtracker.wait_next_incoming_message()
    assert bot_message_from_user.text == text
    assert not bot.relayplugin.is_relay_group(bot_message_from_user.chat)


@pytest.mark.timeout(TIMEOUT)
def test_relay_group_forwarding(relaycrew, outsider):
    bot = relaycrew.bot
    user = relaycrew.user

    # create outside chat
    outsider_botcontact = outsider.create_contact(bot.get_config("addr"))
    outsider_outside_chat = outsider.create_chat(outsider_botcontact)
    outsider_outside_chat.send_text("test 1:1 message to bot")

    # get outside chat
    message_from_outsider = bot._evtracker.wait_next_incoming_message()
    bot_outside_chat = message_from_outsider.chat
    assert not bot.relayplugin.is_relay_group(bot_outside_chat)
    assert message_from_outsider.is_in_fresh()

    # get relay group
    user_forwarded_message_from_outsider = user._evtracker.wait_next_incoming_message()
    user_relay_group = user_forwarded_message_from_outsider.create_chat()
    user_relay_group.send_text(
        "Chatter in relay group"
    )  # send normal reply, not forwarded
    bot_chatter_in_relay_group = bot._evtracker.wait_next_incoming_message()
    bot_relay_group = bot_chatter_in_relay_group.chat

    # check if relay group has relay group properties
    assert bot_relay_group.get_name().startswith(
        "[%s] " % (bot.get_config("addr").split("@")[0],)
    )
    assert (
        bot_relay_group.get_messages()[0].get_sender_contact() == bot.get_self_contact()
    )
    assert not bot_relay_group.is_protected()
    assert relaycrew.get_contacts() == bot_relay_group.get_contacts()
    assert bot.relayplugin.is_relay_group(bot_relay_group)

    # send direct reply, should be forwarded
    user_direct_reply = deltachat.Message.new_empty(user, view_type="text")
    user_direct_reply.set_text("This should be forwarded to the outsider")
    user_direct_reply.quote = user_forwarded_message_from_outsider
    sent_id = dclib.dc_send_msg(
        user._dc_context, user_relay_group.id, user_direct_reply._dc_msg
    )
    assert sent_id == user_direct_reply.id
    assert message_from_outsider.is_in_seen()

    # check that direct reply was forwarded to outsider
    outsider_direct_reply = outsider._evtracker.wait_next_incoming_message()
    assert outsider_direct_reply.text == "This should be forwarded to the outsider"
    assert outsider_direct_reply.chat == outsider_outside_chat
    assert outsider_direct_reply.get_sender_contact() == outsider_botcontact

    # check that normal reply was not forwarded to outsider
    assert bot_chatter_in_relay_group.text not in [
        msg.text for msg in bot_outside_chat.get_messages()
    ]

    # reply with outsider
    outsider_outside_chat.send_text("Second message by outsider")

    # check that outsider's reply ends up in the same chat
    user_second_message_from_outsider = user._evtracker.wait_next_incoming_message()
    assert user_second_message_from_outsider.chat == user_relay_group

    # check that relay group explanation is not forwarded to outsider
    for chat in outsider.get_chats():
        for msg in chat.get_messages():
            assert "This is the relay group for" not in msg.text


@pytest.mark.timeout(TIMEOUT)
def test_offboarding(team_bot, relaycrew, outsider, team_user):
    # outsider sends message, creates relay group
    outsider_botcontact = outsider.create_contact(team_bot.get_config("addr"))
    outsider_outside_chat = outsider.create_chat(outsider_botcontact)
    outsider_outside_chat.send_text("test 1:1 message to bot")

    # get relay group
    user_relay_group = team_user._evtracker.wait_next_incoming_message().chat
    bot_relay_group = team_bot.get_chats()[-1]

    # outsider gets added to crew
    qr = relaycrew.get_join_qr()
    outsider.qr_join_chat(qr)
    outsider._evtracker.wait_securejoin_joiner_progress(1000)

    # user kicks outsider from crew
    user_crew = get_user_crew(team_user)
    user_crew.remove_contact(team_user.create_contact(outsider))
    team_bot._evtracker.wait_next_incoming_message()

    # user leaves crew
    user_crew.remove_contact(team_user)
    # make sure they are also offboarded from relay group
    team_bot._evtracker.wait_next_incoming_message()
    team_user._evtracker.wait_next_incoming_message()
    team_user._evtracker.wait_next_incoming_message()
    team_user._evtracker.wait_next_incoming_message()
    for contact in bot_relay_group.get_contacts():
        assert team_user.get_config("addr") != contact.addr

    # make sure there is no message in relay group that outsider was kicked
    for msg in user_relay_group.get_messages():
        print(msg.text)
        assert outsider.get_config("addr") + " removed by " not in msg.text


@pytest.mark.timeout(TIMEOUT)
def test_default_outside_help(relaycrew, outsider):
    bot = relaycrew.bot
    user = relaycrew.user

    # create outside chat
    outsider_botcontact = outsider.create_contact(bot.get_config("addr"))
    outsider_outside_chat = outsider.create_chat(outsider_botcontact)
    outsider_outside_chat.send_text("/help")

    # get response
    outside_help_message = outsider._evtracker.wait_next_incoming_message()
    assert "I forward messages to the " in outside_help_message.text

    # assert no relay group was created
    assert len(bot.get_chats()) == 2
    assert len(user.get_chats()) == 1


@pytest.mark.timeout(TIMEOUT)
def test_empty_outside_help(relaycrew, outsider):
    bot = relaycrew.bot
    user = relaycrew.user

    # set outside_help_message empty
    for chat in user.get_chats():
        print(chat.id, chat.get_name())
    user_crew = user.get_chat_by_id(11)
    assert user_crew.get_name().startswith("Team")
    user_crew.send_text("/set_outside_help")
    # ensure /set_outside_help arrives before sending /help
    bot._evtracker.wait_next_incoming_message()

    # create outside chat
    outsider_botcontact = outsider.create_contact(bot.get_config("addr"))
    outsider_outside_chat = outsider.create_chat(outsider_botcontact)
    outsider_outside_chat.send_text("/help")

    # get forwarded /help message
    user._evtracker.wait_next_incoming_message()  # "Removed help message for outsiders"
    user._evtracker.wait_next_incoming_message()  # explanation message
    user_forwarded_message_from_outsider = user._evtracker.wait_next_incoming_message()
    assert user_forwarded_message_from_outsider.text == "/help"


@pytest.mark.timeout(TIMEOUT)
def test_changed_outside_help(relaycrew, outsider):
    bot = relaycrew.bot
    user = relaycrew.user

    # set outside_help_message empty
    for chat in user.get_chats():
        print(chat.id, chat.get_name())
    user_crew = user.get_chat_by_id(11)
    assert user_crew.get_name().startswith("Team")
    outside_help_text = "Hi friend :) send me messages to chat with the team"
    user_crew.send_text("/set_outside_help " + outside_help_text)
    # ensure /set_outside_help arrives before sending /help
    bot._evtracker.wait_next_incoming_message()

    # create outside chat
    outsider_botcontact = outsider.create_contact(bot.get_config("addr"))
    outsider_outside_chat = outsider.create_chat(outsider_botcontact)
    outsider_outside_chat.send_text("/help")

    # get response
    outside_help_message = outsider._evtracker.wait_next_incoming_message()
    assert outside_help_message.text == outside_help_text

    # assert no relay group was created
    assert len(bot.get_chats()) == 2
    assert len(user.get_chats()) == 1


@pytest.mark.timeout(TIMEOUT)
def test_change_avatar(relaycrew):
    bot = relaycrew.bot
    user = relaycrew.user

    for contact in user.get_contacts():
        if contact.addr == bot.get_config("addr"):
            assert not contact.get_profile_image()
            botcontact = contact
            break
    else:
        pytest.fail("bot contact not found")

    example_png_path = "/usr/share/pixmaps/debian-logo.png"
    if not os.path.exists(example_png_path):
        pytest.skip(f"example image not available: {example_png_path}")

    # set avatar to example image
    user_crew = get_user_crew(user)
    msg = deltachat.Message.new_empty(user, "image")
    msg.set_text("/set_avatar")
    msg.set_file(example_png_path)
    sent_id = dclib.dc_send_msg(user._dc_context, user_crew.id, msg._dc_msg)
    assert sent_id == msg.id

    group_avatar_changed_msg = user._evtracker.wait_next_incoming_message()
    assert "Group image changed" in group_avatar_changed_msg.text
    assert user_crew.get_profile_image()

    confirmation_msg = user._evtracker.wait_next_incoming_message()
    assert confirmation_msg.text == "Avatar changed to this image."
    assert botcontact.get_profile_image()


@pytest.mark.timeout(TIMEOUT * 2)
def test_forward_sending_errors_to_relay_group(relaycrew):
    usercrew = relaycrew.user.get_chats()[-1]
    usercrew.send_text("/start_chat alice@example.org This_Message_will_fail test")

    while len(relaycrew.bot.get_chats()) < 3:
        time.sleep(0.1)
    out_chat = relaycrew.bot.get_chats()[-1]
    outgoing_message = out_chat.get_messages()[-1]
    print(outgoing_message)
    begin = int(time.time())
    while not outgoing_message.is_out_failed() and int(time.time()) < begin + TIMEOUT:
        time.sleep(0.1)
    assert outgoing_message.is_out_failed()

    while len(relaycrew.user.get_chats()) < 2 and int(time.time()) < begin + TIMEOUT:
        time.sleep(0.1)
    for chat in relaycrew.user.get_chats():
        if "This Message will fail" in chat.get_name():
            relay_group = chat

    while len(relay_group.get_messages()) < 3 and int(time.time()) < begin + TIMEOUT:
        print(relay_group.get_messages()[-1].text)
        time.sleep(0.1)
    assert (
        "Recipient address rejected: Domain example.org does not accept mail"
        not in relay_group.get_messages()[-1].text
    )
    assert (
        "Invalid unencrypted mail to <alice@example.org>"
        in relay_group.get_messages()[-1].text
    )


@pytest.mark.timeout(TIMEOUT)
def test_public_invite(relaycrew, outsider):
    crew = get_user_crew(relaycrew.user)
    crew.send_text("/generate-invite")
    result = relaycrew.user._evtracker.wait_next_incoming_message()
    # assert result.filename
    # assert result.text.startswith("https://i.delta.chat")

    # qr = result.filename
    # invite = "OPENPGP4FPR:" + result.text[22::]
    chat = outsider.qr_setup_contact(result.text)
    outsider._evtracker.wait_securejoin_joiner_progress(1000)

    while not chat.is_protected():
        print(chat.get_messages()[-1].text)
        time.sleep(1)
