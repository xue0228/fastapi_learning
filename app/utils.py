import hashlib
import datetime
import os
import re
import random
import base64
import math
from typing import Union
from io import BytesIO

import aiofiles
from PIL import Image
from passlib.context import CryptContext
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
from Crypto.Util import Padding


# 密码文本加密器
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def encrypt_by_aes(data: bytes, key: bytes):
    cipher = AES.new(key, AES.MODE_ECB)
    return cipher.encrypt(Padding.pad(data, len(key)))


def decrypt_by_aes(data: bytes, key: bytes):
    cipher = AES.new(key, AES.MODE_ECB)
    return Padding.unpad(cipher.decrypt(data), len(key))


def generate_aes_key(bit_num: int) -> bytes:
    """
    获取指定位数随机bytes
    :param bit_num:
    :return:
    """
    return get_random_bytes(bit_num)


def time_to_str(time: datetime.datetime) -> str:
    """
    datetime格式转为string
    :param time:
    :return:
    """
    return str(round(time.timestamp() * 1000))


async def read_file(path: str) -> bytes:
    """
    异步读取文件数据
    :param path:
    :return:
    """
    async with aiofiles.open(path, 'rb') as f:
        return await f.read()


async def save_file(data: bytes, path: str) -> None:
    """
    保存数据到指定文件地址
    :param data:
    :param path:
    :return:
    """
    dirpath, filename = os.path.split(path)
    if not os.path.exists(dirpath):
        os.makedirs(dirpath)
    async with aiofiles.open(path, 'wb') as f:
        await f.write(data)


def create_random_secret_key():
    """
    生成随机32位16进制数密钥
    :return:
    """
    return ''.join([hex(random.randint(0, 255))[2:].zfill(2) for i in range(32)])


def is_image(data: bytes) -> Union[bool, str]:
    """
    判断字节流是否为图片格式
    :param data: 图片数据
    :return: 图片后缀
    """
    try:
        return '.' + Image.open(BytesIO(data)).format.lower()
    except IOError:
        return False


def get_md5_hash(data: bytes) -> str:
    """
    使用md5算法获取字节流hash文本
    :param data: 数据
    :return:
    """
    return hashlib.md5(data).hexdigest()


def get_dirname_from_datetime(date: datetime.datetime) -> str:
    """
    根据时间戳生成年/月/日形式的路径地址
    :param date:
    :return:
    """
    year = str(date.year)
    month = str(date.month).zfill(2)
    day = str(date.day).zfill(2)
    return os.path.join(year, month, day)


if __name__ == '__main__':
    # print(create_random_secret_key())
    # print(re.match(r'^[a-zA-Z0-9]{32}\.[a-zA-Z0-9]{1,7}$', '076e3caed758a1718c91a0e9cae3368f.444jpeg'))
    # print(datetime.datetime.utcnow().timestamp() * 1000)
    # print(time_to_str(datetime.datetime.utcnow()))
    # generate_aes_key(16)
    from app.settings import AES_KEY
    # x = (time_to_str(datetime.datetime.utcnow()) + '.46465465.654654646444444444444444444444444444444444444444444444444444444444444444444444444444444444444444444444444444444444445').encode('utf8')
    # y = decrypt_by_aes(encrypt_by_aes(x, AES_KEY), AES_KEY)
    # print(base64.b64encode(x).decode('utf8'))
    x = base64.b16encode(AES_KEY).decode('utf8')
    print(x)
