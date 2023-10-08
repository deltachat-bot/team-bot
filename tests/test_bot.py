from teams_bot.commands import get_crew_id


def test_is_relay_group(relaycrew, outsider):
    botcontact_outsider = outsider.create_contact(relaycrew.bot.get_config("addr"))
    outsider_to_bot = outsider.create_chat(botcontact_outsider)
    outsider_to_bot.send_text("test message to bot")
    message_from_outsider = relaycrew.bot.wait_next_incoming_message()
    assert not relaycrew.bot.relayplugin.is_relay_group(message_from_outsider.chat)

    relaycrew.user.wait_next_incoming_message()  # group added message
    forwarded_message_from_outsider = relaycrew.user.wait_next_incoming_message()
    user_relay_group = forwarded_message_from_outsider.create_chat()
    user_relay_group.send_text("Harmless reply in relay group")
    message_in_relay_group = relaycrew.bot.wait_next_incoming_message()
    assert message_in_relay_group.chat.get_name().startswith(
        "[%s] " % (relaycrew.bot.get_config("addr").split("@")[0],)
    )
    assert (
        message_in_relay_group.chat.get_messages()[0].get_sender_contact()
        == relaycrew.bot.get_self_contact()
    )
    assert not message_in_relay_group.chat.is_protected()
    assert (
        relaycrew.bot.get_chat_by_id(get_crew_id(relaycrew.bot)).get_contacts()
        == message_in_relay_group.chat.get_contacts()
    )
    assert relaycrew.bot.relayplugin.is_relay_group(message_in_relay_group.chat)

    outsider_to_bot = outsider.create_group_chat(
        "test with outsider", contacts=[botcontact_outsider]
    )
    outsider_to_bot.send_text("test message to outsider group")
    message_from_outsider = relaycrew.bot.wait_next_incoming_message()
    assert not relaycrew.bot.relayplugin.is_relay_group(message_from_outsider.chat)

    botcontact_user = relaycrew.user.create_contact(relaycrew.bot.get_config("addr"))
    user_to_bot = relaycrew.user.create_chat(botcontact_user)
    user_to_bot.send_text("test message to bot")
    message_from_user = relaycrew.bot.wait_next_incoming_message()
    assert not relaycrew.bot.relayplugin.is_relay_group(message_from_user.chat)

    user_group = relaycrew.user.create_group_chat(
        "test with user", contacts=[botcontact_user]
    )
    user_group.send_text("testing message to user group")
    message_from_user = relaycrew.bot.wait_next_incoming_message()
    assert not relaycrew.bot.relayplugin.is_relay_group(message_from_user.chat)
