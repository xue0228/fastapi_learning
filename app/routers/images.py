import datetime
import os
from typing import List, Union
from io import BytesIO
from enum import Enum

from base64 import b64encode, b64decode
from fastapi import Query, Response, APIRouter, Depends, File, UploadFile, Body, HTTPException, status, Path, Form
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.sql import and_
from sqlalchemy.engine.result import RowProxy
from PIL import Image

from app.dbs.base import aio_db
from app.dbs.tables import images, user_image
from app.routers.auth import get_current_user
from app.routers.users import UserOut
from app.settings import UPLOAD_PATH, AES_KEY
from app.utils import time_to_str, encrypt_by_aes, decrypt_by_aes, get_dirname_from_datetime
from app.utils import read_file, save_file, is_image, get_md5_hash

router = APIRouter(
    prefix='/api/v1/images',
    tags=['图片'],
    responses={404: {'description': '没有找到该图片'}}
)


class ImageOut(BaseModel):
    image_id: int
    image_hash_name: str
    is_private: bool
    created_time: datetime.datetime
    updated_time: datetime.datetime
    user_id: int
    private_url: str
    public_url: str = ''


class OrderBy(str, Enum):
    updated_time = 0
    created_time = 1


class Filter(str, Enum):
    all = 0
    private = 1
    public = 2


def get_image_return(image_db: RowProxy, user_image_db: RowProxy) -> dict:
    # 合并图片表及用户-图片关系表中数据
    res = dict(image_db)
    res.update(dict(user_image_db))

    # 添加图片url信息
    res.update({'private_url': router.prefix + '/private/' + str(image_db.image_id)})
    if not user_image_db.is_private:
        time = time_to_str(user_image_db.updated_time)
        key = '.'.join([time, str(image_db.image_id), str(user_image_db.user_id)])
        key = encrypt_by_aes(key.encode('utf8'), AES_KEY)
        key = b64encode(key).decode('utf8')
        public_url = router.prefix + '/public/' + image_db.image_hash_name + '?key=' + key
        res.update({'public_url': public_url})
    return res


def get_image_path(image_db: RowProxy) -> str:
    return os.path.join(
        UPLOAD_PATH,
        'image',
        get_dirname_from_datetime(image_db.image_created_time),
        image_db.image_hash_name
    )


def get_thumb_image_path(image_db: RowProxy) -> str:
    return os.path.join(
        UPLOAD_PATH,
        'image',
        'thumb',
        os.path.splitext(image_db.image_hash_name)[0] + '.jpeg'
    )


def get_compress_image_path(image_db: RowProxy) -> str:
    return os.path.join(
        UPLOAD_PATH,
        'image',
        'compress',
        os.path.splitext(image_db.image_hash_name)[0] + '.jpeg'
    )


async def generate_thumb_image(image_path: str, thumb_image_path: str) -> None:
    if not os.path.exists(thumb_image_path):
        image = await read_file(image_path)
        image = Image.open(BytesIO(image)).convert('RGB')
        image.thumbnail((128, 128))
        thumb_image = BytesIO()
        image.save(thumb_image, format='JPEG')
        await save_file(thumb_image.getvalue(), thumb_image_path)


async def generate_compress_image(
        image_path: str,
        compress_image_path: str,
        size: int = 500,
        quality: int = 90,
        step: int = 5,
) -> None:
    if not os.path.exists(compress_image_path):
        image = await read_file(image_path)
        o_size = len(image) / 1024
        if o_size <= size:
            os.symlink(image_path, compress_image_path)
            return
        while o_size > size:
            compress_image = BytesIO()
            im = Image.open(BytesIO(image)).convert('RGB')
            im.save(compress_image, format='JPEG', quality=quality)
            compress_image = compress_image.getvalue()
            if quality - step < 0:
                break
            quality -= step
            o_size = len(compress_image) / 1024
        await save_file(compress_image, compress_image_path)


