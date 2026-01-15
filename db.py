import os
import sqlite3

import psycopg
from psycopg.rows import dict_row


DB_PATH = "ebl.db"
DATABASE_URL = os.getenv("DATABASE_URL")


def get_connection(db_path=DB_PATH):
    if DATABASE_URL:
        return psycopg.connect(DATABASE_URL, row_factory=dict_row)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def param_placeholder():
    return "%s" if DATABASE_URL else "?"


def using_postgres():
    return bool(DATABASE_URL)
