from pymysql.err import IntegrityError
from fastapi import Request, status
from fastapi.responses import JSONResponse


class HasUsedException(Exception):
    """
    参数值与数据库中数据重复，已被使用
    """
    def __init__(self, name, value=None):
        self.name = name
        self.value = value


async def has_used_exception_handler(request: Request, exc: HasUsedException):
    if exc.value is not None:
        message = f'"{exc.value}",the value of param "{exc.name}",has been used'
    else:
        message = f'The value of param "{exc.name}" has been used'
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={'detail': message}
    )


async def integrity_error_handler(request: Request, exc: IntegrityError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={'detail': str(exc)}
    )
