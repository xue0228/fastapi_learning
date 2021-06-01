import time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from pymysql.err import IntegrityError

from app.middlewares import ProcessTimeHeaderMiddleware
from app.routers import images, auth, users
from app.databases.base import aio_db
from app.errors import *


app = FastAPI(
    title='xyw-api',
    description='个人api接口',
    version='0.0.1',
)
app.include_router(images.router)
app.include_router(users.router)
app.include_router(auth.router)

# response的header中添加X-Process-Time字段
app.add_middleware(ProcessTimeHeaderMiddleware)

# 大于一定体积的数据自动压缩传送
app.add_middleware(GZipMiddleware, minimum_size=500)

# 允许跨域
origins = ['*']
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(HasUsedException, has_used_exception_handler)
# app.add_exception_handler(IntegrityError, integrity_error_handler)


@app.get("/")
async def root():
    # time.sleep(1)
    # async with aio_db as db:
    #     print(db)
    # raise LengthException('xue', None, 10)
    raise HasUsedException('xue')
    # return {"message": "Hello World"}
