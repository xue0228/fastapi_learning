import sqlalchemy as sa
import databases

from app.settings import DATABASE_URL


metadata = sa.MetaData()

aio_db = databases.Database(DATABASE_URL, min_size=5, max_size=20)
