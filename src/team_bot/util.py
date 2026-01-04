from typing import Optional

from deltachat_rpc_client import Account
from deltachat_rpc_client._utils import AttrDict


def get_crew_id(event: AttrDict) -> Optional[int]:
    ac = event.account
    crew_id = ac.get_config("ui.crew_id")
    if crew_id:
        return int(crew_id)


def get_crew_invite(account: Account) -> str:
    """Return crew invite and store it in the account object"""
    crew_invite = account.get_config("ui.crew_invite")
    if not crew_invite:
        crew_invite = account.get_qr_code()
        account.crew_invite = crew_invite
    return crew_invite
