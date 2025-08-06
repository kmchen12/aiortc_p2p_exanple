from cryptography.fernet import Fernet

key = Fernet.generate_key()
print("請將此金鑰貼入 caller.py 與 callee.py：")
print(key.decode())
