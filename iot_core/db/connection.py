import pymysql
from iot_core.core.config import load_config

def get_connection():
    cfg = load_config()["database"]

    return pymysql.connect(
        host=cfg["host"],
        port=int(cfg.get("port", 3306)),
        user=cfg["user"],
        password=cfg["password"],
        database=cfg["name"],
        autocommit=True,
        charset="utf8mb4",
    )
