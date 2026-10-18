from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser

from bson import ObjectId
import mongomock
from pymongo.errors import AutoReconnect
import pytest

from app import create_app
from app.db import get_db


class MarketPage(HTMLParser):
    """Inspect links and content without depending on the page's CSS classes."""

    def __init__(self, response):
        super().__init__()
        self.item_links = []
        self.images = []
        self.text_parts = []
        self.feed(response.get_data(as_text=True))

    @property
    def text(self):
        return "".join(self.text_parts)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        href = attrs.get("href", "")
        if tag == "a" and href.startswith("/items/") and ObjectId.is_valid(href[7:]):
            self.item_links.append(href)
        if tag == "img":
            self.images.append(attrs)

    def handle_data(self, data):
        self.text_parts.append(data)


@pytest.fixture
def marketplace():
    client = mongomock.MongoClient()
    app = create_app({
        "TESTING": True,
        "SECRET_KEY": "market-test-only-secret",
        "MONGODB_URI": "mongodb://localhost:27017",
        "MONGODB_DB": "test_market",
        "MONGO_CLIENT": client,
    })
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    owner = ObjectId()
    examples = (
        (1, "Desk lamp", "active", now),
        (2, "Course textbook", "active", now + timedelta(days=1)),
        (3, "Wireless keyboard", "active", now + timedelta(days=1)),
        (4, "Sold lamp", "sold", now + timedelta(days=2)),
        (5, "Deleted lamp", "deleted", now + timedelta(days=3)),
        (6, "Draft lamp", "draft", now + timedelta(days=4)),
    )
    documents = {}
    for suffix, title, status, created_at in examples:
        documents[title] = {
            "_id": ObjectId(f"{suffix:024x}"),
            "owner_id": owner,
            "title": title,
            "description": "Working lamp for a study desk\nPickup on campus.",
            "price": 12.5,
            "category": "Furniture",
            "condition": "Good",
            "image_url": "",
            "contact_info": "seller@example.edu\nMeet at the library.",
            "status": status,
            "created_at": created_at,
            "updated_at": created_at,
        }
    with app.app_context():
        get_db().items.insert_many(list(documents.values()))
    yield app, documents
    client.close()


def item_path(documents, title):
    return f"/items/{documents[title]['_id']}"


def test_browse_is_public_active_only_and_newest_first_with_stable_ties(marketplace):
    app, documents = marketplace
    response = app.test_client().get("/items")
    assert response.status_code == 200
    assert MarketPage(response).item_links == [
        item_path(documents, title)
        for title in ("Wireless keyboard", "Course textbook", "Desk lamp")
    ]
    assert b"$12.50" in response.data
    assert b"Furniture" in response.data and b"Good" in response.data
    assert b"No photo" in response.data
    assert b"Sold lamp" not in response.data
    assert b"Deleted lamp" not in response.data
    assert b"Draft lamp" not in response.data


def test_browse_empty_catalog_is_helpful(marketplace):
    app, _ = marketplace
    with app.app_context():
        get_db().items.update_many({}, {"$set": {"status": "sold"}})
    response = app.test_client().get("/items")
    assert response.status_code == 200
    assert b"No items are available right now" in response.data
    assert MarketPage(response).item_links == []


def test_active_detail_is_public_and_shows_listing_fields_and_contact(marketplace):
    app, documents = marketplace
    response = app.test_client().get(item_path(documents, "Desk lamp"))
    assert response.status_code == 200
    text = MarketPage(response).text
    for field in ("title", "description", "category", "condition", "contact_info"):
        assert documents["Desk lamp"][field] in text
    assert "$12.50" in text
    assert "No photo" in text


def test_sold_detail_is_labeled_and_hides_seller_contact(marketplace):
    app, documents = marketplace
    response = app.test_client().get(item_path(documents, "Sold lamp"))
    assert response.status_code == 200
    page = MarketPage(response)
    text = page.text
    assert "Sold lamp" in text
    assert "Sold" in [part.strip() for part in page.text_parts]
    assert "seller@example.edu" not in text
    assert "Meet at the library" not in text


def test_listing_image_is_used_on_browse_and_detail(marketplace):
    app, documents = marketplace
    image_url = "https://example.edu/images/lamp.jpg"
    with app.app_context():
        get_db().items.update_one(
            {"_id": documents["Desk lamp"]["_id"]}, {"$set": {"image_url": image_url}}
        )
    browser = app.test_client()
    for path in ("/items", item_path(documents, "Desk lamp")):
        response = browser.get(path)
        assert response.status_code == 200
        assert any(image.get("src") == image_url for image in MarketPage(response).images)


