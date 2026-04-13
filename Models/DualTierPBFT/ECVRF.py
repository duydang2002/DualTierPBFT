# ecvrf.py
# Minimal ECVRF-like implementation (secp256k1)
# Educational / testing only — NOT production-grade crypto!

import hashlib
import sys

# --- curve params for secp256k1 ---
P  = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F
A  = 0
B  = 7
# base point
Gx = 0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798
Gy = 0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8
N  = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
HCOFACTOR = 1

# --- helper math ---
def _inv_mod(x, m=P):
    # modular inverse
    return pow(x, m-2, m)

def _is_on_curve(point):
    if point is None:
        return True
    x, y = point
    return (y*y - (x*x*x + A*x + B)) % P == 0

def _point_add(p, q):
    # Add two points in affine coords, handle identity None
    if p is None: return q
    if q is None: return p
    (x1,y1), (x2,y2) = p, q
    if x1 == x2 and (y1 != y2 or y1 == 0):
        return None
    if x1 == x2:
        # doubling
        lam = (3 * x1*x1 + A) * _inv_mod(2*y1, P) % P
    else:
        lam = (y2 - y1) * _inv_mod(x2 - x1, P) % P
    x3 = (lam*lam - x1 - x2) % P
    y3 = (lam*(x1 - x3) - y1) % P
    return (x3, y3)

def _point_mul(k, point):
    # scalar multiply with double-and-add
    if k % N == 0 or point is None:
        return None
    if k < 0:
        # k * P = -k * (-P)
        return _point_mul(-k, (point[0], (-point[1]) % P))
    result = None
    addend = point
    while k:
        if k & 1:
            result = _point_add(result, addend)
        addend = _point_add(addend, addend)
        k >>= 1
    return result

def _int_to_bytes(x, length):
    return x.to_bytes(length, 'big')

def _bytes_to_int(b):
    return int.from_bytes(b, 'big')

def _point_to_bytes_uncompressed(pt):
    if pt is None:
        return b'\x00'
    x, y = pt
    return b'\x04' + _int_to_bytes(x, 32) + _int_to_bytes(y, 32)

