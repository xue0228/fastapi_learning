import datetime

from pydantic import Field, BaseModel
from fastapi import APIRouter, HTTPException, Depends

from app.errors import *
from app.dbs.base import aio_db
from app.dbs.tables import users
from app.utils import pwd_context
from app.routers.auth import get_current_user


router = APIRouter(
    prefix='/api/v1/users',
    tags=['用户']
)


class UserIn(BaseModel):
    name: str = Field(
        ...,
        min_length=3,
        max_length=20,
        title='用户名',
        regex=r'^[a-z0-9A-Z][a-z0-9A-Z_]{2,19}$',
    )
    password: str = Field(
        ...,
        min_length=8,
        max_length=20,
        title='用户密码',
        regex=r'^[a-z0-9A-Z~!@#$%^&*()_+{}|":?><`\-=\[\]\\\';/.,]{8,20}$',
    )
    nickname: str = Field(
        ...,
        min_length=1,
        max_length=20,
        title='用户昵称',
    )
    telephone_number: str = Field(
        ...,
        min_length=11,
        max_length=11,
        title='用户手机号码',
        regex=r'^[1-9][0-9]{10}$',
    )
    email: str = Field(
        ...,
        title='用户邮箱地址',
        regex=r'^[a-zA-Z0-9_-]+@[a-zA-Z0-9_-]+(\.[a-zA-Z0-9_-]+)+$',
    )


class UserOut(BaseModel):
    user_id: int
    user_name: str
    user_nickname: str
    user_telephone_number: int
    user_email: str
    user_registration_time: datetime.datetime


@router.post('/', response_model=UserOut)
async def add_user(user: UserIn):
    async with aio_db as db:
        # 数据库unique参数校验
        if await db.fetch_one(users.select().where(users.c.user_name == user.name)) is not None:
            raise HasUsedException('name', user.name)
        if await db.fetch_one(users.select().where(users.c.user_nickname == user.nickname)) is not None:
            raise HasUsedException('nickname', user.nickname)
        if await db.fetch_one(users.select().where(users.c.user_email == user.email)) is not None:
            raise HasUsedException('email', user.email)
        if await db.fetch_one(users.select().where(users.c.user_telephone_number == user.telephone_number)) is not None:
            raise HasUsedException('telephone_number', user.telephone_number)

        # 向数据库中插入新用户信息
        query = users.insert()
        values = {
            'user_name': user.name,
            'user_password': pwd_context.hash(user.password),
            'user_nickname': user.nickname,
            'user_registration_time': datetime.datetime.utcnow(),
            'user_email': user.email,
            'user_telephone_number': user.telephone_number
        }
        user_id = await db.execute(query=query, values=values)
        user_db = await db.fetch_one(users.select().where(users.c.user_id == user_id))
    return dict(user_db)


@router.get('/me', response_model=UserOut)
async def get_user(user: UserOut = Depends(get_current_user)):
    return user