@router.get('/', response_model=List[ImageOut])
async def get_images(
        user: UserOut = Depends(get_current_user),
        ascending: bool = False,
        limit: int = Query(10, gt=0, le=100),
        page: int = Query(1, gt=0),
        order_by: OrderBy = Query(0),
        filter: Filter = Query(0),
):
    query = user_image.select()
    if filter == Filter.private:
        query = query.where(and_(
            user_image.c.user_id == user.user_id,
            user_image.c.is_private == True,
        ))
    elif filter == Filter.public:
        query = query.where(and_(
            user_image.c.user_id == user.user_id,
            user_image.c.is_private == False,
        ))
    elif filter == Filter.all:
        query = query.where(user_image.c.user_id == user.user_id)
    if order_by == OrderBy.updated_time:
        if ascending:
            query = query.order_by(user_image.c.updated_time.asc())
        else:
            query = query.order_by(user_image.c.updated_time.desc())
    elif order_by == OrderBy.created_time:
        if ascending:
            query = query.order_by(user_image.c.created_time.asc())
        else:
            query = query.order_by(user_image.c.created_time.desc())
    query = query.limit(limit).offset((page - 1) * limit)

    async with aio_db as db:
        user_image_dbs = await db.fetch_all(query)
        res = []
        for user_image_db in user_image_dbs:
            image_db = await db.fetch_one(images.select().where(
                images.c.image_id == user_image_db.image_id
            ))
            res.append(get_image_return(image_db, user_image_db))
    return res


@router.get('/private/{image_id}', description='获取私人图片数据')
async def get_private_image(
        image_id: int, user: UserOut = Depends(get_current_user),
        thumb: bool = False,
        compress: bool = True,
):
    async with aio_db as db:
        # 判断该用户是否存储有该id图片
        if await db.fetch_one(user_image.select().where(and_(
            user_image.c.image_id == image_id,
            user_image.c.user_id == user.user_id
        ))) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail='No such image'
            )

        # 获取数据库中该图片信息
        image_db = await db.fetch_one(images.select().where(
            images.c.image_id == image_id
        ))

    # 图片存储地址
    image_path = get_image_path(image_db)

    if thumb:
        thumb_image_path = get_thumb_image_path(image_db)
        await generate_thumb_image(image_path, thumb_image_path)
        return FileResponse(thumb_image_path)

    if compress:
        compress_image_path = get_compress_image_path(image_db)
        await generate_compress_image(image_path, compress_image_path)
        return FileResponse(compress_image_path)

    return FileResponse(image_path)


@router.get('/public/{image_hash_name}', description='获取公开图片数据')
async def get_public_image(
        key: str,
        image_hash_name: str = Path(
            ...,
            title='图片名称',
            regex=r'^[a-zA-Z0-9]{32}\.[a-zA-Z0-9]{1,7}$',
        ),
        thumb: bool = False,
        compress: bool = True,
):
    image_hash_name = image_hash_name.lower()
    # 定义无图片错误
    no_image_exception = HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail='No such image'
            )

    # aes解密key值
    try:
        key = b64decode(key.encode('utf8'))
        key = decrypt_by_aes(key, AES_KEY).decode('utf8')
    except Exception:
        raise no_image_exception

    # 切分key值
    key = key.split('.')
    if len(key) != 3:
        raise no_image_exception
    time, image_id, user_id = key
    try:
        image_id = int(image_id)
        user_id = int(user_id)
    except Exception:
        raise no_image_exception

    # 与数据库中数据对比验证
    async with aio_db as db:
        image_db = await db.fetch_one(images.select().where(
            images.c.image_hash_name == image_hash_name
        ))
        if image_db is None:
            raise no_image_exception
        user_image_db = await db.fetch_one(user_image.select().where(and_(
            user_image.c.image_id == image_id, user_image.c.user_id == user_id
        )))
        if user_image_db is None:
            raise no_image_exception
        if time_to_str(user_image_db.updated_time) != time:
            raise no_image_exception

    # 图片存储地址
    image_path = get_image_path(image_db)

    if thumb:
        thumb_image_path = get_thumb_image_path(image_db)
        await generate_thumb_image(image_path, thumb_image_path)
        return FileResponse(thumb_image_path)

    if compress:
        compress_image_path = get_compress_image_path(image_db)
        await generate_compress_image(image_path, compress_image_path)
        return FileResponse(compress_image_path)

    return FileResponse(image_path)