# --- Tonelli-Shanks for sqrt mod p (needed for try-and-increment) ---
def _legendre_symbol(a, p=P):
    return pow(a, (p-1)//2, p)

def _mod_sqrt(a, p=P):
    # Solve x^2 = a mod p. p % 4 == 3 for secp256k1? No, secp256k1 p % 4 == 3, so sqrt = a^{(p+1)/4}
    if a == 0:
        return 0
    if p % 4 == 3:
        x = pow(a, (p+1)//4, p)
        if (x*x) % p == a % p:
            return x
        return None
    # Generic Tonelli-Shanks omitted for brevity (not needed here)
    raise NotImplementedError("mod sqrt for this p not implemented")

# --- hash-to-curve (try-and-increment) ---
def hash_to_curve(alpha: bytes, max_tries=256):
    # Returns a curve point H such that H = HashToCurve(alpha)
    for ctr in range(max_tries):
        h = hashlib.sha256(alpha + bytes([ctr])).digest()
        x = int.from_bytes(h, 'big') % P
        rhs = (x*x*x + A*x + B) % P
        if _legendre_symbol(rhs) == 1:
            y = _mod_sqrt(rhs)
            # choose one y deterministically, e.g. even-y
            if y is None:
                continue
            if (y % 2) == 1:
                y = P - y
            pt = (x, y)
            if _is_on_curve(pt):
                # ensure pt has order dividing N (since cofactor=1 for secp256k1 this is fine)
                return pt
    raise ValueError("hash_to_curve failed to find a valid point")

# --- deterministic nonce (simple) ---
def derive_k(sk_int: int, h_point_bytes: bytes):
    # SIMPLE deterministic k: sha256(sk_bytes || h_point_bytes || b'ecvrf') mod N
    # Replace with RFC6979 for production
    sk_bytes = _int_to_bytes(sk_int, 32)
    k = _bytes_to_int(hashlib.sha256(sk_bytes + b'\x00' + h_point_bytes + b'ecvrf').digest()) % N
    if k == 0:
        # fallback
        k = 1
    return k

# --- VRF operations ---
class ECVRF:
    def __init__(self):
        self.G = (Gx, Gy)
        # Nothing else stateful

    def generate_keypair(self):
        # WARNING: in production use a CRYPTOGEN secure RNG
        import secrets
        sk = secrets.randbelow(N-1) + 1
        pk = _point_mul(sk, self.G)
        return sk, pk

    def prove(self, sk_int: int, alpha: bytes):
        """
        Returns (beta, proof_bytes)
        beta: VRF output bytes = SHA256(0x03 || Gamma) (as an example)
        proof: serialized: gamma || c || s  (each fixed length)
        """
        # 1) H = HashToCurve(alpha)
        H = hash_to_curve(alpha)
        H_bytes = _point_to_bytes_uncompressed(H)

        # 2) Gamma = sk * H
        Gamma = _point_mul(sk_int, H)
        Gamma_bytes = _point_to_bytes_uncompressed(Gamma)

        # 3) k deterministic
        k = derive_k(sk_int, H_bytes)

        # 4) compute R = k*G, R_h = k*H
        R = _point_mul(k, self.G)
        R_h = _point_mul(k, H)

        # 5) compute challenge c = hash(H || Gamma || R || R_h) mod N
        c_hash = hashlib.sha256(
            _point_to_bytes_uncompressed(H) +
            Gamma_bytes +
            _point_to_bytes_uncompressed(R) +
            _point_to_bytes_uncompressed(R_h)
        ).digest()
        c = _bytes_to_int(c_hash) % N

        # 6) s = (k + c*sk) mod N  (Schnorr style)
        s = (k + (c * sk_int)) % N

        # 7) output beta (hash of Gamma) and proof (Gamma || c || s)
        beta = hashlib.sha256(b'\x03' + Gamma_bytes).digest()
        c_bytes = _int_to_bytes(c, 32)
        s_bytes = _int_to_bytes(s, 32)
        proof = Gamma_bytes + c_bytes + s_bytes
        return beta, proof

    def verify(self, pk_point, alpha: bytes, beta: bytes, proof: bytes) -> bool:
        """
        Verify proof for public key pk_point (x,y tuple), message alpha, expected beta.
        proof format: Gamma_bytes(65) || c(32) || s(32)
        """
        try:
            # parse proof
            if len(proof) != 65 + 32 + 32:
                return False
            Gamma_bytes = proof[:65]
            c = _bytes_to_int(proof[65:97])
            s = _bytes_to_int(proof[97:129])

            # reconstruct Gamma point
            if Gamma_bytes[0] != 4:
                return False
            gx = _bytes_to_int(Gamma_bytes[1:33])
            gy = _bytes_to_int(Gamma_bytes[33:65])
            Gamma = (gx, gy)
            if not _is_on_curve(Gamma):
                return False

            # check beta matches Gamma
            expected_beta = hashlib.sha256(b'\x03' + Gamma_bytes).digest()
            if expected_beta != beta:
                return False

            # recompute H = HashToCurve(alpha)
            H = hash_to_curve(alpha)

            # compute U = s*G - c*Y   (we compute s*G + (-c)*Y)
            sG = _point_mul(s, self.G)
            cY = _point_mul(c % N, pk_point)
            # compute U = sG + (-cY)
            neg_cY = (cY[0], (-cY[1]) % P) if cY is not None else None
            U = _point_add(sG, neg_cY)

            # compute V = s*H - c*Gamma
            sH = _point_mul(s, H)
            cGamma = _point_mul(c % N, Gamma)
            neg_cGamma = (cGamma[0], (-cGamma[1]) % P) if cGamma is not None else None
            V = _point_add(sH, neg_cGamma)

            # recompute challenge
            c2_hash = hashlib.sha256(
                _point_to_bytes_uncompressed(H) +
                _point_to_bytes_uncompressed(Gamma) +
                _point_to_bytes_uncompressed(U) +
                _point_to_bytes_uncompressed(V)
            ).digest()
            c2 = _bytes_to_int(c2_hash) % N

            return c2 == c
        except Exception as e:
            # don't expose internals in real usage
            print("Verify error:", e, file=sys.stderr)
            return False

# --- Demo ---
def demo():
    vrf = ECVRF()
    sk, pk = vrf.generate_keypair()
    alpha = b"my-secret-seed-12345"
    alpha2= b"my-secret-seed-123456"
    beta, proof = vrf.prove(sk, alpha)
    print("beta:", beta.hex())
    print("proof len:", len(proof))

    ok = vrf.verify(pk, alpha2, beta, proof)
    print("verify:", ok)

    # test tamper
    bad_beta = bytes([beta[0] ^ 0xFF]) + beta[1:]
    print("verify tampered beta:", vrf.verify(pk, alpha, bad_beta, proof))

if __name__ == "__main__":
    demo()
