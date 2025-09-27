import orjson
import msgpack
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import ciphers, padding
from cryptography.hazmat.primitives.ciphers import algorithms, modes

def decrypt_aes_cbc_pkcs7(encrypted_data: bytes, key: bytes, iv: bytes) -> bytes:
    """
    使用 AES/CBC/PKCS7 同步解密数据。
    """
    cipher = ciphers.Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    decrypted_padded_data = decryptor.update(encrypted_data) + decryptor.finalize()

    unpadder = padding.PKCS7(algorithms.AES.block_size).unpadder()
    unpadded_data = unpadder.update(decrypted_padded_data) + unpadder.finalize()

    return unpadded_data

async def decrypt_and_parse_bin_file(
        encrypted_bytes: bytes,
        aes_key: bytes,
        aes_iv: bytes
) -> dict:
    """
    主函数：解密 .bin 文件内容并使用 MessagePack 解析。
    返回解析后的 Python 字典。
    """
    try:
        decrypted_bytes = decrypt_aes_cbc_pkcs7(encrypted_bytes, aes_key, aes_iv)

        parsed_data = msgpack.unpackb(decrypted_bytes, raw=False)

        return parsed_data
    except Exception as e:
        raise ValueError(f"解密或解析数据失败: {e}")