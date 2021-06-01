import sqlalchemy as sa

from app.databases.base import metadata


users = sa.Table(
    'users',
    metadata,
    sa.Column('user_id', sa.BIGINT, sa.Sequence('user_id_seq'), primary_key=True),
    sa.Column('user_name', sa.String(20), nullable=False, unique=True, index=True),
    sa.Column('user_password', sa.String(60), nullable=False),
    sa.Column('user_nickname', sa.String(20), nullable=False, unique=True, index=True),
    sa.Column('user_registration_time', sa.DateTime, nullable=False),
    sa.Column('user_email', sa.String(30), nullable=False, unique=True, index=True),
    sa.Column('user_telephone_number', sa.String(20), nullable=False, unique=True, index=True),
)

images = sa.Table(
    'images',
    metadata,
    sa.Column('image_id', sa.BIGINT, sa.Sequence('image_id_seq'), primary_key=True),
    sa.Column('image_hash_name', sa.String(40), nullable=False, unique=True, index=True),
    sa.Column('image_created_time', sa.DateTime, nullable=False),
)

user_image = sa.Table(
    'user_image',
    metadata,
    sa.Column('user_image_id', sa.BIGINT, sa.Sequence('user_image_id_seq'), primary_key=True),
    sa.Column('user_id', None, sa.ForeignKey('users.user_id'), nullable=False),
    sa.Column('image_id', None, sa.ForeignKey('images.image_id'), nullable=False),
    sa.Column('is_private', sa.Boolean, default=False),
    sa.Column('created_time', sa.DateTime, nullable=False),
    sa.Column('updated_time', sa.DateTime, nullable=False),
)
