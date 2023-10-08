from io import StringIO
import importlib.resources

from pyinfra.operations import git, server, files, systemd


def deploy_teams_bot(unix_user: str, bot_email: str, bot_passwd: str, dbdir: str = None):
    """Deploy TeamsBot to a UNIX user, with specified credentials

    :param unix_user: the existing UNIX user of the bot
    :param bot_email: the email address for the bot account
    :param bot_passwd: the password for the bot's email account
    :param dbdir: the directory where the bot's data will be stored. default: ~/.config/teams-bot/email@example.org
    """

    clone_xdcget = git.repo(
        name="Pull the teams-bot repository",
        src="https://git.0x90.space/missytake/teams-bot",
        dest=f"/home/{unix_user}/teams-bot",
        _su_user=unix_user,
        _use_su_login=True,
    )

    if clone_xdcget.changed:
        server.script(
            name="Setup virtual environment for teams-bot",
            src=importlib.resources.files(__package__) / "pyinfra_assets" / "setup-venv.sh",
            _su_user=unix_user,
            _use_su_login=True,
        )

        server.shell(
            name="Compile teams-bot",
            commands=[
                f". .local/lib/teams-bot.venv/bin/activate && cd /home/{unix_user}/teams-bot && pip install ."
            ],
            _su_user=unix_user,
            _use_su_login=True,
        )

    if not dbdir:
        dbdir = f"/home/{unix_user}/.config/teams_bot/{bot_email}/"
    secrets = [
        f"TEAMS_INIT_EMAIL={bot_email}",
        f"TEAMS_INIT_PASSWORD={bot_passwd}",
        f'TEAMS_INIT_DBDIR={dbdir}',
        f'TEAMS_RUN_DBDIR={dbdir}',
    ]
    env = "\n".join(secrets)
    files.put(
        name="upload secrets",
        src=StringIO(env),
        dest=f"/home/{unix_user}/.env",
        mode="0600",
        user=unix_user,
    )

    files.directory(
        name="chown database directory",
        path=dbdir,
        mode="0700",
        recursive=True,
        user=unix_user,
    )

    files.template(
        name="upload teams-bot systemd unit",
        src=importlib.resources.files(__package__) / "pyinfra_assets" / "teams-bot.service.j2",
        dest=f"/home/{unix_user}/.config/systemd/user/teams-bot.service",
        user=unix_user,
        unix_user=unix_user,
        bot_email=bot_email,
    )
    systemd.daemon_reload(
        name=f"{unix_user}: load teams-bot systemd service",
        user_name=unix_user,
        user_mode=True,
        _su_user=unix_user,
        _use_su_login=True,
    )

    server.shell(
        name=f"enable {unix_user}'s systemd units to auto-start at boot",
        commands=[f"loginctl enable-linger {unix_user}"],
    )