@pytest.mark.parametrize("item_id", ["example", "f" * 23, "g" * 24])
def test_invalid_detail_ids_return_friendly_404_without_database_access(marketplace, monkeypatch, item_id):
    app, _ = marketplace

    def unexpected_database_access():
        pytest.fail("An invalid item ID must be rejected before accessing MongoDB")

    monkeypatch.setattr("app.market.get_db", unexpected_database_access)
    response = app.test_client().get(f"/items/{item_id}")
    assert response.status_code == 404
    assert b"Item not found" in response.data


@pytest.mark.parametrize("title", [None, "Deleted lamp", "Draft lamp"])
def test_missing_deleted_and_unsupported_items_return_friendly_404(marketplace, title):
    app, documents = marketplace
    path = item_path(documents, title) if title else f"/items/{ObjectId()}"
    response = app.test_client().get(path)
    assert response.status_code == 404
    assert b"Item not found" in response.data
    assert b"seller@example.edu" not in response.data
    if title:
        assert title.encode() not in response.data


@pytest.mark.parametrize("path_kind", ["browse", "detail"])
def test_database_failure_returns_503_without_private_details(marketplace, monkeypatch, path_kind):
    app, documents = marketplace

    def unavailable(*args, **kwargs):
        raise AutoReconnect("private database connection detail")

    with app.app_context():
        monkeypatch.setattr(get_db().items, "find" if path_kind == "browse" else "find_one", unavailable)
    path = "/items" if path_kind == "browse" else item_path(documents, "Desk lamp")
    response = app.test_client().get(path)
    assert response.status_code == 503
    assert b"temporarily unavailable" in response.data
    assert b"private database connection detail" not in response.data
    assert b"No items are available" not in response.data
    assert b"Item not found" not in response.data


def test_cursor_failure_during_browse_does_not_display_partial_or_empty_results(marketplace, monkeypatch):
    app, documents = marketplace

    class BrokenCursor:
        def sort(self, *args, **kwargs):
            return self

        def __iter__(self):
            yield documents["Desk lamp"]
            raise AutoReconnect("private cursor connection detail")

    with app.app_context():
        monkeypatch.setattr(get_db().items, "find", lambda *args, **kwargs: BrokenCursor())
    response = app.test_client().get("/items")
    assert response.status_code == 503
    assert b"temporarily unavailable" in response.data
    assert b"private cursor connection detail" not in response.data
    assert b"No items are available" not in response.data
    assert MarketPage(response).item_links == []


def test_listing_text_is_escaped_and_multiline_content_is_preserved(marketplace):
    app, documents = marketplace
    title = '<script>alert("title")</script>'
    description = '<img src=x onerror="alert(1)">\nPickup after class.'
    contact = '<script>alert("contact")</script>\nContact by campus email.'
    with app.app_context():
        get_db().items.update_one({"_id": documents["Desk lamp"]["_id"]}, {"$set": {
            "title": title, "description": description, "contact_info": contact,
        }})
    browser = app.test_client()
    for path in ("/items", item_path(documents, "Desk lamp")):
        response = browser.get(path)
        assert response.status_code == 200
        assert b"<script>" not in response.data
        assert b"<img src=x" not in response.data
        assert b"&lt;script&gt;" in response.data
        page = MarketPage(response)
        assert title in page.text
        assert description in page.text
    assert contact in MarketPage(browser.get(item_path(documents, "Desk lamp"))).text


def test_search_result_opens_real_detail_and_public_reads_do_not_change_items(marketplace):
    app, documents = marketplace
    with app.app_context():
        before = list(get_db().items.find().sort("_id", 1))
    browser = app.test_client()
    search_response = browser.get("/search?q=Desk+lamp")
    assert search_response.status_code == 200
    links = MarketPage(search_response).item_links
    assert links == [item_path(documents, "Desk lamp")]
    detail_response = browser.get(links[0])
    assert detail_response.status_code == 200
    assert b"seller@example.edu" in detail_response.data
    assert browser.get("/items").status_code == 200
    assert browser.get(item_path(documents, "Sold lamp")).status_code == 200
    assert browser.get(item_path(documents, "Deleted lamp")).status_code == 404
    with app.app_context():
        assert list(get_db().items.find().sort("_id", 1)) == before
