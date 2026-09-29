"""BTN — black; one last slow pulse, the signal as at the start (89.0–90.0)."""
from comp.comp import CompParams
from tls import edl
from tls.camera import Cam, v3

SHOT = edl.SHOT_BY_ID["BTN"]


def cam_at(t):
    return Cam(fwd=v3(0, 1, 0))


def params(t, q):
    return {"black": True, "comp": CompParams()}
