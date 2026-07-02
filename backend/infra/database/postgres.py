from psycopg2 import pool
from dotenv import load_dotenv
import os


load_dotenv()

connection_pool = pool.SimpleConnectionPool(
    minconn=int(os.getenv("POSTGRES_POOL_MIN", "1")),
    maxconn=int(os.getenv("POSTGRES_POOL_MAX", "10")),
    host=os.environ["POSTGRES_HOST"],
    database=os.environ["POSTGRES_DB"],
    user=os.environ["POSTGRES_USER"],
    password=os.environ["POSTGRES_PASSWORD"],
    port=int(os.getenv("POSTGRES_PORT", "5432")),
    connect_timeout=10
)

def get_conn():
    return connection_pool.getconn()

def release_conn(conn):
    connection_pool.putconn(conn)
