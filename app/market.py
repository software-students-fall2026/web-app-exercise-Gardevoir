"""Public browsing and item details for the campus marketplace."""

from flask import Blueprint, current_app, render_template, url_for
from pymongo.errors import PyMongoError

from app.db import get_db, parse_object_id
from app.item_data import public_item

market = Blueprint("market", __name__)


@market.get("/items")
def items():
    try:
        documents = get_db().items.find({"status": "active"}).sort(
            [("created_at", -1), ("_id", -1)]
        )
        listings = [public_item(document) for document in documents]
    except PyMongoError:
        current_app.logger.exception("Unable to load marketplace items")
        return render_template(
            "market/items.html",
            items=[],
            service_error="The marketplace is temporarily unavailable. Please try again.",
        ), 503

    return render_template("market/items.html", items=listings, service_error=None)


@market.get("/items/<item_id>")
def item_detail(item_id):
    object_id = parse_object_id(item_id)
    if object_id is None:
        return _item_not_found()

    try:
        document = get_db().items.find_one(
            {"_id": object_id, "status": {"$in": ["active", "sold"]}}
        )
    except PyMongoError:
        current_app.logger.exception("Unable to load marketplace item details")
        return render_template(
            "market/message.html",
            heading="Marketplace temporarily unavailable",
            message="Item details are temporarily unavailable. Please try again.",
            retry_url=url_for("market.item_detail", item_id=item_id),
        ), 503

    if document is None:
        return _item_not_found()
    return render_template("market/detail.html", item=public_item(document))


def _item_not_found():
    return render_template(
        "market/message.html",
        heading="Item not found",
        message="This listing does not exist or is no longer available.",
        retry_url=None,
    ), 404
