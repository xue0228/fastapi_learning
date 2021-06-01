import os


# DATABASE_URL = r'mysql://root:Xue19891210@localhost:3306/xue-api'
# MIGRATION_URL = r'mysql://root:Xue19891210@localhost:3306/xue-api'
DATABASE_URL = r'mysql://root:yaxing@localhost:3306/xue-api'
MIGRATION_URL = r'mysql+mysqlconnector://root:yaxing@localhost:3306/xue-api'

SECRET_KEY = '65de8f8e11a1437465154534d0a746b83a1cd341538a2a2fc5a751e809a0a2ca'
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 24*60

BASE_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_PATH = os.path.join(BASE_PATH, 'upload')

AES_KEY = b'\xf9\x10\xa60%M\xc3\x07\x0b#\xa7\xd6\xebY\x18V'
