"""Kotak Neo service — request shapes, parsing, session handling (no network)."""
import asyncio
import json
from urllib.parse import parse_qs

import httpx
import pytest

from services import kotak_service as ks


def run(coro):
    return asyncio.run(coro)


# ── TOTP ──────────────────────────────────────────────────────────────────────

def test_totp_rfc6238_vector():
    # RFC 6238 SHA-1 secret "12345678901234567890" → T=59 → 94287082 (8 digits) → 287082 (6)
    secret = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"
    assert ks.totp_now(secret, for_time=59) == "287082"
    assert ks.totp_now(secret.lower(), for_time=1111111109) == "081804"
    assert ks.totp_now("GEZD GNBV GY3T QOJQ GEZD GNBV GY3T QOJQ", for_time=59) == "287082"


def test_bad_secret_and_creds():
    with pytest.raises(ValueError):
        ks.validate_totp_secret("not base32 !!")
    with pytest.raises(ValueError):
        ks.validate_credentials({"accessToken": "x", "ucc": "AB1", "mobileNumber": "9876543210",
                                 "mpin": "12ab56", "totpSecret": "GEZDGNBVGY3TQOJQ"})


def test_mobile_normalisation():
    assert ks.normalise_mobile("9876543210") == "+919876543210"
    assert ks.normalise_mobile("919876543210") == "+919876543210"
    assert ks.normalise_mobile("+91 98765 43210") == "+919876543210"


def test_instrument_key_roundtrip():
    key = ks.make_instrument_key("mcx_fo", "445566", "CRUDEOILM26OCT6100CE")
    assert ks.parse_instrument_key(key) == ("mcx_fo", "445566", "CRUDEOILM26OCT6100CE")
    assert ks.is_kotak_key(key)
    assert not ks.is_kotak_key("NSE_FO|43427")
    assert not ks.is_kotak_key("43427")


# ── HTTP mocking ──────────────────────────────────────────────────────────────

class Recorder:
    def __init__(self, handler):
        self.handler = handler
        self.calls = []

    def __call__(self, request: httpx.Request):
        body = request.content.decode() if request.content else ""
        self.calls.append((request.method, str(request.url), dict(request.headers), body))
        return self.handler(request, body)


_REAL_ASYNC_CLIENT = httpx.AsyncClient


@pytest.fixture
def mock_http(monkeypatch):
    def install(handler):
        rec = Recorder(handler)
        transport = httpx.MockTransport(rec)
        real = _REAL_ASYNC_CLIENT

        def factory(*a, **k):
            k["transport"] = transport
            return real(*a, **k)

        monkeypatch.setattr(ks.httpx, "AsyncClient", factory)
        return rec
    return install


CREDS = {"accessToken": "tok-123", "ucc": "ab123", "mobileNumber": "9876543210", "mpin": "123456",
         "totpSecret": "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"}


def _jwt(exp: int) -> str:
    import base64
    payload = base64.urlsafe_b64encode(json.dumps({"exp": exp}).encode()).decode().rstrip("=")
    return f"h.{payload}.s"


def test_login_two_steps(mock_http, monkeypatch):
    monkeypatch.setattr(ks.time, "time", lambda: 1_800_000_010.0)   # mid-window, no wait

    def handler(req, body):
        if req.url.path.endswith("/tradeApiLogin"):
            return httpx.Response(200, json={"data": {"token": "VIEW", "sid": "VSID", "ucc": "AB123",
                                                      "greetingName": "Ravi"}})
        if req.url.path.endswith("/tradeApiValidate"):
            return httpx.Response(200, json={"data": {"token": _jwt(1_800_050_000), "sid": "SSID",
                                                      "baseUrl": "https://e21.kotaksecurities.com/",
                                                      "dataCenter": "E21", "ucc": "AB123"}})
        return httpx.Response(404)

    rec = mock_http(handler)
    sess = run(ks.login("acc1", CREDS))

    m1, u1, h1, b1 = rec.calls[0]
    assert u1 == "https://mis.kotaksecurities.com/login/1.0/tradeApiLogin"
    assert h1["authorization"] == "tok-123" and h1["neo-fin-key"] == "neotradeapi"
    assert json.loads(b1) == {"mobileNumber": "+919876543210", "ucc": "AB123",
                              "totp": ks.totp_now(CREDS["totpSecret"], 1_800_000_010.0)}
    m2, u2, h2, b2 = rec.calls[1]
    assert u2.endswith("/login/1.0/tradeApiValidate")
    assert h2["sid"] == "VSID" and h2["auth"] == "VIEW"
    assert json.loads(b2) == {"mpin": "123456"}

    assert sess.base_url == "https://e21.kotaksecurities.com"
    assert sess.sid == "SSID" and sess.auth.startswith("h.")
    assert sess.expires_at is not None
    again = ks.KotakSession.from_handle(sess.to_handle())
    assert again == sess and ks.is_handle(sess.to_handle())


