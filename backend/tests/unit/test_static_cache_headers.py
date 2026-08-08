"""The frontend must never be served from a stale browser cache.

index.html requests the bundle as `dist/bundle.js?v=20` -- a version counter a
human has to remember to bump. Nobody does. So the bundle's contents change on
every `npm run build` while its URL stays byte-identical, and a browser that
cached that URL keeps executing old JavaScript: you rebuild, restart the server,
reload the page, and the app is visibly unchanged. It is indistinguishable from
a build that failed silently.

Sending `Cache-Control: no-cache` makes the browser revalidate before reusing a
cached copy, so the stale `?v=` counter stops being load-bearing. It is not
`no-store`: with the ETag Starlette already sends, an unchanged file still costs
only an empty 304.
"""
import os

import pytest
from fastapi.testclient import TestClient

from backend.src.api.main import app, FRONTEND_DIR


pytestmark = pytest.mark.skipif(
    not os.path.isdir(FRONTEND_DIR),
    reason="frontend/ is not present, so the static mount does not exist",
)


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_index_is_revalidated_not_blindly_reused(client):
    response = client.get("/index.html")
    assert response.status_code == 200
    assert response.headers.get("cache-control") == "no-cache"


def test_bundle_is_revalidated(client):
    if not os.path.isfile(os.path.join(FRONTEND_DIR, "dist", "bundle.js")):
        pytest.skip("bundle.js has not been built")

    response = client.get("/dist/bundle.js")
    assert response.status_code == 200
    assert response.headers.get("cache-control") == "no-cache"
    # An ETag has to be present, or "revalidate" degrades into "download the
    # whole bundle every single page load".
    assert response.headers.get("etag")


def test_revalidation_still_allows_a_cheap_304(client):
    """no-cache must not mean no-store: unchanged files stay nearly free."""
    first = client.get("/index.html")
    etag = first.headers.get("etag")
    assert etag

    second = client.get("/index.html", headers={"If-None-Match": etag})
    assert second.status_code == 304
    assert second.content == b""
    # The directive has to survive onto the 304, or the next request forgets to
    # revalidate again.
    assert second.headers.get("cache-control") == "no-cache"
