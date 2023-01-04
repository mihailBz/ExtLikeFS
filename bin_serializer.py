import binascii
from pickle import dumps, loads


def text_to_bits(
    text: str, encoding: str = "utf-8", errors: str = "surrogatepass"
) -> str:
    bits = bin(int(binascii.hexlify(text.encode(encoding, errors)), 16))[2:]
    return bits.zfill(8 * ((len(bits) + 7) // 8))


def text_from_bits(
    bits: str, encoding: str = "utf-8", errors: str = "surrogatepass"
) -> str:
    n = int(bits, 2)
    return int2bytes(n).decode(encoding, errors)


def bytes_to_bits(bytes_: bytes) -> str:
    bits = bin(int(binascii.hexlify(bytes(bytes_)), 16))[2:]
    return bits.zfill(8 * ((len(bits) + 7) // 8))


def bytes_from_bits(bits: str) -> bytes:
    n = int(bits, 2)
    return int2bytes(n)


def int2bytes(i: int) -> bytes:
    hex_string = "%x" % i
    n = len(hex_string)
    return binascii.unhexlify(hex_string.zfill(n + (n & 1)))


def bit_dumps(o: object) -> str:
    return bytes_to_bits(dumps(o))


def bit_loads(bits: str) -> object:
    return loads(bytes_from_bits(bits))