def test_login_error_is_friendly(mock_http, monkeypatch):
    monkeypatch.setattr(ks.time, "time", lambda: 1_800_000_010.0)
    mock_http(lambda req, body: httpx.Response(
        401, json={"status": "error", "message": "Invalid credentials or TOTP.", "errorCode": "401"}))
    with pytest.raises(ks.KotakLoginError) as ei:
        run(ks.login("acc1", CREDS))
    assert "TOTP" in str(ei.value)


SESSION = ks.KotakSession(account_id="acc1", access_token="tok-123", ucc="AB123", auth="SESSJWT",
                          sid="SSID", base_url="https://e21.kotaksecurities.com",
                          created_at="2099-01-01T09:00:00+05:30")


def _form(body: str) -> dict:
    return json.loads(parse_qs(body)["jData"][0])


def test_place_order_payload_mcx(mock_http):
    rec = mock_http(lambda req, body: httpx.Response(200, json={"nOrdNo": "260610000123", "stat": "Ok",
                                                                "stCode": 200}))
    oid = run(ks.place_order(SESSION.to_handle(), segment="mcx_fo", trading_symbol="CRUDEOILM26OCT6100CE",
                             side="SELL", quantity=1, order_type="L", price=152.3, product="NRML",
                             validity="IOC", tag="CR_ABC_CE_E"))
    assert oid == "260610000123"
    method, url, headers, body = rec.calls[0]
    assert url == "https://e21.kotaksecurities.com/quick/order/rule/ms/place"
    assert headers["auth"] == "SESSJWT" and headers["sid"] == "SSID" and headers["neo-fin-key"] == "neotradeapi"
    assert headers["content-type"].startswith("application/x-www-form-urlencoded")
    j = _form(body)
    assert j == {"am": "NO", "dq": "0", "es": "mcx_fo", "mp": "0", "pc": "NRML", "pf": "N", "pr": "152.30",
                 "pt": "L", "qt": "1", "rt": "DAY", "tp": "0", "ts": "CRUDEOILM26OCT6100CE", "tt": "S",
                 "os": "NEOTRADEAPI", "ig": "CR_ABC_CE_E"}


def test_place_order_guards():
    h = SESSION.to_handle()
    with pytest.raises(ks.KotakError):
        run(ks.place_order(h, segment="nse_fo", trading_symbol="X", side="B", quantity=65, order_type="L", price=0))
    with pytest.raises(ks.KotakError):
        run(ks.place_order(h, segment="nse_fo", trading_symbol="X", side="B", quantity=65, order_type="SL",
                           price=10, trigger_price=0))
    with pytest.raises(ks.KotakError):
        run(ks.place_order(h, segment="nse_fo", trading_symbol="X", side="B", quantity=0, order_type="L", price=1))


def test_sl_order_payload(mock_http):
    rec = mock_http(lambda req, body: httpx.Response(200, json={"nOrdNo": "9", "stat": "Ok", "stCode": 200}))
    run(ks.place_order(SESSION.to_handle(), segment="nse_fo", trading_symbol="NIFTY26OCT25000CE", side="BUY",
                       quantity=65, order_type="SL", price=143.0, trigger_price=130.0, validity="DAY"))
    j = _form(rec.calls[0][3])
    assert (j["pt"], j["pr"], j["tp"], j["tt"], j["rt"]) == ("SL", "143.00", "130.00", "B", "DAY")


def test_error_response_raises_and_reads_both_message_keys(mock_http):
    mock_http(lambda req, body: httpx.Response(200, json={"stat": "Not_Ok", "emsg": "Insufficient balance.",
                                                          "stCode": 1004}))
    with pytest.raises(ks.KotakError) as ei:
        run(ks.cancel_order(SESSION.to_handle(), "1"))
    assert ei.value.code == 1004 and "Insufficient" in str(ei.value)
    mock_http(lambda req, body: httpx.Response(200, json={"stCode": 100008, "errMsg": "unauthorized",
                                                          "stat": "Not_Ok"}))
    with pytest.raises(ks.KotakError) as ei:
        run(ks.cancel_order(SESSION.to_handle(), "1"))
    assert ei.value.ip_not_whitelisted


