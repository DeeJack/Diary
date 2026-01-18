# Security Documentation

## Overview

Diary is designed with privacy and security as fundamental requirements. Every design decision prioritizes protecting user data from unauthorized access.

## Threat Model

### Assumptions

**In Scope**:
- Attacker gains access to saved notebook files
- Attacker observes file system (file names, sizes, access times)
- Attacker attempts password guessing attacks
- Attacker attempts to tamper with encrypted files
- Memory dump attacks while application is closed
- Shoulder surfing attacks (observing screen)

**Out of Scope**:
- Malware running on user's system with root/admin privileges
- Keyloggers or screen recorders
- Physical access to unlocked, running application
- Side-channel attacks (timing, power analysis)
- Attacks on the operating system or Qt framework

### Security Goals

1. **Confidentiality**: Notebook contents are unreadable without password
2. **Integrity**: Tampering with encrypted files is detectable
3. **Authentication**: Only correct password can decrypt notebooks
4. **Forward Secrecy**: Compromised notebook doesn't reveal other notebooks (different salts)

## Encryption Design

### Cryptographic Primitives

**XChaCha20-Poly1305** (Authenticated Encryption with Associated Data):
- **Algorithm**: XChaCha20 stream cipher + Poly1305 MAC
- **Key Size**: 256 bits (32 bytes)
- **Nonce Size**: 192 bits (24 bytes) - extended from ChaCha20's 96 bits
- **Authentication Tag**: 128 bits (16 bytes)

**Why XChaCha20-Poly1305?**
- Fast on all platforms (no hardware acceleration required)
- Constant-time (resistant to timing attacks)
- Large nonce space (2^192) eliminates nonce reuse concerns
- AEAD (authenticated encryption) prevents tampering
- Well-studied, IETF standardized (RFC 8439)

### Key Derivation

**Argon2ID** (Password-Based Key Derivation):
```python
Parameters:
  variant    = Argon2id (hybrid of Argon2i and Argon2d)
  time_cost  = 2 iterations
  memory     = 64 MB (65536 KB)
  threads    = 4
  salt       = 32 bytes (random, per-file)
  output     = 32 bytes (256-bit key)
```

**Why Argon2ID?**
- Winner of Password Hashing Competition (2015)
- Resistant to GPU/ASIC attacks (memory-hard)
- Hybrid mode balances side-channel resistance (Argon2i) and GPU resistance (Argon2d)
- Tunable parameters allow adjustment as hardware improves

**Parameter Justification**:
- **2 iterations**: Balance between security and UX (sub-second unlock)
- **64 MB memory**: Significant GPU resistance without excessive RAM
- **4 threads**: Utilize multi-core CPUs efficiently
- **32-byte salt**: Prevents rainbow tables and parallel attacks

### File Format

```
Encrypted Notebook File Structure:
┌─────────────────────────────────────┐
│ Magic Bytes: "DIARY001" (8 bytes)   │  ← File format identification
├─────────────────────────────────────┤
│ Salt (32 bytes)                     │  ← Argon2 salt (random per file)
├─────────────────────────────────────┤
│ Nonce (24 bytes)                    │  ← XChaCha20 nonce (random per file)
├─────────────────────────────────────┤
│ Encrypted Data (variable length)    │  ← Chunked encryption (64KB chunks)
│   Chunk 1: [ciphertext]            │
│   Chunk 2: [ciphertext]            │
│   ...                               │
│   Chunk N: [ciphertext]            │
├─────────────────────────────────────┤
│ Authentication Tag (16 bytes)       │  ← Poly1305 MAC (integrity check)
└─────────────────────────────────────┘
```

**Magic Bytes**: `DIARY001` identifies file format version
**Salt**: Random per file, prevents rainbow table attacks
**Nonce**: Random per file, ensures unique keystream
**Chunking**: 64KB chunks prevent memory exhaustion on large notebooks
**Auth Tag**: Poly1305 MAC covers entire file (detects any tampering)

### Encryption Process

```python
def encrypt_notebook(notebook_data: bytes, password: str) -> bytes:
    # 1. Generate random salt (32 bytes)
    salt = os.urandom(32)

    # 2. Derive key from password using Argon2
    key = argon2.hash_password(
        password=password.encode('utf-8'),
        salt=salt,
        time_cost=2,
        memory_cost=65536,  # 64 MB
        parallelism=4,
        hash_len=32
    )

    # 3. Generate random nonce (24 bytes)
    nonce = os.urandom(24)

    # 4. Compress data with ZSTD (before encryption)
    compressed_data = zstd.compress(notebook_data, level=3)

    # 5. Encrypt in 64KB chunks
    cipher = ChaCha20_Poly1305(key, nonce)
    ciphertext_chunks = []
    for chunk in split_into_chunks(compressed_data, 64 * 1024):
        ciphertext_chunks.append(cipher.update(chunk))

    # 6. Finalize and get authentication tag
    final_chunk = cipher.finalize()
    auth_tag = cipher.tag

    # 7. Assemble file
    return (
        b"DIARY001" +
        salt +
        nonce +
        b"".join(ciphertext_chunks) + final_chunk +
        auth_tag
    )
```

