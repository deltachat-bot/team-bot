import os

import pickledb
import requests

import deltachat
import pytest
from _pytest.pytester import LineMatcher

from teams_bot.bot import RelayPlugin


class ClickRunner:
    def __init__(self, main):
        from click.testing import CliRunner

        self.runner = CliRunner()
        self._main = main
        self._rootargs = []

    def set_basedir(self, account_dir):
        self._rootargs.insert(0, "--basedir")
        self._rootargs.insert(1, account_dir)

    def run_ok(self, args, fnl=None, input=None):
        __tracebackhide__ = True
        argv = self._rootargs + args
        # we use our nextbackup helper to cache account creation
        # unless --no-test-cache is specified
        res = self.runner.invoke(self._main, argv, catch_exceptions=False, input=input)
        if res.exit_code != 0:
            print(res.output)
            raise Exception("cmd exited with %d: %s" % (res.exit_code, argv))
        return _perform_match(res.output, fnl)

    def run_fail(self, args, fnl=None, input=None, code=None):
        __tracebackhide__ = True
        argv = self._rootargs + args
        res = self.runner.invoke(self._main, argv, catch_exceptions=False, input=input)
        if res.exit_code == 0 or (code is not None and res.exit_code != code):
            print(res.output)
            raise Exception(
                "got exit code {!r}, expected {!r}, output: {}".format(
                    res.exit_code,
                    code,
                    res.output,
                ),
            )
        return _perform_match(res.output, fnl)


def _perform_match(output, fnl):
    __tracebackhide__ = True
    if fnl:
        lm = LineMatcher(output.splitlines())
        lines = [x.strip() for x in fnl.strip().splitlines()]
        try:
            lm.fnmatch_lines(lines)
        except Exception:
            print(output)
            raise
    return output


@pytest.fixture
def cmd():
    """invoke a command line subcommand."""
    from teams_bot.cli import teams_bot

    return ClickRunner(teams_bot)


@pytest.fixture
def tmp_file_path(request, tmpdir):
    if request.param:
        path = str(tmpdir) + "/" + str(request.param)
        with open(path, "w+", encoding="utf-8") as f:
            f.write("test")
        return path


@pytest.fixture
def relaycrew(crew):
    crew.bot.relayplugin = RelayPlugin(crew.bot, crew.kvstore)
    crew.bot.add_account_plugin(crew.bot.relayplugin)
    assert not crew.bot.relayplugin.is_relay_group(crew)
    yield crew


@pytest.fixture
def crew(teams_bot, teams_user, tmpdir):
    from teams_bot.bot import SetupPlugin

    crew = teams_bot.create_group_chat(
        f"Team: {teams_bot.get_config('addr')}", verified=True
    )
    setupplugin = SetupPlugin(crew.id)
    teams_bot.add_account_plugin(setupplugin)
    qr = crew.get_join_qr()
    teams_user.qr_join_chat(qr)
    setupplugin.member_added.wait(timeout=30)
    crew.user = teams_user
    crew.bot = teams_bot
    crew.bot.setupplugin = setupplugin

    # wait until old user is properly added to crew
    last_message = teams_user.wait_next_incoming_message().text
    while (
        f"Member Me ({teams_user.get_config('addr')}) added by bot" not in last_message
    ):
        print("User received message:", last_message)
        last_message = teams_user.wait_next_incoming_message().text

    crew.kvstore = pickledb.load(tmpdir + "pickle.db", True)
    crew.kvstore.set("crew_id", crew.id)
    yield crew


@pytest.fixture
def teams_bot(tmpdir):
    ac = account(tmpdir + "/bot.sqlite", show_ffi=True)
    yield ac
    ac.shutdown()
    ac.wait_shutdown()


@pytest.fixture
def teams_user(tmpdir):
    ac = account(tmpdir + "/user.sqlite")
    yield ac
    ac.shutdown()
    ac.wait_shutdown()


@pytest.fixture
def outsider(tmpdir):
    ac = account(tmpdir + "/outsider.sqlite")
    yield ac
    ac.shutdown()
    ac.wait_shutdown()


def account(db_path, show_ffi=False):
    token = os.environ.get(
        "DCC_NEW_TMP_EMAIL", "https://nine.testrun.org/cgi-bin/newemail.py"
    )
    print(token)
    ac = deltachat.Account(str(db_path))
    credentials = requests.post(token).json()
    email = credentials["email"]
    password = credentials["password"]
    print(db_path, email, password)
    ac.run_account(email, password, show_ffi=show_ffi)
    return ac


@pytest.fixture
def chat(tmpdir):
    token = os.getenv("DCC_NEW_TMP")
    ac = deltachat.Account(str(tmpdir) + "/db.sqlite")
    # create bot account from token
    # create chat partner from token
    # initiate a chat between them
    # return the chat object
    print(token, str(ac.get_config("addr")))
