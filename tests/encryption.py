import json
import secrets
from pathlib import Path

from typing_extensions import Any

from diary.utils.encryption import SecureEncryption


def test_encryption():
    def progress(processed: int, total: int):
        percent = (processed / total) * 100
        print(f"\rProgress: {percent:.1f}%", end="", flush=True)

    # Example: Encrypt JSON to file
    print("=== Secure JSON Encryption System ===\n")

    encrypted_file = Path("notebook.enc")

    # Create test JSON data
    test_data: dict[str, Any] = {
        "pages": [
            {
                "id": 1,
                "title": "My First Page",
                "strokes": [
                    {"points": [[10, 20, 0.5], [15, 25, 0.6]], "color": "#000000"},
                    {"points": [[30, 40, 0.7], [35, 45, 0.8]], "color": "#FF0000"},
                ],
                "text_boxes": [{"x": 100, "y": 200, "content": "Hello World!"}],
            },
            {"id": 2, "title": "Second Page", "strokes": [], "text_boxes": []},
        ],
        "metadata": {"created": "2024-10-16", "version": "1.0"},
    }

    # Convert to JSON string
    json_string = json.dumps(test_data, indent=2)

    password = "MySecurePassword123!"

    print(f"Original JSON size: {len(json_string)} bytes\n")
    print("Sample of JSON data:")
    print(json_string[:200] + "...\n")

    # Generate salt and derive key
    salt = secrets.token_bytes(SecureEncryption.SALT_SIZE)
    key_buffer = SecureEncryption.derive_key(password, salt)

    # Encrypt JSON to file
    print("Encrypting JSON to file...")
    SecureEncryption.encrypt_bytes_to_file(
        json_string.encode(), encrypted_file, key_buffer, salt, progress
    )
    print(f"\n✓ Encrypted to {encrypted_file}")
    print(f"  Encrypted size: {encrypted_file.stat().st_size} bytes\n")

    # Decrypt file to JSON
    print("Decrypting file to JSON...")
    # Read salt from file and derive key again
    file_salt = SecureEncryption.read_salt_from_file(encrypted_file)
    decrypt_key_buffer = SecureEncryption.derive_key(password, file_salt)
    decrypted_json = SecureEncryption.decrypt_file(
        encrypted_file, decrypt_key_buffer, progress
    )
    print("\n✓ Decrypted JSON string")

    # Parse and verify
    decrypted_data = json.loads(decrypted_json)

    assert decrypted_data == test_data
    if decrypted_data == test_data:
        print("\n✓ SUCCESS: Decrypted data matches original!")
        print(f"\nDecrypted data has {len(decrypted_data['pages'])} pages")
        print(f"First page title: '{decrypted_data['pages'][0]['title']}'")
    else:
        print("\n✗ ERROR: Decrypted data does not match!")

    # Clean up
    encrypted_file.unlink()

    print("\n=== Test completed ===")

    # Example: Wrong password
    print("\n=== Testing wrong password ===")
    test_json = json.dumps({"test": "data"})
    test_salt = secrets.token_bytes(SecureEncryption.SALT_SIZE)
    test_key_buffer = SecureEncryption.derive_key("correct_password", test_salt)
    SecureEncryption.encrypt_bytes_to_file(
        test_json.encode(), Path("test.enc"), test_key_buffer, test_salt
    )

    try:
        wrong_salt = SecureEncryption.read_salt_from_file(Path("test.enc"))
        wrong_key_buffer = SecureEncryption.derive_key("wrong_password", wrong_salt)
        _ = SecureEncryption.decrypt_file(Path("test.enc"), wrong_key_buffer)
        print("✗ ERROR: Should have failed with wrong password!")
        assert False
    except ValueError as e:
        assert True
        print(f"✓ Correctly rejected wrong password: {e}")

    Path("test.enc").unlink()
