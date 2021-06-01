from PIL import Image
from app.utils import *


with open('1.png', 'rb') as f:
    data = f.read()
    print(is_image(data))
    hash = get_md5_hash(data)
    print(len(hash))
    print(get_dirname_from_datetime(datetime.datetime.utcnow()))
