"""Small pure-Python verifier for the AMD SHAKE256 LMS/HSS vectors.

This is a correctness reference for the fixed parameter sets used by the
SCU35 comparison. It is not a hardened implementation.
"""
from __future__ import annotations

import re
from pathlib import Path

N = 32
_LMS = {15: 5, 16: 10, 17: 15}  # AMD SHAKE256 m=32 tree IDs
_OTS = {10: 2, 11: 4, 12: 8}  # AMD SHAKE256 n=32 Winternitz IDs


def _u32(n: int) -> bytes:
    return n.to_bytes(4, "big")


def _u16(n: int) -> bytes:
    return n.to_bytes(2, "big")


def _h(data: bytes) -> bytes:
    return __import__("hashlib").shake_256(data).digest(N)


def _params(lms_type: int, ots_type: int):
    if lms_type not in _LMS or ots_type not in _OTS:
        raise ValueError("unsupported AMD SHAKE256 LMS/LM-OTS parameter ID")
    h, w = _LMS[lms_type], _OTS[ots_type]
    u = (8 * N + w - 1) // w
    cksum_bits = (u * ((1 << w) - 1)).bit_length()
    p = u + (cksum_bits + w - 1) // w
    # RFC 8554 aligns the checksum's most significant bit to bit 15.
    # AMD's parameter table uses ls=6,4,0 for w=2,4,8 respectively.
    ls = {2: 6, 4: 4, 8: 0}[w]
    return h, w, p, ls


def _coeff(data: bytes, i: int, w: int) -> int:
    bit = i * w
    return (data[bit // 8] >> (8 - w - bit % 8)) & ((1 << w) - 1)


def _ots_public(message: bytes, sig: bytes, I: bytes, q: int,
                ots_type: int) -> bytes:
    _, w, p, ls = _params(16, ots_type)  # LMS height doesn't affect OTS
    if len(sig) != 4 + N + p * N or int.from_bytes(sig[:4], "big") != ots_type:
        raise ValueError("invalid LM-OTS signature length or type")
    C = sig[4:4 + N]
    Q = _h(I + _u32(q) + b"\x81\x81" + C + message)
    checksum = sum(((1 << w) - 1) - _coeff(Q, i, w)
                   for i in range((8 * N) // w))
    checksum <<= ls
    msg_cksum = Q + checksum.to_bytes(2, "big")
    z = []
    off = 4 + N
    for i in range(p):
        y = sig[off:off + N]
        off += N
        a = _coeff(msg_cksum, i, w)
        for j in range(a, (1 << w) - 1):
            y = _h(I + _u32(q) + _u16(i) + bytes([j]) + y)
        z.append(y)
    return _h(I + _u32(q) + b"\x80\x80" + b"".join(z))


def _lms_root(message: bytes, signature: bytes, pub: bytes) -> bytes:
    if len(pub) != 56:
        raise ValueError("invalid LMS public key length")
    lms_type, ots_type = int.from_bytes(pub[:4], "big"), int.from_bytes(pub[4:8], "big")
    h, _, p, _ = _params(lms_type, ots_type)
    expected = 4 + 4 + N + p * N + 4 + h * N
    if len(signature) != expected:
        raise ValueError("invalid LMS signature length")
    q = int.from_bytes(signature[:4], "big")
    if q >= (1 << h) or int.from_bytes(signature[4:8], "big") != ots_type:
        raise ValueError("invalid LMS q or LM-OTS type")
    type_offset = 8 + N + p * N
    if int.from_bytes(signature[type_offset:type_offset + 4], "big") != lms_type:
        raise ValueError("signature LMS type differs from public key")
    I, T1 = pub[8:24], pub[24:56]
    Kc = _ots_public(message, signature[4:4 + 4 + N + p * N], I, q, ots_type)
    node_num = (1 << h) + q
    tmp = _h(I + _u32(node_num) + b"\x82\x82" + Kc)
    path = signature[8 + N + p * N + 4:]
    for i in range(h):
        sibling = path[i * N:(i + 1) * N]
        parent = node_num >> 1
        if node_num & 1:
            tmp = _h(I + _u32(parent) + b"\x83\x83" + sibling + tmp)
        else:
            tmp = _h(I + _u32(parent) + b"\x83\x83" + tmp + sibling)
        node_num = parent
    if node_num != 1 or len(T1) != N:
        raise ValueError("invalid LMS tree path")
    return tmp


def verify_lms(message: bytes, signature: bytes, public_key: bytes) -> bool:
    """Verify a single LMS signature; malformed or unsupported inputs return False."""
    try:
        return _lms_root(bytes(message), bytes(signature), bytes(public_key)) == public_key[24:56]
    except (ValueError, OverflowError, IndexError, TypeError):
        return False


def verify_hss(message: bytes, signature: bytes, public_key: bytes) -> bool:
    """Verify one or two level HSS signatures using AMD's RFC-shaped wire format."""
    try:
        message, signature, public_key = bytes(message), bytes(signature), bytes(public_key)
        if len(public_key) != 60 or len(signature) < 4:
            return False
        levels = int.from_bytes(public_key[:4], "big")
        nspk = int.from_bytes(signature[:4], "big")
        if levels not in (1, 2) or nspk != levels - 1:
            return False
        if levels == 1:
            return verify_lms(message, signature[4:], public_key[4:])
        # Signature layout: Nspk, sig[0], pub[1], sig[1]. Vendor vector has
        # Nspk=1, so its first LMS signature authenticates the terminal key.
        # Locate sig[0] by the known parameter sizes of the root public key.
        root = public_key[4:]
        h, _, p, _ = _params(int.from_bytes(root[:4], "big"), int.from_bytes(root[4:8], "big"))
        sig0_len = 8 + N + p * N + 4 + h * N
        if len(signature) < 4 + sig0_len + 56:
            return False
        sig0 = signature[4:4 + sig0_len]
        child_pub = signature[4 + sig0_len:4 + sig0_len + 56]
        sig1 = signature[4 + sig0_len + 56:]
        # The root key's signature signs the child's 56-byte LMS public key.
        if _lms_root(child_pub, sig0, root) != root[24:56]:
            return False
        return _lms_root(message, sig1, child_pub) == child_pub[24:56]
    except (ValueError, OverflowError, IndexError, TypeError):
        return False


def load_vectors(path):
    """Parse the five named public test arrays from the vendor C source.

    Returns {"Lms": {algorithm, message, signature, public_key},
    "Hss": {...}}. No private material is parsed.
    """
    source = Path(path).read_text(encoding="utf-8")
    names = ("LmsShake256Data", "LmsShake256Signature", "LmsShake256PubKey",
             "HssShake256Data", "HssShake256Signature", "HssShake256PubKey")
    values = {}
    for name in names:
        match = re.search(r"\b" + name + r"\s*\[[^]]*\][^=]*=\s*\{(.*?)\};", source, re.S)
        if not match:
            raise ValueError(f"array {name} not found")
        values[name] = bytes(int(x, 16) for x in re.findall(r"0x([0-9a-fA-F]{2})", match.group(1)))
    return {
        "Lms": {"algorithm": "LMS-SHAKE256", "message": values[names[0]],
                "signature": values[names[1]], "public_key": values[names[2]]},
        "Hss": {"algorithm": "HSS-SHAKE256", "message": values[names[3]],
                "signature": values[names[4]], "public_key": values[names[5]]},
    }
