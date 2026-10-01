import httpx
import pytest

from app.services import funding_signals as funding

FEED = """<rss><channel>
<item><title>Acme Labs raises $5 Mn in Series A led by Peak XV</title></item>
<item><title>Globex bags funding from Accel</title></item>
<item><title>Why founders should raise less</title></item>
<item><title>the market raises concerns</title></item>
</channel></rss>"""


def test_only_raise_headlines_name_a_company():
    assert funding.company_from_headline("Acme Labs raises $5 Mn") == "Acme Labs"
    assert funding.company_from_headline("Why founders should raise less") is None
    assert funding.company_from_headline("the market raises concerns") is None
    assert funding.parse_feed(FEED) == ["Acme Labs", "Globex"]
    assert funding.parse_feed("not xml") == []


class FakeRedis:
    def __init__(self):
        self.data = {}

    async def set(self, key, value, nx=False, ex=None):
        if nx and key in self.data:
            return None
        self.data[key] = value
        return True

    async def mget(self, keys):
        return [self.data.get(k) for k in keys]


@pytest.mark.asyncio
async def test_funded_companies_are_matched_by_squashed_name(monkeypatch):
    redis = FakeRedis()

    async def get_redis():
        return redis

    async def get(url, **kwargs):
        return httpx.Response(200, text=FEED, request=httpx.Request("GET", url))

    monkeypatch.setattr(funding, "_redis", get_redis)
    monkeypatch.setattr(funding, "public_get", get)
    monkeypatch.setattr(funding.settings, "FUNDING_FEEDS", ["https://news.example.com/feed"])
    found = await funding.funded_among(["ACME LABS", "Initech", "globex"])
    assert found == {"acme labs", "globex"}
    # a second call inside the refresh window does not read the feed again
    assert await funding.refresh() == 0


@pytest.mark.asyncio
async def test_signal_is_off_without_feeds_and_never_raises(monkeypatch):
    monkeypatch.setattr(funding.settings, "FUNDING_FEEDS", [])
    assert await funding.funded_among(["Acme"]) == set()

    async def broken():
        raise ConnectionError("redis down")

    monkeypatch.setattr(funding.settings, "FUNDING_FEEDS", ["https://news.example.com/feed"])
    monkeypatch.setattr(funding, "_redis", broken)
    assert await funding.funded_among(["Acme"]) == set()
