"""SM3 hash implementation (GB/T 32905-2016) in pure Python.
Used by A-Bogus signing for Douyin / TikTok request verification.
"""

from __future__ import annotations

_MASK = 0xFFFFFFFF

IV: tuple[int, ...] = (
    0x7380166F,
    0x4914B2B9,
    0x172442D7,
    0xDA8A0600,
    0xA96F30BC,
    0x163138AA,
    0xE38DEE4D,
    0xB0FB0E4E,
)

T_J: tuple[int, ...] = (0x79CC4519,) * 16 + (0x7A879D8A,) * 48


def _rotate_left(val: int, count: int) -> int:
    count &= 31
    return ((val << count) | (val >> (32 - count))) & _MASK


def _ff(j: int, x: int, y: int, z: int) -> int:
    if j < 16:
        return x ^ y ^ z
    return (x & y) | (x & z) | (y & z)


def _gg(j: int, x: int, y: int, z: int) -> int:
    if j < 16:
        return x ^ y ^ z
    return (x & y) | (~x & z)


def _p0(x: int) -> int:
    return x ^ _rotate_left(x, 9) ^ _rotate_left(x, 17)


def _p1(x: int) -> int:
    return x ^ _rotate_left(x, 15) ^ _rotate_left(x, 23)


def _compress(v: tuple[int, ...], b: bytes) -> tuple[int, ...]:
    w: list[int] = [int.from_bytes(b[i : i + 4], "big") for i in range(0, 64, 4)]
    for j in range(16, 68):
        x = w[j - 16] ^ w[j - 9] ^ _rotate_left(w[j - 3], 15)
        w.append(_p1(x) ^ _rotate_left(w[j - 13], 7) ^ w[j - 6])

    w_prime: list[int] = [w[j] ^ w[j + 4] for j in range(64)]

    a, b_val, c, d, e, f, g, h = v

    for j in range(64):
        ss1 = _rotate_left(
            (_rotate_left(a, 12) + e + _rotate_left(T_J[j], j)) & _MASK,
            7,
        )
        ss2 = ss1 ^ _rotate_left(a, 12)
        tt1 = (_ff(j, a, b_val, c) + d + ss2 + w_prime[j]) & _MASK
        tt2 = (_gg(j, e, f, g) + h + ss1 + w[j]) & _MASK
        d = c
        c = _rotate_left(b_val, 9)
        b_val = a
        a = tt1
        h = g
        g = _rotate_left(f, 19)
        f = e
        e = _p0(tt2)

    return (
        a ^ v[0],
        b_val ^ v[1],
        c ^ v[2],
        d ^ v[3],
        e ^ v[4],
        f ^ v[5],
        g ^ v[6],
        h ^ v[7],
    )


def sm3_digest(data: bytes) -> bytes:
    length_bits = len(data) * 8
    padded = bytearray(data)
    padded.append(0x80)
    while (len(padded) % 64) != 56:
        padded.append(0x00)
    padded.extend(length_bits.to_bytes(8, "big"))

    v = IV
    for i in range(0, len(padded), 64):
        v = _compress(v, padded[i : i + 64])

    out = bytearray()
    for word in v:
        out.extend(word.to_bytes(4, "big"))
    return bytes(out)


def sm3_to_array(text: str) -> list[int]:
    return list(sm3_digest(text.encode("utf-8")))
