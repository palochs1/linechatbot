from cryptography.fernet import Fernet
import base64

key = Fernet.generate_key()
cipher_suite = Fernet(key)

def encrypt_data(data, key):
    cipher_suite = Fernet(key)
    return base64.urlsafe_b64encode(cipher_suite.encrypt(data.encode())).decode()

def decrypt_data(data, key):
    cipher_suite = Fernet(key)
    return cipher_suite.decrypt(base64.urlsafe_b64decode(data)).decode()
