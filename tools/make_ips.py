#!/usr/bin/env python3
"""make_ips.py ORIGINAL PATCHED OUT.ips - writes an IPS patch."""
import sys

src = open(sys.argv[1], 'rb').read()
dst = open(sys.argv[2], 'rb').read()
src += b'\x00' * (len(dst) - len(src))      # patchers zero-fill when growing the file

out = bytearray(b'PATCH')
i = 0
while i < len(dst):
    if src[i] == dst[i]:
        i += 1
        continue
    j = i
    # extend the record while bytes differ (bridging gaps of up to 5 equal bytes)
    while j < len(dst) and j - i < 0xFFFF:
        if src[j] != dst[j]:
            j += 1
        elif any(src[k] != dst[k] for k in range(j, min(j + 6, len(dst)))):
            j += 1
        else:
            break
    if i == 0x454F46:                        # offset "EOF" is reserved: start one byte earlier
        i -= 1
    out += i.to_bytes(3, 'big') + (j - i).to_bytes(2, 'big') + dst[i:j]
    i = j
out += b'EOF'
open(sys.argv[3], 'wb').write(out)

# verify
def apply(base, patch):
    data = bytearray(base)
    p = 5
    while patch[p:p + 3] != b'EOF':
        off = int.from_bytes(patch[p:p + 3], 'big')
        size = int.from_bytes(patch[p + 3:p + 5], 'big')
        p += 5
        chunk = patch[p:p + size]
        p += size
        if len(data) < off + size:
            data += b'\x00' * (off + size - len(data))
        data[off:off + size] = chunk
    return bytes(data)

result = apply(open(sys.argv[1], 'rb').read(), out)
assert result == dst, 'IPS round trip failed'
print(f'{sys.argv[3]}: {len(out)} bytes, verified')
