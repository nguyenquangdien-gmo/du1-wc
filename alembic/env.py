import os
from logging.config import fileConfig
from dotenv import load_dotenv

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Load environment variables
load_dotenv()

# Import your models
from database.database import Base
import database.models  # Quan trọng: Import models để Alembic nhận diện bảng

# values within the .ini file in use.
config = context.config

from sqlalchemy.engine import make_url

# Cập nhật URL từ biến môi trường
db_url = os.environ.get("DATABASE_URL")
if not db_url:
    raise ValueError("Alembic yêu cầu biến môi trường DATABASE_URL để thực hiện migrations.")

# Tự động sửa lỗi Driver
if db_url.startswith("mysql://"):
    db_url = db_url.replace("mysql://", "mysql+pymysql://", 1)

# Phân tích và làm sạch URL
url_obj = make_url(db_url)
query = dict(url_obj.query)
query.pop("ssl-mode", None)
query.pop("ssl_ca", None)
clean_url = str(url_obj._replace(query=query))

config.set_main_option("sqlalchemy.url", clean_url)

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
