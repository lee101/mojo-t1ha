"""Portable t1ha2 kernels exposed through a small C ABI."""

comptime U8Ptr = Pointer[UInt8, AnyOrigin[mut=True]]
comptime U64Ptr = Pointer[UInt64, AnyOrigin[mut=True]]

comptime P0 = UInt64(0xEC99BF0D8372CAAB)
comptime P1 = UInt64(0x82434FE90EDCEF39)
comptime P2 = UInt64(0xD4F06DB99D67BE4B)
comptime P3 = UInt64(0xBD9CACC22C6E9571)
comptime P4 = UInt64(0x9C06FAF4D023E3AB)
comptime P5 = UInt64(0xC060724A8424F345)
comptime P6 = UInt64(0xCB5AF53AE3AAAC31)


@always_inline
def rot64(v: UInt64, n: UInt64) -> UInt64:
    return (v >> n) | (v << (UInt64(64) - n))


@always_inline
def mul_high(a: UInt64, b: UInt64) -> UInt64:
    return UInt64((UInt128(a) * UInt128(b)) >> UInt128(64))


@always_inline
def mux64(v: UInt64, prime: UInt64) -> UInt64:
    return (v * prime) ^ mul_high(v, prime)


@always_inline
def final64(a: UInt64, b: UInt64) -> UInt64:
    var x = (a + rot64(b, UInt64(41))) * P0
    var y = (rot64(a, UInt64(23)) + b) * P6
    return mux64(x ^ y, P5)


@always_inline
def load64(data: U8Ptr, start: Int) -> UInt64:
    var address = Int(data) + start
    if (address & 7) == 0:
        return U64Ptr(unsafe_from_address=address).unsafe_load(0)
    var value = UInt64(0)
    for j in range(8):
        value |= UInt64(data.unsafe_load(start + j)) << UInt64(j * 8)
    return value


@always_inline
def tail64(data: U8Ptr, start: Int, length: Int) -> UInt64:
    var value = UInt64(0)
    var count = length & 7
    if count == 0:
        count = 8
    for j in range(count):
        value |= UInt64(data.unsafe_load(start + j)) << UInt64(j * 8)
    return value


@always_inline
def update_block(state: U64Ptr, data: U8Ptr, start: Int):
    var a = state.unsafe_load(0)
    var b = state.unsafe_load(1)
    var c = state.unsafe_load(2)
    var d = state.unsafe_load(3)
    var w0 = load64(data, start)
    var w1 = load64(data, start + 8)
    var w2 = load64(data, start + 16)
    var w3 = load64(data, start + 24)
    var d02 = w0 + rot64(w2 + d, UInt64(56))
    var c13 = w1 + rot64(w3 + c, UInt64(19))
    state.unsafe_store(3, d ^ (b + rot64(w1, UInt64(38))))
    state.unsafe_store(2, c ^ (a + rot64(w0, UInt64(57))))
    state.unsafe_store(1, b ^ (P6 * (c13 + w2)))
    state.unsafe_store(0, a ^ (P5 * (d02 + w3)))


def squash(state: U64Ptr):
    var a = state.unsafe_load(0)
    var b = state.unsafe_load(1)
    var c = state.unsafe_load(2)
    var d = state.unsafe_load(3)
    state.unsafe_store(0, a ^ (P6 * (c + rot64(d, UInt64(23)))))
    state.unsafe_store(1, b ^ (P5 * (rot64(c, UInt64(19)) + d)))


def mix_ab(state: U64Ptr, left: Int, right: Int, value: UInt64, prime: UInt64):
    var product = state.unsafe_load(right) + value
    state.unsafe_store(left, state.unsafe_load(left) ^ (product * prime))
    state.unsafe_store(right, state.unsafe_load(right) + mul_high(product, prime))


def final128(state: U64Ptr, result: U64Ptr):
    mix_ab(state, 0, 1, rot64(state.unsafe_load(2), UInt64(41)) ^ state.unsafe_load(3), P0)
    mix_ab(state, 1, 2, rot64(state.unsafe_load(3), UInt64(23)) ^ state.unsafe_load(0), P6)
    mix_ab(state, 2, 3, rot64(state.unsafe_load(0), UInt64(19)) ^ state.unsafe_load(1), P5)
    mix_ab(state, 3, 0, rot64(state.unsafe_load(1), UInt64(31)) ^ state.unsafe_load(2), P4)
    result.unsafe_store(0, state.unsafe_load(2) + state.unsafe_load(3))
    result.unsafe_store(1, state.unsafe_load(0) ^ state.unsafe_load(1))


def tail_ab(state: U64Ptr, data: U8Ptr, start: Int, length: Int) -> UInt64:
    var pos = start
    if length > 24:
        mix_ab(state, 0, 1, load64(data, pos), P4)
        pos += 8
    if length >= 17:
        mix_ab(state, 1, 0, load64(data, pos), P3)
        pos += 8
    if length >= 9:
        mix_ab(state, 0, 1, load64(data, pos), P2)
        pos += 8
    if length >= 1:
        mix_ab(state, 1, 0, tail64(data, pos, length), P1)
    return final64(state.unsafe_load(0), state.unsafe_load(1))


def tail_abcd(state: U64Ptr, data: U8Ptr, start: Int, length: Int, result: U64Ptr):
    var pos = start
    if length > 24:
        mix_ab(state, 0, 3, load64(data, pos), P4)
        pos += 8
    if length >= 17:
        mix_ab(state, 1, 0, load64(data, pos), P3)
        pos += 8
    if length >= 9:
        mix_ab(state, 2, 1, load64(data, pos), P2)
        pos += 8
    if length >= 1:
        mix_ab(state, 3, 2, tail64(data, pos, length), P1)
    final128(state, result)


