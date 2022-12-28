import binascii
from pickle import dumps, loads


def text_to_bits(text, encoding='utf-8', errors='surrogatepass'):
    bits = bin(int(binascii.hexlify(text.encode(encoding, errors)), 16))[2:]
    return bits.zfill(8 * ((len(bits) + 7) // 8))


def text_from_bits(bits, encoding='utf-8', errors='surrogatepass'):
    n = int(bits, 2)
    return int2bytes(n).decode(encoding, errors)


def bytes_to_bits(bytes_):
    bits = bin(int(binascii.hexlify(bytes(bytes_)), 16))[2:]
    return bits.zfill(8 * ((len(bits) + 7) // 8))


def bytes_from_bits(bits):
    n = int(bits, 2)
    return int2bytes(n)


def int2bytes(i):
    hex_string = '%x' % i
    n = len(hex_string)
    return binascii.unhexlify(hex_string.zfill(n + (n & 1)))


def bit_dumps(o):
    return bytes_to_bits(dumps(o))


def bit_loads(bits):
    return loads(bytes_from_bits(bits))


# dumped = bytes_to_bits(dumps(['.']))
# print(loads(bytes_from_bits(dumped)))
