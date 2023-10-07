from teams_bot.commands import get_crew_id


def test_get_crew_id(crew):
    """Test if crew is properly found in delta chat database."""
    assert crew.id == get_crew_id(crew.bot)


def test_disable_old_crew(crew, outsider):
    """Test if crew is properly disabled if someone else creates a new crew on the command line."""
    old_crew_id = get_crew_id(crew.bot)

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