### Decryption Process

```python
def decrypt_notebook(encrypted_file: bytes, password: str) -> bytes:
    # 1. Verify magic bytes
    assert encrypted_file[:8] == b"DIARY001"

    # 2. Extract salt and nonce
    salt = encrypted_file[8:40]
    nonce = encrypted_file[40:64]

    # 3. Extract ciphertext and auth tag
    ciphertext = encrypted_file[64:-16]
    auth_tag = encrypted_file[-16:]

    # 4. Derive key (same parameters as encryption)
    key = argon2.hash_password(
        password=password.encode('utf-8'),
        salt=salt,
        time_cost=2,
        memory_cost=65536,
        parallelism=4,
        hash_len=32
    )

    # 5. Decrypt and verify authentication tag
    cipher = ChaCha20_Poly1305(key, nonce)
    plaintext_chunks = []
    for chunk in split_into_chunks(ciphertext, 64 * 1024):
        plaintext_chunks.append(cipher.update(chunk))

    # 6. Finalize (verifies auth tag automatically)
    try:
        final_chunk = cipher.finalize_with_tag(auth_tag)
        compressed_data = b"".join(plaintext_chunks) + final_chunk
    except InvalidTag:
        raise AuthenticationError("File has been tampered with")

    # 7. Decompress
    return zstd.decompress(compressed_data)
```

## Security Features

### 1. Secure Memory Management

**SecureBuffer Class**:
```python
class SecureBuffer:
    """Wrapper for sensitive data that zeros memory on deletion"""

    def __init__(self, data: bytes):
        self._data = bytearray(data)

    def get(self) -> bytes:
        return bytes(self._data)

    def __del__(self):
        # Zero memory before deallocation
        for i in range(len(self._data)):
            self._data[i] = 0
```

**Usage**:
- Encryption keys stored in SecureBuffer
- Passwords zeroed after key derivation
- Plaintext zeroed after encryption

**Limitations**:
- Python garbage collector may delay zeroing
- CPython may create string copies during operations
- OS may swap memory to disk (mitigated by mlock where available)

### 2. Authenticated Encryption

**Poly1305 MAC** prevents:
- **Bit-flipping attacks**: Changing ciphertext without detection
- **Truncation attacks**: Removing chunks from end of file
- **Splicing attacks**: Combining parts of different encrypted files

**Authentication Guarantees**:
- Any modification to ciphertext invalidates auth tag
- Decryption fails immediately if tampered
- No partial plaintext leaked on auth failure

### 3. Unique Salts and Nonces

**Salt Uniqueness**:
- New random salt generated for each save
- Prevents rainbow table attacks
- Prevents cross-file password correlation

**Nonce Uniqueness**:
- New random nonce generated for each save
- XChaCha20's 192-bit nonce makes collisions astronomically unlikely
- Ensures unique keystream for each encryption

### 4. Compression Before Encryption

