"""
Encrypt and decrypt data with Argon2ID and XChaCha20-Poly1305
"""

import secrets
import struct
from pathlib import Path
from typing import Callable, cast

import nacl.secret
import nacl.utils
import nacl
from argon2.low_level import hash_secret_raw, Type


class SecureBuffer:
    """Wrapper for sensitive data that zeros memory on deletion"""

    def __init__(self, data: bytes):
        self._data: bytearray = bytearray(data)

    def __bytes__(self):
        return bytes(self._data)

    def __len__(self):
        return len(self._data)

    def __del__(self):
        # Zero out memory before deletion
        if hasattr(self, "_data"):
            for i in range(len(self._data)):
                self._data[i] = 0

    def wipe(self):
        """Explicitly wipe the data"""
        for i in range(len(self._data)):
            self._data[i] = 0


class SecureEncryption:
    """
    Secure file encryption using Argon2id for key derivation and
    XChaCha20-Poly1305 for authenticated encryption.
    """

    # Constants
    CHUNK_SIZE: int = 64 * 1024  # 64 KB chunks
    SALT_SIZE: int = 32  # 256 bits
    NONCE_SIZE: int = 24  # 192 bits for XChaCha20
    KEY_SIZE: int = 32  # 256 bits
    TAG_SIZE: int = 16  # 128 bits for Poly1305 MAC

    # Argon2id parameters (OWASP recommended minimums for 2023+)
    ARGON2_TIME_COST: int = 2  # iterations
    ARGON2_MEMORY_COST: int = 64 * 1024  # 64 MB
    ARGON2_PARALLELISM: int = 4  # threads

    # File format version
    VERSION: int = 1

    # File format magic bytes
    MAGIC: bytes = b"SECENC01"

    def __init__(self):
        """Initialize the encryption system"""
        pass

    @staticmethod
    def _derive_key(password: str, salt: bytes) -> SecureBuffer:
        """
        Derive encryption key from password using Argon2id

        Args:
            password: User password
            salt: Random salt

        Returns:
            SecureBuffer containing derived key
        """
        # Convert password to bytes
        password_bytes = password.encode("utf-8")

        try:
            # Derive key using Argon2id
            raw_key = hash_secret_raw(
                secret=password_bytes,
                salt=salt,
                time_cost=SecureEncryption.ARGON2_TIME_COST,
                memory_cost=SecureEncryption.ARGON2_MEMORY_COST,
                parallelism=SecureEncryption.ARGON2_PARALLELISM,
                hash_len=SecureEncryption.KEY_SIZE,
                type=Type.ID,  # Argon2id
            )
            return SecureBuffer(raw_key)
        finally:
            # Zero out password bytes
            password_bytes = bytearray(password_bytes)
            for i in range(len(password_bytes)):
                password_bytes[i] = 0

    @staticmethod
    def encrypt_json_to_file(
        json_string: str,
        output_path: Path,
        password: str,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> None:
        """
        Encrypt a JSON string and save to file using streaming encryption

        Args:
            json_string: JSON string to encrypt
            output_path: Path to encrypted output file
            password: Encryption password
            progress_callback: Optional callback(bytes_processed, total_bytes)
        """
        output_path = Path(output_path)

        # Convert JSON string to bytes
        data_bytes = json_string.encode("utf-8")
        total_size = len(data_bytes)
        bytes_processed = 0

        # Generate random salt
        salt = secrets.token_bytes(SecureEncryption.SALT_SIZE)

        # Derive encryption key
        key_buffer = SecureEncryption._derive_key(password, salt)

        try:
            # Create cipher
            box = nacl.secret.Aead(bytes(key_buffer))

            with open(output_path, "wb") as outfile:
                # Write header: magic + version + salt
                _ = outfile.write(SecureEncryption.MAGIC)
                _ = outfile.write(struct.pack("<H", SecureEncryption.VERSION))
                _ = outfile.write(salt)

                # Encrypt and write chunks
                chunk_number = 0
                offset = 0

                while offset < total_size:
                    # Get next chunk
                    chunk_end = min(offset + SecureEncryption.CHUNK_SIZE, total_size)
                    chunk = data_bytes[offset:chunk_end]

                    # Generate unique nonce for this chunk
                    # Using chunk number + random bytes for nonce
                    nonce_base = secrets.token_bytes(SecureEncryption.NONCE_SIZE - 8)
                    nonce = nonce_base + struct.pack("<Q", chunk_number)

                    # Encrypt chunk (includes MAC tag)
                    encrypted_chunk = box.encrypt(chunk, nonce=nonce)

                    # Write chunk size + encrypted data
                    chunk_size = len(encrypted_chunk)
                    _ = outfile.write(struct.pack("<I", chunk_size))
                    _ = outfile.write(encrypted_chunk)

                    bytes_processed += len(chunk)
                    offset = chunk_end
                    chunk_number += 1

                    if progress_callback:
                        progress_callback(bytes_processed, total_size)
            # Zero out data bytes
            data_bytes = bytearray(data_bytes)
            for i in range(len(data_bytes)):
                data_bytes[i] = 0
        finally:
            key_buffer.wipe()

    @staticmethod
    def decrypt_file_to_json(
        input_path: Path,
        password: str,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> str:
        """
        Decrypt a file and return JSON string using streaming decryption

        Args:
            input_path: Path to encrypted file
            password: Decryption password
            progress_callback: Optional callback(bytes_processed, total_bytes)

        Returns:
            Decrypted JSON string

        Raises:
            ValueError: If file format is invalid or decryption fails
        """
        input_path = Path(input_path)

        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")

        file_size = input_path.stat().st_size
        bytes_processed = 0

        # Collect decrypted chunks
        decrypted_chunks: list[bytes] = []

        with open(input_path, "rb") as infile:
            # Read and verify header
            magic = infile.read(len(SecureEncryption.MAGIC))
            if magic != SecureEncryption.MAGIC:
                raise ValueError("Invalid file format: wrong magic bytes")

            version_bytes = infile.read(2)
            version: int = cast(int, struct.unpack("<H", version_bytes)[0])
            if version != SecureEncryption.VERSION:
                raise ValueError(f"Unsupported file version: {version}")

            # Read salt
            salt = infile.read(SecureEncryption.SALT_SIZE)
            if len(salt) != SecureEncryption.SALT_SIZE:
                raise ValueError("Invalid file format: truncated salt")

            # Derive decryption key
            key_buffer = SecureEncryption._derive_key(password, salt)

            try:
                # Create cipher
                box = nacl.secret.Aead(bytes(key_buffer))

                # Decrypt chunks
                while True:
                    # Read chunk size
                    chunk_size_bytes = infile.read(4)
                    if not chunk_size_bytes:
                        break  # End of file

                    if len(chunk_size_bytes) < 4:
                        raise ValueError("Invalid file format: truncated chunk size")

                    chunk_size = cast(int, struct.unpack("<I", chunk_size_bytes)[0])

                    # Sanity check on chunk size
                    if (
                        chunk_size
                        > SecureEncryption.CHUNK_SIZE
                        + SecureEncryption.NONCE_SIZE
                        + SecureEncryption.TAG_SIZE
                        + 100
                    ):
                        raise ValueError("Invalid file format: chunk size too large")

                    # Read encrypted chunk
                    encrypted_chunk = infile.read(chunk_size)
                    if len(encrypted_chunk) != chunk_size:
                        raise ValueError("Invalid file format: truncated chunk")

                    try:
                        # Decrypt chunk (verifies MAC automatically)
                        plaintext = box.decrypt(encrypted_chunk)
                        decrypted_chunks.append(plaintext)
                    except Exception as e:
                        print(e)
                        raise ValueError(
                            "Decryption failed: wrong password or corrupted data"
                        )
                    finally:
                        encrypted_chunk = bytearray(encrypted_chunk)
                        for i in range(len(encrypted_chunk)):
                            encrypted_chunk[i] = 0
                    bytes_processed += chunk_size
                    if progress_callback:
                        progress_callback(bytes_processed, file_size)

                # Combine all decrypted chunks
                full_data = b"".join(decrypted_chunks)

                for chunk in decrypted_chunks:
                    chunk_array = bytearray(chunk)
                    for i in range(len(chunk_array)):
                        chunk_array[i] = 0
                try:
                    json_string = full_data.decode("utf-8")
                    return json_string
                finally:
                    full_data = bytearray(full_data)
                    for i in range(len(full_data)):
                        full_data[i] = 0
            finally:
                key_buffer.wipe()
