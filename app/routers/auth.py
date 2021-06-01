from datetime import datetime, timedelta
from typing import Optional

from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, status, Query
from jose import JWTError, jwt
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

from app.settings import SECRET_KEY, JWT_ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES
from app.dbs.base import aio_db
from app.dbs.tables import users
from app.utils import pwd_context


router = APIRouter(
    prefix='/api/v1/auth',
    tags=['验证']
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl='api/v1/auth')


class Token(BaseModel):
    access_token: str
    token_type: str


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """
    生成JWT令牌
    :param data: 需要签名的字典数据
    :param expires_delta: 令牌有效时间
    :return:
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt


async def get_current_user(token: str = Depends(oauth2_scheme)):
    """
    验证jwt令牌，获取用户信息
    :param token:
    :return:
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token, SECRET_KEY, algorithms=[JWT_ALGORITHM],
            options={'verify_sub': False}
        )
        user_id: int = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError as e:
        print(repr(e))
        raise credentials_exception
    async with aio_db as db:
        user = await db.fetch_one(users.select().where(users.c.user_id == user_id))
    if user is None:
        raise credentials_exception
    return user


@router.post('/', response_model=Token)
async def get_jwt(
        form_data: OAuth2PasswordRequestForm = Depends(),
        expires: int = Query(ACCESS_TOKEN_EXPIRE_MINUTES, gt=0, le=30*24*60)
):
    # 在数据库中查询该用户
    async with aio_db as db:
        user = await db.fetch_one(users.select().where(users.c.user_name == form_data.username))
    # 数据库中无此用户时返回404
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No such username",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # 验证密码正确性
    if pwd_context.verify(form_data.password, user.user_password):
        access_token = create_access_token(
            data={'sub': user.user_id}, expires_delta=timedelta(minutes=expires)
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return {"access_token": access_token, "token_type": "bearer"}