@router.post('/', response_model=ImageOut, description='用户上传图片接口')
async def upload_image(
        user: UserOut = Depends(get_current_user),
        upload_file: UploadFile = File(...),
        private: bool = Body(False),
):
    # 读取上传的数据
    data = upload_file.file.read()
    # 校验文件格式是否为图片
    suffix = is_image(data)
    if not suffix:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail='The type of Uploaded file is not image',
        )

    # 用hash值和文件后缀生成文件名
    hash_name = get_md5_hash(data) + suffix
    # 获取当前utc时间
    utc_now = datetime.datetime.utcnow()

    async with aio_db as db:
        # 查找数据库中有无相同图片
        image_db = await db.fetch_one(images.select().where(images.c.image_hash_name == hash_name))
        # 数据库中没有该图片时保存数据到服务器并将相关信息写入数据库
        if image_db is None:
            # 图片保存相对路径
            save_path = os.path.join(get_dirname_from_datetime(utc_now), hash_name)
            # 保存图片到绝对路径
            await save_file(data, os.path.join(UPLOAD_PATH, 'image', save_path))

            query = images.insert()
            values = {
                'image_hash_name': hash_name,
                'image_created_time': utc_now,
            }
            image_id = await db.execute(query=query, values=values)
            image_db = await db.fetch_one(images.select().where(images.c.image_id == image_id))

        # 在数据库中查找该用户是否上传过该图片
        if await db.fetch_one(user_image.select().where(and_(
            user_image.c.image_id == image_db.image_id, user_image.c.user_id == user.user_id
        ))) is not None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail='The uploaded image has been existed',
            )

        # 更改用户-图片关系表
        user_image_id = await db.execute(
            query=user_image.insert(),
            values={
                'user_id': user.user_id,
                'image_id': image_db.image_id,
                'is_private': private,
                'created_time': utc_now,
                'updated_time': utc_now,
            }
        )
        user_image_db = await db.fetch_one(user_image.select().where(user_image.c.user_image_id == user_image_id))

    return get_image_return(image_db, user_image_db)


@router.put('/{image_id}', response_model=ImageOut, description='修改图片相关信息')
async def modify_image(
        image_id: int,
        private: bool = Form(...),
        user: UserOut = Depends(get_current_user),
):
    async with aio_db as db:
        # 判断该用户是否存储有该id图片
        user_image_db = await db.fetch_one(user_image.select().where(and_(
                user_image.c.image_id == image_id,
                user_image.c.user_id == user.user_id
        )))
        if user_image_db is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail='No such image'
            )

        # 修改数据库中相关数据
        user_image_id = await db.execute(
            query=user_image.update().where(user_image.c.user_image_id == user_image_db.user_image_id),
            values={
                'is_private': private,
                'updated_time': datetime.datetime.utcnow(),
            }
        )

        # 查询两表中的数据
        image_db = await db.fetch_one(images.select().where(images.c.image_id == image_id))
        user_image_db = await db.fetch_one(user_image.select().where(user_image.c.user_image_id == user_image_id))

    return get_image_return(image_db, user_image_db)


@router.delete(
    '/{image_id}',
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    description='删除指定图片',
)
async def delete_image(
        image_id: int,
        user: UserOut = Depends(get_current_user),
):
    async with aio_db as db:
        # 判断该用户是否存储有该id图片
        user_image_db = await db.fetch_one(user_image.select().where(and_(
            user_image.c.image_id == image_id,
            user_image.c.user_id == user.user_id
        )))
        if user_image_db is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail='No such image'
            )

        user_image_dbs = await db.fetch_all(user_image.select().where(
            user_image.c.image_id == image_id
        ))

        transaction = await aio_db.transaction()
        try:
            # await transaction.start()
            await db.execute(user_image.delete().where(
                user_image.c.user_image_id == user_image_db.user_image_id
            ))
            if len(user_image_dbs) == 1:
                image_db = await db.fetch_one(images.select().where(
                    images.c.image_id == image_id
                ))

                image_path = get_image_path(image_db)
                thumb_image_path = get_thumb_image_path(image_db)
                compress_image_path = get_compress_image_path(image_db)

                await db.execute(images.delete().where(
                    images.c.image_id == image_id
                ))

                if os.path.exists(image_path):
                    os.remove(image_path)
                if os.path.exists(thumb_image_path):
                    os.remove(thumb_image_path)
                if os.path.exists(compress_image_path):
                    os.remove(compress_image_path)
        except Exception:
            await transaction.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        else:
            await transaction.commit()
