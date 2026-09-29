"""BLK1 — hard cut to black, true digital silence (82.5–84.5)."""
from comp.comp import CompParams
from tls import edl
from tls.camera import Cam, v3

SHOT = edl.SHOT_BY_ID["BLK1"]


def cam_at(t):
    return Cam(fwd=v3(0, 1, 0))


def params(t, q):
    return {"black": True, "comp": CompParams()}
