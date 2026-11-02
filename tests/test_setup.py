import pytest

from team_bot.setup import configure_email, configure_password, configure_proxy


@pytest.mark.parametrize(
    ("email", "prev_email", "reconfigure", "res_email"),
    [
        (None, None, True, "@nine.testrun.org"),
        ("test@example.org", None, True, "@example.org"),
        (None, "test@example.org", False, "@example.org"),
        ("test@example.org", "test@example.org", False, "@example.org"),
        ("test@new.org", "test@example.org", True, "@new.org"),
    ],
)
def test_configure_email(email, prev_email, reconfigure, res_email):
    result = configure_email(email, prev_email)
    assert result[0] == reconfigure
    assert result[1].endswith(res_email)


@pytest.mark.parametrize(
    ("password", "prev_pass", "reconfigure", "res_pass"),
    [
        (None, None, True, 20),
        ("s3cr3t", None, True, 6),
        ("new-password", "s3cr3t", True, 12),
        (None, "s3cr3t", False, 6),
        ("s3cr3t", "s3cr3t", False, 6),
    ],
)
def test_configure_param(password, prev_pass, reconfigure, res_pass):
    result = configure_password(password, prev_pass)
    assert result[0] == reconfigure
    assert len(result[1]) == res_pass


def test_configure_proxy(bot):
    proxy_url = "socks5://127.0.0.1:9050"
    assert configure_proxy(proxy_url, bot.account)
    bot.configure(bot.account.get_config("configured_addr"), bot.account.get_config("mail_pw"))
    assert bot.account.get_config("proxy_enabled") == "1"
    assert bot.account.get_config("proxy_url") == proxy_url
    assert configure_proxy(None, bot.account)
    bot.configure(bot.account.get_config("configured_addr"), bot.account.get_config("mail_pw"))
    assert bot.account.get_config("proxy_enabled") == "0"
    assert bot.account.get_config("proxy_url") == proxy_url