def init_state(state: U64Ptr, x: UInt64, y: UInt64):
    state.unsafe_store(0, x)
    state.unsafe_store(1, y)
    state.unsafe_store(2, rot64(y, UInt64(23)) + ~x)
    state.unsafe_store(3, ~y + rot64(x, UInt64(19)))


def atonce64(data: U8Ptr, length: Int, seed: UInt64) -> UInt64:
    var state_storage = SIMD[DType.uint64, 4](0)
    var state = U64Ptr(unsafe_from_address=Int(Pointer(to=state_storage)))
    state.unsafe_store(0, seed)
    state.unsafe_store(1, UInt64(length))
    var pos = 0
    if length > 32:
        state.unsafe_store(2, rot64(UInt64(length), UInt64(23)) + ~seed)
        state.unsafe_store(3, ~UInt64(length) + rot64(seed, UInt64(19)))
        while pos + 32 <= length:
            update_block(state, data, pos)
            pos += 32
        squash(state)
    return tail_ab(state, data, pos, length - pos)


def atonce128(data: U8Ptr, length: Int, seed: UInt64, result: U64Ptr):
    var state_storage = SIMD[DType.uint64, 4](0)
    var state = U64Ptr(unsafe_from_address=Int(Pointer(to=state_storage)))
    var a = seed
    var b = UInt64(length)
    var c = rot64(b, UInt64(23)) + ~a
    var d = ~b + rot64(a, UInt64(19))
    var pos = 0
    if length > 32:
        while pos + 32 <= length:
            var w0 = load64(data, pos)
            var w1 = load64(data, pos + 8)
            var w2 = load64(data, pos + 16)
            var w3 = load64(data, pos + 24)
            var d02 = w0 + rot64(w2 + d, UInt64(56))
            var c13 = w1 + rot64(w3 + c, UInt64(19))
            d = d ^ (b + rot64(w1, UInt64(38)))
            c = c ^ (a + rot64(w0, UInt64(57)))
            b = b ^ (P6 * (c13 + w2))
            a = a ^ (P5 * (d02 + w3))
            pos += 32
    state.unsafe_store(0, a)
    state.unsafe_store(1, b)
    state.unsafe_store(2, c)
    state.unsafe_store(3, d)
    tail_abcd(state, data, pos, length - pos, result)


@export("mt1_t1ha2_atonce")
def mt1_t1ha2_atonce(data_addr: Int, length: Int, seed: UInt64) abi("C") -> UInt64:
    return atonce64(U8Ptr(unsafe_from_address=data_addr), length, seed)


@export("mt1_t1ha2_atonce128")
def mt1_t1ha2_atonce128(data_addr: Int, length: Int, seed: UInt64, result_addr: Int) abi("C"):
    atonce128(
        U8Ptr(unsafe_from_address=data_addr), length, seed,
        U64Ptr(unsafe_from_address=result_addr),
    )


@export("mt1_stream_init")
def mt1_stream_init(state_addr: Int, meta_addr: Int, seed_x: UInt64, seed_y: UInt64) abi("C"):
    init_state(U64Ptr(unsafe_from_address=state_addr), seed_x, seed_y)
    var meta = U64Ptr(unsafe_from_address=meta_addr)
    meta.unsafe_store(0, UInt64(0))
    meta.unsafe_store(1, UInt64(0))


@export("mt1_stream_update")
def mt1_stream_update(state_addr: Int, buffer_addr: Int, meta_addr: Int, data_addr: Int, length: Int) abi("C"):
    var state = U64Ptr(unsafe_from_address=state_addr)
    var buffer = U8Ptr(unsafe_from_address=buffer_addr)
    var meta = U64Ptr(unsafe_from_address=meta_addr)
    var data = U8Ptr(unsafe_from_address=data_addr)
    var partial = Int(meta.unsafe_load(0))
    meta.unsafe_store(1, meta.unsafe_load(1) + UInt64(length))
    var pos = 0
    if partial > 0:
        var needed = 32 - partial
        var chunk = needed if length >= needed else length
        for i in range(chunk):
            buffer.unsafe_store(partial + i, data.unsafe_load(i))
        partial += chunk
        pos += chunk
        if partial < 32:
            meta.unsafe_store(0, UInt64(partial))
            return
        update_block(state, buffer, 0)
        partial = 0
    while pos + 32 <= length:
        update_block(state, data, pos)
        pos += 32
    var remaining = length - pos
    for i in range(remaining):
        buffer.unsafe_store(i, data.unsafe_load(pos + i))
    meta.unsafe_store(0, UInt64(remaining))


@export("mt1_stream_final")
def mt1_stream_final(state_addr: Int, buffer_addr: Int, meta_addr: Int, result_addr: Int) abi("C"):
    var state = U64Ptr(unsafe_from_address=state_addr)
    var buffer = U8Ptr(unsafe_from_address=buffer_addr)
    var meta = U64Ptr(unsafe_from_address=meta_addr)
    var total_bits = (meta.unsafe_load(1) << UInt64(3)) ^ (UInt64(1) << UInt64(63))
    var bits = SIMD[DType.uint64, 1](total_bits)
    mt1_stream_update(state_addr, buffer_addr, meta_addr, Int(Pointer(to=bits)), 8)
    tail_abcd(state, buffer, 0, Int(meta.unsafe_load(0)), U64Ptr(unsafe_from_address=result_addr))
