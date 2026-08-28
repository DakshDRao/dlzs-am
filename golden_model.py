def lead_one(a, w):
    assert 0 <= a < (1 << w), f"operand {a} out of range for width {w}"
    if a == 0:
        raise ValueError("lead_one undefined for 0")
    return a.bit_length() - 1

def dlzs_floor(a,b,w):
    if a == 0 or b == 0:
        return 0
    
    return b << lead_one(a,w)
def dlzs_ceil(a,b,w):
    if a == 0 or b == 0:
        return 0
    k = lead_one(a,w)
    if a & (a - 1):
        k = k + 1
    return b << k
def dlzs_nearest_linear(a,b,w):
    if a == 0 or b == 0:
        return 0
    k = lead_one(a,w)
    if k > 0 and (a >> (k - 1)) & 1 :
        k = k + 1
    return b << k
def dlzs_nearest_log(a,b,w):
    if a == 0 or b == 0:
        return 0
    k = lead_one(a,w)
    if a * a >= 2 * 2 ** (2*k) :
        k = k + 1
    return b << k

def mitchell(a, b, w):
    if a == 0 or b == 0:
        return 0
    ka, kb = lead_one(a, w), lead_one(b, w)
    Ma, Mb = a - (1 << ka), b - (1 << kb)
    frac = (Ma << kb) + (Mb << ka)      
    base = 1 << (ka + kb)                
    if frac < base:
        return base + frac               
    return frac << 1
def drum_extract(a, k, w):
    ka = lead_one(a, w)
    s = max(0, ka - k + 1)      
    t = a >> s
    if s > 0:
        t |= 1                  
    return t, s


def drum(a, b, k, w):
    if a == 0 or b == 0:
        return 0
    ta, sa = drum_extract(a, k, w)
    tb, sb = drum_extract(b, k, w)
    return (ta * tb) << (sa + sb)                     


assert dlzs_floor(8, 5, 8) == 40      # a=8 exact power, exact result
assert dlzs_ceil(8, 5, 8) == 40       # exact power, must NOT round up
assert dlzs_floor(7, 5, 8) == 20      # 7 -> 4, 5<<2
assert dlzs_ceil(7, 5, 8) == 40       # 7 -> 8, 5<<3
assert dlzs_floor(0, 5, 8) == 0
assert dlzs_ceil(5, 0, 8) == 0
assert dlzs_nearest_linear(1,  5, 8) == 5     # k=0, no mantissa bit
assert dlzs_nearest_linear(22, 5, 8) == 80    # 22 -> 16
assert dlzs_nearest_linear(26, 5, 8) == 160   # 26 -> 32
assert dlzs_nearest_linear(24, 5, 8) == 160   # tie -> up
assert dlzs_nearest_linear(16, 5, 8) == 80    # exact power
assert dlzs_nearest_log(22, 1, 8) == 16   # 22^2=484  < 512
assert dlzs_nearest_log(23, 1, 8) == 32   # 23^2=529 >= 512
assert mitchell(16, 16, 8) == 256    # both exact, must be exact
assert mitchell(22, 22, 8) == 448    # no carry (exact 484)
assert mitchell(31, 31, 8) == 960    # carry     (exact 961)
assert mitchell(24, 23, 8) == 496    # ma+mb = 0.9375, no carry
assert mitchell(24, 24, 8) == 512    # ma+mb = 1.0 exactly, carry
assert drum(4,   4,   4, 8) == 16      # fits in 4 bits, exact
assert drum(16,  16,  4, 8) == 324     # s=1, 8|1=9, 81<<2 (exact 256)
assert drum(16,  16,  5, 8) == 256     # fits in 5 bits, exact
assert drum(255, 255, 4, 8) == 57600   # 15*15<<8 (exact 65025)