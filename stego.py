from pathlib import Path


def bytes_to_bits(data: bytes) -> list[int]:
    bits = []
    for byte in data:
        for i in range(7, -1, -1):
            bits.append((byte >> i) & 1)
    return bits


def bits_to_bytes(bits: list[int]) -> bytes:
    if len(bits) % 8 != 0:
        raise ValueError("Bit length must be a multiple of 8.")

    output = bytearray()
    for i in range(0, len(bits), 8):
        byte = 0
        for bit in bits[i:i + 8]:
            byte = (byte << 1) | bit
        output.append(byte)
    return bytes(output)


def int_to_32bits(n: int) -> list[int]:
    return [(n >> i) & 1 for i in range(31, -1, -1)]


def bits_to_int(bits: list[int]) -> int:
    value = 0
    for bit in bits:
        value = (value << 1) | bit
    return value


def get_period_sequence(L: int, mode: str):
    if L <= 0:
        raise ValueError("L must be greater than 0.")

    if mode == "fixed":
        while True:
            yield L

    elif mode == "cycle3":
        seq = [8, 16, 28]
        i = 0
        while True:
            yield seq[i % len(seq)]
            i += 1

    elif mode == "alternate":
        seq = [L, 2 * L]
        i = 0
        while True:
            yield seq[i % len(seq)]
            i += 1

    else:
        raise ValueError("Unsupported mode. Use: fixed, cycle3, or alternate.")


def embed_message(carrier_path: str, message_path: str, output_path: str, S: int, L: int, mode: str):
    carrier_bytes = Path(carrier_path).read_bytes()
    message_bytes = Path(message_path).read_bytes()

    carrier_bits = bytes_to_bits(carrier_bytes)

    message_ext = Path(message_path).suffix.lower().lstrip(".")
    ext_bytes = message_ext.encode("utf-8")
    ext_bits = bytes_to_bits(ext_bytes)

    message_bits = bytes_to_bits(message_bytes)

    # Metadata format:
    # [32 bits ext length in bytes][ext bytes][32 bits message length in bytes][message bytes]
    ext_len_bits = int_to_32bits(len(ext_bytes))
    message_len_bits = int_to_32bits(len(message_bytes))

    payload_bits = ext_len_bits + ext_bits + message_len_bits + message_bits

    if S < 0:
        raise ValueError("S must be 0 or greater.")

    positions = []
    pos = S
    period_gen = get_period_sequence(L, mode)

    for _ in payload_bits:
        if pos >= len(carrier_bits):
            raise ValueError("Carrier file is too small for this message with the given S, L, and mode.")
        positions.append(pos)
        pos += next(period_gen)

    for idx, bit in zip(positions, payload_bits):
        carrier_bits[idx] = bit

    stego_bytes = bits_to_bytes(carrier_bits)
    Path(output_path).write_bytes(stego_bytes)


def extract_message(stego_path: str, output_base_path: str, S: int, L: int, mode: str) -> str:
    stego_bytes = Path(stego_path).read_bytes()
    stego_bits = bytes_to_bits(stego_bytes)

    if S < 0:
        raise ValueError("S must be 0 or greater.")

    pos = S
    period_gen = get_period_sequence(L, mode)

    def read_bits(count: int) -> list[int]:
        nonlocal pos
        result = []
        for _ in range(count):
            if pos >= len(stego_bits):
                raise ValueError("Stego file ended before extraction could complete.")
            result.append(stego_bits[pos])
            pos += next(period_gen)
        return result

    # Read extension length
    ext_len_bits = read_bits(32)
    ext_len_bytes = bits_to_int(ext_len_bits)

    # Read extension
    ext_bits = read_bits(ext_len_bytes * 8)
    ext_bytes = bits_to_bytes(ext_bits) if ext_len_bytes > 0 else b""
    recovered_ext = ext_bytes.decode("utf-8") if ext_bytes else "bin"

    # Read message length
    message_len_bits = read_bits(32)
    message_len_bytes = bits_to_int(message_len_bits)

    # Read message bytes
    message_bits = read_bits(message_len_bytes * 8)
    recovered_bytes = bits_to_bytes(message_bits)

    output_path = f"{output_base_path}.{recovered_ext}"
    Path(output_path).write_bytes(recovered_bytes)

    return output_path