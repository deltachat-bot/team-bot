from io import StringIO
import importlib.resources

from pyinfra.operations import git, server, files, systemd
from pyinfra import host
from pyinfra.facts.systemd import SystemdStatus


def deploy_team_bot(
    unix_user: str, bot_email: str, bot_passwd: str, dbdir: str = None
):
    """Deploy TeamsBot to a UNIX user, with specified credentials

    :param unix_user: the existing UNIX user of the bot
    :param bot_email: the email address for the bot account
    :param bot_passwd: the password for the bot's email account
    :param dbdir: the directory where the bot's data will be stored. default: ~/.config/team-bot/email@example.org
    """

    clone_repo = git.repo(
        name="Pull the team-bot repository",
        src="https://github.com/deltachat-bot/team-bot",
        dest=f"/home/{unix_user}/team-bot",
        rebase=True,
        _su_user=unix_user,
        _use_su_login=True,
    )

    if clone_repo.changed:
        server.script(
            name="Setup virtual environment for team-bot",
            src=importlib.resources.files(__package__)
            / "pyinfra_assets"
            / "setup-venv.sh",
            _su_user=unix_user,
            _use_su_login=True,
        )

        server.shell(
            name="Compile team-bot",
            commands=[
                f". .local/lib/team-bot.venv/bin/activate && cd /home/{unix_user}/team-bot && pip install ."
            ],
            _su_user=unix_user,
            _use_su_login=True,
        )

    if not dbdir:
        dbdir = f"/home/{unix_user}/.config/team_bot/{bot_email}/"
    secrets = [
        f"TEAMS_DBDIR={dbdir}",
        f"TEAMS_INIT_EMAIL={bot_email}",
        f"TEAMS_INIT_PASSWORD={bot_passwd}",
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
        name="upload team-bot systemd unit",
        src=importlib.resources.files(__package__)
        / "pyinfra_assets"
        / "team-bot.service.j2",
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

    services = host.get_fact(
        SystemdStatus,
        user_mode=True,
        user_name=unix_user,
        _su_user=unix_user,
        _use_su_login=True,
    )
    try:
        if services["team-bot.service"]:
            systemd.service(
                name=f"{unix_user}: restart team-bot systemd service",
                service="team-bot.service",
                running=True,
                restarted=True,
                user_mode=True,
                _su_user=unix_user,
                _use_su_login=True,
            )
    except KeyError:
        pass
