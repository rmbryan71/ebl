import os

import pytest

from app import app


@pytest.fixture
def client():
    app.config.update({"TESTING": True})
    with app.test_client() as client:
        yield client


def test_login_page_loads(client):
    resp = client.get("/login")
    assert resp.status_code == 200


def test_rules_page_loads(client):
    resp = client.get("/rules")
    assert resp.status_code == 200


def test_news_page_loads(client):
    resp = client.get("/news")
    assert resp.status_code == 200


def test_audit_redirects_to_login(client):
    resp = client.get("/audit")
    assert resp.status_code in {302, 401}
    if resp.status_code == 302:
        assert "/login" in resp.headers.get("Location", "")


def test_roster_requires_db(client):
    if not os.getenv("DATABASE_URL"):
        pytest.skip("DATABASE_URL not set.")
    resp = client.get("/")
    assert resp.status_code == 200
