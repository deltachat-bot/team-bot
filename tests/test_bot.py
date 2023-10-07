from teams_bot.bot import get_crew_id, RelayPlugin


def test_get_crew_id(crew):
    """Test if crew is properly found in delta chat database."""
    assert crew.id == get_crew_id(crew.bot)


def test_disable_old_crew(crew, outsider):
    """Test if crew is properly disabled if someone else creates a new crew on the command line."""
    old_crew_id = get_crew_id(crew.bot)

    # wait until old user is properly added to crew
    last_message = crew.user.wait_next_incoming_message().text
    while (
        f"Member Me ({crew.user.get_config('addr')}) added by bot" not in last_message
    ):
        print("User received message:", last_message)
        last_message = crew.user.wait_next_incoming_message().text

    # outsider fires up the command line and creates a new crew
    new_crew = crew.bot.create_group_chat(
        f"Team: {crew.bot.get_config('addr')}", verified=True
    )
    assert new_crew.id != old_crew_id
    qr = new_crew.get_join_qr()

    # prepare setupplugin for waiting on second group join
    crew.bot.setupplugin.member_added.clear()
    crew.bot.setupplugin.crew_id = new_crew.id

    # outsider joins new crew
    outsider.qr_join_chat(qr)
    crew.bot.setupplugin.member_added.wait(timeout=30)
    assert len(new_crew.get_contacts()) == 2
    assert new_crew.get_name() == f"Team: {crew.bot.get_config('addr')}"
    assert new_crew.is_protected()
    assert new_crew.id == get_crew_id(crew.bot, crew.bot.setupplugin)

    # old user receives disable warning
    crew.user.wait_next_incoming_message()
    quit_message = crew.user.wait_next_incoming_message()
    assert "There is a new Group for the Team now" in quit_message.text
    assert outsider.get_config("addr") in quit_message.text


def test_is_relay_group(crew, outsider):
    crew.bot.relayplugin = RelayPlugin(crew.bot)
    assert not crew.bot.relayplugin.is_relay_group(crew)

    botcontact_outsider = outsider.create_contact(crew.bot.get_config("addr"))
    outsider_to_bot = outsider.create_chat(botcontact_outsider)
    outsider_to_bot.send_text("test message to bot")
    message_from_outsider = crew.bot.wait_next_incoming_message()
    assert not crew.bot.relayplugin.is_relay_group(message_from_outsider.chat)

    outsider_to_bot = outsider.create_group_chat(
        "test with outsider", contacts=[botcontact_outsider]
    )
    outsider_to_bot.send_text("test message to outsider group")
    message_from_outsider = crew.bot.wait_next_incoming_message()
    assert not crew.bot.relayplugin.is_relay_group(message_from_outsider.chat)

    botcontact_user = crew.user.create_contact(crew.bot.get_config("addr"))
    user_to_bot = crew.user.create_chat(botcontact_user)
    user_to_bot.send_text("test message to bot")
    message_from_user = crew.bot.wait_next_incoming_message()
    assert not crew.bot.relayplugin.is_relay_group(message_from_user.chat)

    user_group = crew.user.create_group_chat(
        "test with user", contacts=[botcontact_user]
    )
    user_group.send_text("testing message to user group")
    message_from_user = crew.bot.wait_next_incoming_message()
    assert not crew.bot.relayplugin.is_relay_group(message_from_user.chat)

    # get example from actual relay group as soon as it works
