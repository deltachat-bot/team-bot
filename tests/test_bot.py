import deltachat
from deltachat.capi import lib as dclib

from teams_bot.commands import get_crew_id


def test_not_relay_groups(relaycrew, outsider):
    bot = relaycrew.bot
    user = relaycrew.user

    # bot <-> outsider 1:1 chat
    outsider_botcontact = outsider.create_contact(bot.get_config("addr"))
    outsider_outside_chat = outsider.create_chat(outsider_botcontact)
    outsider_outside_chat.send_text("test 1:1 message to bot")

    bot_message_from_outsider = bot.wait_next_incoming_message()
    bot_outside_chat = bot_message_from_outsider.chat
    assert not bot.relayplugin.is_relay_group(bot_outside_chat)

    # bot <-> outsider group chat
    outsider_bot_group = outsider.create_group_chat(
        "test with outsider", contacts=[outsider_botcontact]
    )
    outsider_bot_group.send_text("test message to outsider group")
    bot_message_from_outsider = bot.wait_next_incoming_message()
    assert not bot.relayplugin.is_relay_group(bot_message_from_outsider.chat)

    # bot <-> user 1:1 chat
    user_botcontact = user.create_contact(bot.get_config("addr"))
    user_to_bot = user.create_chat(user_botcontact)
    user_to_bot.send_text("test message to bot")
    bot_message_from_user = bot.wait_next_incoming_message()
    assert not bot.relayplugin.is_relay_group(bot_message_from_user.chat)

    # bot <-> user group chat
    user_group = user.create_group_chat("test with user", contacts=[user_botcontact])
    user_group.send_text("testing message to user group")
    bot_message_from_user = bot.wait_next_incoming_message()
    assert not bot.relayplugin.is_relay_group(bot_message_from_user.chat)


def test_relay_group_forwarding(relaycrew, outsider):
    bot = relaycrew.bot
    user = relaycrew.user

    # create outside chat
    outsider_botcontact = outsider.create_contact(bot.get_config("addr"))
    outsider_outside_chat = outsider.create_chat(outsider_botcontact)
    outsider_outside_chat.send_text("test 1:1 message to bot")

    # get outside chat
    message_from_outsider = bot.wait_next_incoming_message()
    bot_outside_chat = message_from_outsider.chat
    assert not bot.relayplugin.is_relay_group(bot_outside_chat)

    # get relay group
    user.wait_next_incoming_message()  # group added message
    user_forwarded_message_from_outsider = user.wait_next_incoming_message()
    user_relay_group = user_forwarded_message_from_outsider.create_chat()
    user_relay_group.send_text(
        "Chatter in relay group"
    )  # send normal reply, not forwarded
    bot_chatter_in_relay_group = bot.wait_next_incoming_message()
    bot_relay_group = bot_chatter_in_relay_group.chat

    # check if relay group has relay group properties
    assert bot_relay_group.get_name().startswith(
        "[%s] " % (bot.get_config("addr").split("@")[0],)
    )
    assert (
        bot_relay_group.get_messages()[0].get_sender_contact() == bot.get_self_contact()
    )
    assert not bot_relay_group.is_protected()
    assert (
        bot.get_chat_by_id(get_crew_id(bot)).get_contacts()
        == bot_relay_group.get_contacts()
    )
    assert bot.relayplugin.is_relay_group(bot_relay_group)

    # send direct reply, should be forwarded
    user_direct_reply = deltachat.Message.new_empty(user, view_type="text")
    user_direct_reply.set_text("This should be forwarded to the outsider")
    user_direct_reply.quote = user_forwarded_message_from_outsider
    sent_id = dclib.dc_send_msg(
        user._dc_context, user_relay_group.id, user_direct_reply._dc_msg
    )
    assert sent_id == user_direct_reply.id

    # check that direct reply was forwarded to outsider
    outsider_direct_reply = outsider.wait_next_incoming_message()
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
    user_second_message_from_outsider = user.wait_next_incoming_message()
    assert user_second_message_from_outsider.chat == user_relay_group
