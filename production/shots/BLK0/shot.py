"""BLK0 — black open (0.0–3.0): sound only (room tone, three slow signal pulses)."""
from comp.comp import CompParams
from tls import edl
from tls.camera import Cam, v3

SHOT = edl.SHOT_BY_ID["BLK0"]


def cam_at(t):
    return Cam(fwd=v3(0, 1, 0))


def params(t, q):
    return {"black": True, "comp": CompParams()}