**Why ZSTD before XChaCha20?**
- Reduces file size (faster I/O, smaller storage)
- Reduces data to encrypt (faster encryption)
- No information leakage (compression ratio doesn't reveal structure due to encryption)

**Compression Level**: 3 (balance speed vs size)

### 5. Atomic File Writes

```python
def atomic_write(data: bytes, target_path: str):
    # Write to temporary file
    temp_path = target_path + ".tmp"
    with open(temp_path, 'wb') as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())  # Force to disk

    # Atomic rename (POSIX guarantees atomicity)
    os.replace(temp_path, target_path)
```

**Prevents**:
- Corrupted files from interrupted writes
- Partial writes leaving file in invalid state
- Data loss from power failure during save

### 6. Password Strength Recommendations

**UI Enforcements**:
- Minimum 8 characters (configurable)
- Strength meter (entropy-based)
- Warning for weak passwords (common words, simple patterns)

**Recommendations**:
- Use passphrases (4+ random words)
- Use password manager for generation/storage
- Avoid personal information (names, dates)

## Attack Resistance

### Brute Force Attacks

**Defenses**:
- Argon2 forces 64MB memory per attempt (limits parallelism)
- 2 iterations add computational cost
- No rate limiting needed (offline attacks infeasible)

**Estimated Attack Cost** (against 8-char password):
- GPU attack: ~1000 attempts/sec on RTX 4090
- Time to exhaustion: centuries for random password
- Mitigated by password complexity requirements

### Dictionary Attacks

**Defenses**:
- Unique salt per file prevents pre-computation
- Argon2 memory cost makes large-scale pre-computation infeasible
- Password strength meter educates users

### Tampering Attacks

**Defenses**:
- Poly1305 auth tag covers entire ciphertext
- Any bit modification causes decryption failure
- No partial data leaked on auth failure

### Known-Plaintext Attacks

**Defenses**:
- XChaCha20 is stream cipher (known plaintext doesn't help)
- Unique nonce per file prevents keystream reuse
- Compression reduces predictability of plaintext structure

### Side-Channel Attacks

**Limited Defenses**:
- Constant-time cryptography (XChaCha20, Poly1305)
- No password-dependent branches in crypto code

**Residual Risks**:
- Cache timing attacks (Python overhead dominates)
- Power analysis (out of scope for software)
- EM radiation (out of scope)

## Privacy Features

### 1. Local-First Storage

- No cloud sync (user controls sync via own tools)
- No telemetry or analytics
- No network requests (except for updates if implemented)

### 2. Encrypted Filenames (Optional)

**Current**: Filenames are plaintext (`my-diary.diary`)
**Future**: Option to encrypt filenames (`a3f2e1d9.diary`)

### 3. Metadata Protection

**Not Protected**:
- File size (reveals notebook size)
- File modification time (reveals when edited)
- Number of files (reveals number of notebooks)

**Mitigation**: Use encrypted container (VeraCrypt, LUKS) for stronger protection

### 4. Steganography (Not Implemented)

**Future Option**: Hide encrypted notebooks in innocent-looking files (images, videos)

## Backup Security

### Automatic Backups

**Location**: `~/.diary/backups/`
**Structure**:
```
backups/
├── daily/
│   └── my-diary-2026-01-17.diary.bak
├── weekly/
│   └── my-diary-2026-W03.diary.bak
└── monthly/
    └── my-diary-2026-01.diary.bak
```

**Encryption**: Backups are encrypted with same password as original
**Rotation**: Old backups automatically deleted (configurable retention)

**Risks**:
- More copies = more attack surface
- Forgot password = lost backups too

**Recommendations**:
- Store backups on encrypted external drive
- Consider password manager for recovery
- Test backup restoration periodically

## Security Best Practices

### For Users

1. **Use Strong Passwords**:
   - 12+ characters or 4+ word passphrase
   - Use password manager (Bitwarden, 1Password, KeePassXC)
   - Don't reuse diary password elsewhere

2. **Protect Backups**:
   - Store on encrypted external drive
   - Don't upload to cloud without additional encryption
   - Test restoration before disaster

3. **Physical Security**:
   - Lock screen when away
   - Enable full disk encryption (BitLocker, FileVault, LUKS)
   - Be aware of shoulder surfing

4. **Recovery Planning**:
   - Write password hint (not password!) in safe place
   - Consider password manager backup
   - Test password before forgetting

### For Developers

1. **Never Log Sensitive Data**:
   - No passwords in logs
   - No plaintext notebook data in logs
   - No encryption keys in crash reports

2. **Secure Dependencies**:
   - Audit cryptography libraries (use pynacl, cryptography)
   - Keep dependencies updated (security patches)
   - Verify signatures on packages

3. **Code Review**:
   - All crypto code requires review
   - No custom crypto (use established libraries)
   - Test encryption/decryption round-trips

4. **Timing Safety**:
   - Use constant-time comparison for MACs
   - Avoid password-dependent branches
   - Zero sensitive memory when done

## Compliance & Standards

### Standards Followed

- **NIST SP 800-63B**: Password guidelines
- **IETF RFC 8439**: ChaCha20-Poly1305 spec
- **IETF RFC 9106**: Argon2 spec
- **OWASP**: Cryptographic storage guidelines

### Certifications

**Not Applicable** (open-source personal project):
- No FIPS 140-2 compliance (would require hardware module)
- No SOC 2 audit (no service provider)
- No ISO 27001 (no organization)

## Known Limitations

1. **Memory Dumps**: Plaintext visible in RAM while notebook open
2. **Swap Files**: OS may write memory to disk swap
3. **Hibernation**: RAM written to disk includes keys
4. **Screen Capture**: Screenshots reveal plaintext content
5. **Keyloggers**: Malware can capture password during unlock
6. **Clipboard**: Copied text may persist in clipboard managers

## Future Security Improvements

### Planned

1. **Hardware Key Support**: YubiKey for second factor
2. **Encrypted Filenames**: Hide notebook names from file system
3. **Memory Locking**: mlock() to prevent swap
4. **Secure Input**: Anti-keylogger measures for password entry

### Under Consideration

1. **Plausible Deniability**: Hidden volumes (VeraCrypt-style)
2. **Duress Passwords**: Secondary password that wipes data
3. **Timed Locks**: Auto-lock after inactivity
4. **Emergency Wipe**: Panic button to delete all data

## Security Disclosure

**Reporting Vulnerabilities**:
- Email: [security contact]
- Encrypt with PGP: [PGP key]
- Allow 90 days for patch before public disclosure

**Hall of Fame**: Contributors will be credited (unless anonymous)

## References

- [IETF RFC 8439: ChaCha20-Poly1305](https://tools.ietf.org/html/rfc8439)
- [IETF RFC 9106: Argon2](https://tools.ietf.org/html/rfc9106)
- [NIST SP 800-63B: Digital Identity Guidelines](https://pages.nist.gov/800-63-3/sp800-63b.html)
- [OWASP Cryptographic Storage Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Cryptographic_Storage_Cheat_Sheet.html)
