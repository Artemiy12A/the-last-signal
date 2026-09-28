"""Display transforms: AgX-style filmic (Blender 4 / Troy Sobotka's AgX, polynomial fit by
bwrensch), sRGB / Rec.709 encoding. Scene-linear Rec.709 in, display-referred out."""
import numpy as np

AGX_IN = np.array([[0.842479062253094, 0.0423282422610123, 0.0423756549057051],
                   [0.0784335999999992, 0.878468636469772, 0.0784336],
                   [0.0792237451477643, 0.0791661274605434, 0.879142973793104]])
AGX_OUT = np.array([[1.19687900512017, -0.0528968517574562, -0.0529716355144438],
                    [-0.0980208811401368, 1.15190312990417, -0.0980434501171241],
                    [-0.0990297440797205, -0.0989611768448433, 1.15107367264116]])
MIN_EV, MAX_EV = -12.47393, 4.026069


def _contrast(x):
    x2 = x * x
    x4 = x2 * x2
    return 15.5 * x4 * x2 - 40.14 * x4 * x + 31.96 * x4 - 6.868 * x2 * x + 0.4298 * x2 + 0.1191 * x - 0.00232


def agx(rgb, punch=0.0, sat=1.0):
    """rgb: (..., 3) scene linear. Returns display-linear (..., 3) in [0,1] (apply srgb_encode after)."""
    v = np.maximum(rgb, 1e-10) @ AGX_IN
    v = np.clip((np.log2(v) - MIN_EV) / (MAX_EV - MIN_EV), 0.0, 1.0)
    v = _contrast(v)
    if punch or sat != 1.0:
        # optional look: slope/power on the encoded signal, saturation around luma
        if punch:
            v = np.clip(v, 0, 1) ** (1.0 + punch)
        luma = v @ np.array([0.2126, 0.7152, 0.0722])
        v = luma[..., None] + sat * (v - luma[..., None])
    v = np.clip(v, 0, 1) @ AGX_OUT
    v = np.clip(v, 0, 1) ** 2.2   # AgX output is display-encoded ~2.2; back to display linear
    return v


def srgb_encode(x):
    x = np.clip(x, 0, 1)
    return np.where(x <= 0.0031308, 12.92 * x, 1.055 * np.power(x, 1 / 2.4) - 0.055)


def to8(rgb_scene, exposure=0.0, punch=0.0, sat=1.0):
    d = agx(rgb_scene * (2.0 ** exposure), punch, sat)
    return (srgb_encode(d) * 255 + 0.5).astype(np.uint8)
