from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization
import json
import base64
import datetime

# Generate a private/public key pair (run this once and save the keys)
private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
public_key = private_key.public_key()

# Save the private key to a file (keep this secure!)
with open("private_key.pem", "wb") as f:
    f.write(private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    ))

# Save the public key to a file (this will be included in the app)
with open("public_key.pem", "wb") as f:
    f.write(public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo  # Updated to SubjectPublicKeyInfo
    ))

def generate_license(user_id: str, days_valid: int) -> tuple[str, str]:
    """
    Generate a signed license key for a user.
    
    Args:
        user_id (str): Unique identifier for the user or organization.
        days_valid (int): Number of days the license is valid for.
    
    Returns:
        tuple: (license_data_base64, signature_base64)
    """
    # Create license data
    expiration_date = (datetime.datetime.now() + datetime.timedelta(days=days_valid)).isoformat()
    license_data = {
        "user_id": user_id,
        "expiration_date": expiration_date,
        "product": "SaveMyCell"
    }
    license_data_json = json.dumps(license_data).encode("utf-8")
    license_data_base64 = base64.b64encode(license_data_json).decode("utf-8")

    # Sign the license data with the private key
    signature = private_key.sign(
        license_data_json,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.MAX_LENGTH
        ),
        hashes.SHA256()
    )
    signature_base64 = base64.b64encode(signature).decode("utf-8")

    return license_data_base64, signature_base64

# Example: Generate a license for a user
user_id = "corporate_user_123"
days_valid = 365  # License valid for 1 year
license_data, signature = generate_license(user_id, days_valid)
print(f"License Data (Base64): {license_data}")
print(f"Signature (Base64): {signature}")

# Save the license to a file for the user
with open(f"license_{user_id}.lic", "w") as f:
    f.write(f"{license_data}\n{signature}")