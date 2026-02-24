"""Filter section synthesis helpers."""

import math

from scipy.signal import butter, cheby1


def design_lp_sallen(fsf, fc, q, c_val):
    # Compute equal-C Sallen-Key component values from section specs.
    f0 = fsf * fc
    c1 = c2 = c_val
    r = 1 / (2 * math.pi * c_val * f0)

    k = 3 - (1 / q)

    # k = 1 + r3/r4
    r4 = 1000
    r3 = r4 / (k - 1)

    return {
        "R1": r,
        "R2": r,
        "R3": r3,
        "R4": r4,
        "C1": c1,
        "C2": c2,
    }


def design_butterworth(order_n, fc):
    wc = 2 * math.pi * fc
    _z, p, _k = butter(order_n, wc, btype="low", analog=True, output="zpk")
    return zpk_to_sections_fsf_q(p)


def design_chebyshev_type1(order_n, fc):
    rp = 3
    wc = 2 * math.pi * fc
    _z, p, _k = cheby1(order_n, rp, wc, btype="low", analog=True, output="zpk")
    return zpk_to_sections_fsf_q(p)


def zpk_to_sections_fsf_q(poles):
    poles = list(poles)
    used = [False] * len(poles)
    out = []

    for i, pole in enumerate(poles):
        if used[i]:
            continue
        if abs(pole.imag) < 1e-12:
            out.append((abs(pole.real), None))
            used[i] = True
        else:
            target = pole.conjugate()
            j = min(
                (j for j in range(len(poles)) if not used[j] and j != i),
                key=lambda idx: abs(poles[idx] - target),
            )
            used[i] = used[j] = True

            w0 = abs(pole)  # |p| (rad/s if poles are analog)
            q = w0 / (-2.0 * pole.real)  # pole.real < 0
            out.append((w0, q))

    # Keep low-Q sections first, then any first-order remainder.
    biquad_sections = sorted(
        [section for section in out if section[1] is not None], key=lambda item: item[1]
    )
    first_order_sections = [section for section in out if section[1] is None]
    return biquad_sections + first_order_sections


def design_rc_lp(fc, fsf, c_val):
    # Compute single-pole RC values from cutoff and scaling factor.
    f0 = fsf * fc
    c1 = c_val
    r1 = 1 / (2 * math.pi * c_val * f0)

    return {
        "R1": r1,
        "C1": c1,
    }
