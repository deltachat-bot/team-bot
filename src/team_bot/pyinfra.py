import importlib.resources
from io import StringIO

from pyinfra.operations import files, git, server, systemd


def deploy_team_bot(
    unix_user: str,
    bot_email: str = None,
    bot_passwd: str = None,
    dbdir: str = None,
    user_invite: str = None,
    branch="main",
):
    """Deploy TeamsBot to a UNIX user, with specified credentials

    :param unix_user: the existing UNIX user of the bot
    :param bot_email: the email address for the bot account. If left out, it will be a random nine.testrun.org address
    :param bot_passwd: the password for the bot's email account. Only needed if bot_email is specified
    :param dbdir: the directory where the bot's data will be stored. default: ~/.config/team-bot/email@example.org
    :param user_invite: the invite link of the first crew member
    :param branch: which branch of https://github.com/deltachat-bot/team-bot to use
    """

    git.config(
        key="rebase.autoStash",
        value="true",
    )
    clone_repo = git.repo(
        name="Pull the team-bot repository",
        src="https://github.com/deltachat-bot/team-bot",
        dest=f"/home/{unix_user}/team-bot",
        branch=branch,
        rebase=True,
        _su_user=unix_user,
        _use_su_login=True,
    )

    if clone_repo.changed:
        server.shell(
            name="Compile team-bot",
            commands=[
                "python3 -m venv ~/.local/lib/team-bot.venv",
                ". ~/.local/lib/team-bot.venv/bin/activate && pip install -U pip wheel",
                f". .local/lib/team-bot.venv/bin/activate && cd /home/{unix_user}/team-bot && pip install .",
            ],
            _su_user=unix_user,
            _use_su_login=True,
        )

    if not dbdir:
        dbdir = f"/home/{unix_user}/.config/team_bot/{bot_email}/"
    secrets = [
        f"TEAMS_DBDIR={dbdir}",
    ]
    if bot_email:
        secrets.append(f"TEAMS_INIT_EMAIL={bot_email}")
    if bot_passwd:
        secrets.append(f"TEAMS_INIT_PASSWORD={bot_passwd}")
    if user_invite:
        secrets.append(f"TEAMS_USER_INVITE={user_invite}")
    env = "\n".join(secrets)
    files.put(
        name="upload secrets",
        src=StringIO(env),
        dest=f"/home/{unix_user}/.env",
        mode="0600",
        user=unix_user,
    )

    files.directory(
        name="chown team_bot directory",
        path=dbdir.rsplit("/", maxsplit=1)[0],
        mode="0700",
        recursive=True,
        user=unix_user,
        group=unix_user,
    )

    files.template(
        name="upload team-bot systemd unit",
        src=importlib.resources.files(__package__) / "pyinfra_assets" / "team-bot.service.j2",
        dest=f"/home/{unix_user}/.config/systemd/user/team-bot.service",
        user=unix_user,
        unix_user=unix_user,
        bot_email=bot_email,
    )

    systemd.daemon_reload(
        name=f"{unix_user}: load team-bot systemd service",
        user_name=unix_user,
        user_mode=True,
        _su_user=unix_user,
        _use_su_login=True,
    )

    server.shell(
        name=f"enable {unix_user}'s systemd units to auto-start at boot",
        commands=[f"loginctl enable-linger {unix_user}"],
    )

    systemd.service(
        name=f"{unix_user}: restart team-bot systemd service",
        service="team-bot.service",
        running=True,
        restarted=True,
        user_mode=True,
        _su_user=unix_user,
        _use_su_login=True,
    )
