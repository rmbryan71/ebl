from db import DATABASE_URL, using_postgres


def main():
    if using_postgres():
        print("Database: Postgres")
        print(f"DATABASE_URL: {DATABASE_URL}")
    else:
        print("Database: SQLite (ebl.db)")


if __name__ == "__main__":
    main()
