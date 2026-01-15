from db import DATABASE_URL


def main():
    if not DATABASE_URL:
        raise SystemExit("DATABASE_URL is not set.")
    print("Database: Postgres")
    print(f"DATABASE_URL: {DATABASE_URL}")


if __name__ == "__main__":
    main()
