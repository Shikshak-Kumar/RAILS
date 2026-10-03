from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

try:
    import snowflake.connector
    HAVE_SNOWFLAKE = True
except ImportError:
    HAVE_SNOWFLAKE = False


def get_snowflake_connection() -> Any | None:
    if not HAVE_SNOWFLAKE:
        logger.warning("snowflake-connector-python is not installed.")
        return None

    connection_name = os.getenv("SNOWFLAKE_CONNECTION_NAME", "NZ32482")
    user = os.getenv("SNOWFLAKE_USER")
    password = os.getenv("SNOWFLAKE_PASSWORD")
    account = os.getenv("SNOWFLAKE_ACCOUNT")
    role = os.getenv("SNOWFLAKE_ROLE", "ACCOUNTADMIN")
    warehouse = os.getenv("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH")
    database = os.getenv("SNOWFLAKE_DATABASE", "RAILS_DB")
    schema = os.getenv("SNOWFLAKE_SCHEMA", "REGULATORY")

    try:
        if user and (password or os.getenv("SNOWFLAKE_PRIVATE_KEY_FILE")):
            conn = snowflake.connector.connect(
                user=user,
                password=password,
                account=account,
                role=role,
                warehouse=warehouse,
                database=database,
                schema=schema,
            )
            return conn
        else:
            conn = snowflake.connector.connect(
                connection_name=connection_name,
                database=database,
                schema=schema,
                warehouse=warehouse,
            )
            return conn
    except Exception as e:
        logger.error(f"Failed to connect to Snowflake: {e}")
        return None