def test_invalid_session_relogs_once(mock_http, monkeypatch):
    fresh = ks.KotakSession(**{**SESSION.__dict__, "auth": "NEWJWT", "sid": "NEWSID"})

    async def fake_ensure(account_id, *, force=False, stale=None):
        assert stale is not None and stale.auth == "SESSJWT"
        return fresh
    monkeypatch.setattr(ks, "ensure_session", fake_ensure)
    monkeypatch.setattr(ks, "cached_session", lambda a: None)

    def handler(req, body):
        if req.headers["auth"] == "SESSJWT":
            return httpx.Response(200, json={"stat": "Not_Ok", "emsg": "Invalid session", "stCode": 1003})
        return httpx.Response(200, json={"stat": "Ok", "stCode": 200, "data": []})
    rec = mock_http(handler)
    assert run(ks.positions(SESSION.to_handle())) == []
    assert [c[2]["auth"] for c in rec.calls] == ["SESSJWT", "NEWJWT"]


# ── Parsing ───────────────────────────────────────────────────────────────────

def test_order_state_from_history():
    rows = [
        {"nOrdNo": "1", "ordSt": "complete", "fldQty": 65, "avgPrc": "101.25", "prcTp": "L",
         "prc": "99.00", "rejRsn": "--", "updRecvTm": "1700000003000000000"},
        {"nOrdNo": "1", "ordSt": "open", "fldQty": 0, "avgPrc": "0.00", "updRecvTm": "1700000002000000000"},
        {"nOrdNo": "1", "ordSt": "open pending", "fldQty": 0, "avgPrc": "0.00", "updRecvTm": "1700000001000000000"},
    ]
    st = ks.normalise_order_state(rows)
    assert st["status"] == "complete" and st["terminal"] and st["filled_qty"] == 65 and st["avg_price"] == 101.25

    st = ks.normalise_order_state([{"ordSt": "rejected", "rejRsn": "RMS:Margin Exceeds", "fldQty": 0}])
    assert st["status"] == "rejected" and "Margin" in st["message"]

    st = ks.normalise_order_state([{"ordSt": "cancelled", "fldQty": "5", "avgPrc": "10"},
                                   {"ordSt": "open", "fldQty": "5", "avgPrc": "10"}])
    assert st["status"] == "cancelled" and st["filled_qty"] == 5

    st = ks.normalise_order_state([{"ordSt": "trigger pending", "fldQty": 0}])
    assert st["status"] == "open" and not st["terminal"]


def test_position_summary_mcx_lots_with_multiplier():
    rows = [{"exSeg": "mcx_fo", "tok": "445566", "trdSym": "CRUDEOILM26OCT6100CE", "flBuyQty": "0",
             "flSellQty": "2", "cfBuyQty": "0", "cfSellQty": "0", "buyAmt": "0", "sellAmt": "3046.00",
             "multiplier": "10", "genNum": "1", "genDen": "1", "prcNum": "1", "prcDen": "1"},
            {"exSeg": "nse_fo", "tok": "445566", "flBuyQty": "65", "flSellQty": "0"}]
    snap = ks.summarise_position_rows(rows, "mcx_fo", "445566", "CRUDEOILM26OCT6100CE")
    assert snap["net_qty"] == -2 and abs(snap["sell_price"] - 152.3) < 1e-6 and snap["found"]
    flat = ks.summarise_position_rows(rows, "mcx_fo", "999", "NOPE")
    assert flat == {"net_qty": 0, "buy_price": 0.0, "sell_price": 0.0, "realised": None, "found": False}


def test_chain_parsing():
    chain = {"common_data": {"mktLot": "1", "multiplier": "10"},
             "call": [{"instrument": {"neoSymbol": "mcx_fo|111", "symbol": "CRUDEOILM26OCT6100CE",
                                      "optionType": "CE", "strikePrice": "6100"}, "quote": {"ltp": "152.30"}}],
             "put": [{"instrument": {"neoSymbol": "mcx_fo|222", "symbol": "CRUDEOILM26OCT6100PE",
                                     "optionType": "PE", "strikePrice": "6100.00"}, "quote": {"ltp": "140.10"}}]}
    strikes = ks.chain_strikes(chain)
    assert strikes[6100.0]["CE"]["key"] == "mcx_fo|111|CRUDEOILM26OCT6100CE"
    assert strikes[6100.0]["PE"]["ltp"] == 140.10
    assert ks.chain_lot_info(chain) == (1, 10.0)
