import re
import html
import os
import sys
import time
from urllib.parse import unquote

import requests


def load_dotenv(path=None):
    """Lightweight .env loader (no extra dependency)."""
    candidates = []
    if path:
        candidates.append(path)
    try:
        candidates.append(
            os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                ".env",
            )
        )
    except Exception:
        pass
    candidates.append(os.path.join(os.getcwd(), ".env"))
    seen = set()
    for p in candidates:
        if not p or p in seen:
            continue
        seen.add(p)
        try:
            if not os.path.isfile(p):
                continue
            with open(p, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    if k and k not in os.environ:
                        os.environ[k] = v
        except Exception:
            continue


load_dotenv()


# =========================================================
# JIO ENDPOINTS
# =========================================================

CHECK_NUMBER_URL = (
    "https://www.jio.com/api/"
    "jio-recharge-service/recharge/mobility/number/{mobile}"
)

SEND_OTP_URL = (
    "https://www.jio.com/api/"
    "jio-login-service/login/sendOtp"
)

VERIFY_OTP_URL = (
    "https://www.jio.com/api/"
    "jio-login-service/login/validateOtp"
)

AUTH_URL = (
    "https://www.jio.com/api/"
    "jio-authenticate-service/authenticate/authJsonData"
)

NAVIGATE_URL = (
    "https://www.jio.com/api/"
    "jio-ott-service/ott/subscription/navigate/Z0241"
)

ACTIVATE_URL = (
    "https://www.jio.com/api/"
    "jio-ott-service/ott/subscription/activate/"
    "Z0241?source=JIO"
)

GOOGLE_URL = (
    "https://www.jio.com/api/"
    "jio-ott-service/ott/subscription/google-ai"
)

SUBMIT_URL = (
    "https://www.jio.com/api/"
    "jio-ott-service/ott/submission/submit"
)

GOOGLE_PAGE = (
    "https://www.jio.com/selfcare/"
    "googleai/?header=no&type=Z0241&source=JIO"
)


# =========================================================
# SESSION
# =========================================================

def create_session():
    session = requests.Session()

    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "Chrome/120 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Origin": "https://www.jio.com",
        "Referer": "https://www.jio.com/selfcare/login/",
    })

    return session


# =========================================================
# HELPERS
# =========================================================

def response_json(response):
    try:
        data = response.json()
    except ValueError:
        return {}

    if isinstance(data, dict):
        return data

    return {}


def api_message(data):
    for key in (
        "errorMessage",
        "responseMessage",
        "responseMsg",
        "message",
    ):
        if data.get(key):
            return str(data[key])

    return ""


def normalize_mobile(value):
    digits = re.sub(r"\D", "", value)

    # Remove India country code
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]

    if not re.fullmatch(r"[6-9]\d{9}", digits):
        return None

    return digits


# =========================================================
# CHECK JIO NUMBER
# =========================================================

def check_jio_number(session, mobile):
    print("\nChecking Jio number...")

    try:
        response = session.get(
            CHECK_NUMBER_URL.format(mobile=mobile),
            timeout=20,
        )

    except requests.RequestException as e:
        print("Network error:", e)
        return False

    print("HTTP:", response.status_code)

    data = response_json(response)

    if response.status_code != 200:
        print("Server response:", api_message(data))
        return False

    if data.get("primaryService"):
        print("Jio number detected.")
        return True

    print("Number was not recognized as Jio.")

    if data:
        print("Response message:", api_message(data))

    return False


# =========================================================
# SEND OTP
# =========================================================

def send_otp(session, mobile):
    print("\nSending OTP...")

    payload = {
        "mobileNumber": mobile,
        "loginFlowType": "MOBILE",
        "alternateNumber": "",
    }

    try:
        response = session.post(
            SEND_OTP_URL,
            json=payload,
            timeout=20,
        )

    except requests.RequestException as e:
        print("Network error:", e)
        return False

    print("HTTP:", response.status_code)

    data = response_json(response)

    message = api_message(data)

    if message:
        print("Message:", message)

    if not response.ok:
        return False

    if (
        data.get("error")
        or data.get("errorMessage")
        or str(data.get("status", "")).lower()
        in {"failed", "failure", "error", "false"}
    ):
        return False

    return True


# =========================================================
# VERIFY OTP
# =========================================================

def verify_otp(session, mobile, otp):
    print("\nVerifying OTP...")

    payload = {
        "mobileNumber": mobile,
        "otp": otp,
    }

    try:
        response = session.post(
            VERIFY_OTP_URL,
            json=payload,
            timeout=20,
        )

    except requests.RequestException as e:
        print("Network error:", e)
        return False

    print("HTTP:", response.status_code)

    data = response_json(response)

    message = api_message(data)

    if message:
        print("Message:", message)

    if not response.ok:
        return False

    if (
        data.get("error")
        or data.get("errorMessage")
        or str(data.get("status", "")).lower()
        in {"failed", "failure", "error", "false"}
    ):
        return False

    return True


# =========================================================
# GRIZZLY SMS API (https://grizzlysms.com/docs)
# sms-activate compatible:
#   GET https://api.grizzlysms.com/stubs/handler_api.php
# =========================================================

GRIZZLY_BASE_URL = (
    "https://api.grizzlysms.com/stubs/handler_api.php"
)

# Defaults for Jio flow:
#   country 22 = India (confirmed via getCountries)
#   service "jio" = MyJio (confirmed via getServicesList:
#   {"code":"jio","name":"MyJio"})
DEFAULT_GRIZZLY_SERVICE = "jio"
DEFAULT_GRIZZLY_COUNTRY = "22"


def grizzly_request(api_key, params, timeout=20):
    """Single GET to Grizzly. Returns raw text stripped."""
    q = {"api_key": api_key}
    q.update(params)
    try:
        r = requests.get(
            GRIZZLY_BASE_URL,
            params=q,
            timeout=timeout,
        )
    except requests.RequestException as e:
        print("Grizzly network error:", e)
        return ""

    text = (r.text or "").strip()
    return text


def grizzly_get_balance(api_key):
    text = grizzly_request(api_key, {"action": "getBalance"})
    # Success: ACCESS_BALANCE:12.34
    if text.startswith("ACCESS_BALANCE:"):
        return True, text.split(":", 1)[1].strip()
    return False, text


def grizzly_get_number(api_key, service, country, quiet=False, max_price=None):
    """
    Returns (activation_id, phone) on success, else ("", "").
    Tries getNumber then getNumberV2 (JSON) fallback.
    Success: ACCESS_NUMBER:38496653:66846426435
    Errors: BAD_KEY, NO_BALANCE, NO_NUMBERS, BAD_SERVICE, etc.
    Docs say on NO_NUMBERS: "repeat a request" - so polling is allowed.
    max_price: e.g. "0.208" buys up to that tier. None = cheapest.
    """
    def _log(msg):
        if not quiet:
            print(msg)

    def _params():
        p = {
            "service": service,
            "country": country,
        }
        if max_price:
            p["maxPrice"] = str(max_price)
        return p

    for action in ("getNumber", "getNumberV2"):
        if action == "getNumber":
            q = {"action": "getNumber"}
            q.update(_params())
            text = grizzly_request(api_key, q)
            if text.startswith("ACCESS_NUMBER:"):
                parts = text.split(":")
                if len(parts) >= 3:
                    return parts[1].strip(), parts[2].strip()
            # getNumberV2 returns JSON even on HTTP 200 text body,
            # so if we got JSON here, try to parse it too
            if text.strip().startswith("{") and "activationId" in text:
                try:
                    import json as _json
                    obj = _json.loads(text)
                    aid = str(obj.get("activationId", "")).strip()
                    phone = str(obj.get("phoneNumber", "")).strip()
                    if aid and phone:
                        return aid, phone
                except Exception:
                    pass
            if action == "getNumber":
                first_error = text or "(empty response)"
                # Don't give up yet - try V2
                if text.startswith("ACCESS_NUMBER:"):
                    break
                # If BAD_ACTION, V2 may still work; continue loop
                if text in ("BAD_ACTION", "BAD_SERVICE", "NO_NUMBERS") or not text.startswith("ACCESS_"):
                    _log(f"Grizzly getNumber failed: {text or '(empty response)'} - trying getNumberV2...")
                    continue
            _log("Grizzly getNumber failed:" + (text or "(empty response)"))
            return "", ""
        else:
            # getNumberV2 -> JSON
            q2 = {"action": "getNumberV2"}
            q2.update(_params())
            text = grizzly_request(api_key, q2)
            if not text:
                _log("Grizzly getNumberV2 failed: (empty response)")
                _log(f"First error was: {first_error}")
                if not quiet:
                    grizzly_diagnose(api_key, service, country)
                return "", ""
            try:
                import json as _json
                # Error responses are plain text even for V2
                if not text.strip().startswith("{"):
                    _log(f"Grizzly getNumberV2 failed: {text}")
                    _log(f"First error was: {first_error}")
                    if not quiet:
                        grizzly_diagnose(api_key, service, country)
                    return "", ""
                obj = _json.loads(text)
                aid = str(obj.get("activationId", "")).strip()
                phone = str(obj.get("phoneNumber", "")).strip()
                if aid and phone:
                    return aid, phone
                _log(f"Grizzly getNumberV2 unexpected JSON: {text[:300]}")
            except Exception as e:
                _log(f"Grizzly getNumberV2 parse failed: {text[:300]} ({e})")
            if not quiet:
                grizzly_diagnose(api_key, service, country)
            return "", ""
    _log("Grizzly getNumber failed:" + (first_error if 'first_error' in dir() else "(unknown)"))
    return "", ""


def grizzly_wait_for_number(api_key, combos, timeout=1800, interval=15, max_price=None):
    """
    Wait until a number is available (polls getNumber).
    combos: list of (service, country), e.g. [("jio","22"),("ot","22")].
    Only Indian numbers (normalize_mobile ok) are accepted.
    Foreign numbers are cancelled immediately to refund.
    Returns (activation_id, phone, service, country) or ("","","","").
    Docs: on NO_NUMBERS docs say "repeat a request" - polling is the
    documented way, there is no server-side wait parameter.
    """
    deadline = time.time() + timeout
    attempt = 0
    price_info = f" maxPrice={max_price}" if max_price else " (cheapest tier)"
    print(
        f"\nWaiting for stock up to {timeout//60}m "
        f"(trying {', '.join(f'{s}/{c}' for s, c in combos)}{price_info}, "
        f"every {interval}s, Ctrl+C to stop)..."
    )
    while True:
        attempt += 1
        for (svc, ctry) in combos:
            aid, phone = grizzly_get_number(
                api_key, svc, ctry, quiet=True, max_price=max_price
            )
            if aid and phone:
                mob = normalize_mobile(phone)
                if mob:
                    print(f"\n[{attempt}] Got {svc}/{ctry}: id={aid} ******{mob[-4:]}")
                    return aid, phone, svc, ctry
                # Foreign/non-Jio number - cancel to refund, keep waiting
                print(
                    f"\n[{attempt}] Got foreign {svc}/{ctry}: {phone} "
                    f"id={aid} - not Indian, cancelling..."
                )
                try:
                    r = grizzly_set_status(api_key, aid, 8)
                    print(f"Cancel (8): {r}")
                except Exception:
                    pass
                # continue waiting for Indian number
        remaining = int(deadline - time.time())
        if remaining <= 0:
            print(f"\nStock wait timeout after {timeout}s.")
            return "", "", "", ""
        # Progress line (overwrites)
        mins, secs = divmod(remaining, 60)
        print(
            f"[{attempt}] NO_NUMBERS for {[f'{s}/{c}' for s, c in combos]} - "
            f"retry in {interval}s ({mins}m{secs:02d} left)...",
            end="\r",
            flush=True,
        )
        try:
            time.sleep(min(interval, max(1, remaining)))
        except KeyboardInterrupt:
            print("\nStopped waiting by user.")
            return "", "", "", ""
        print()  # newline after \r line


def grizzly_diagnose(api_key, service, country):
    """Print actionable hints when getNumber fails."""
    print("\n--- Grizzly diagnose ---")
    print(f"Tried: service={service!r} country={country!r}")
    print("1) Check service code via docs 'Test this method now' dropdown,")
    print("   or open (replace KEY):")
    print("   https://api.grizzlysms.com/stubs/handler_api.php?api_key=KEY&action=getServicesList")
    # Try to fetch it automatically
    try:
        txt = grizzly_request(api_key, {"action": "getServicesList"})
        if txt and len(txt) > 10 and len(txt) < 20000:
            low = txt.lower()
            # Find jio-like entries
            import json as _json
            try:
                arr = _json.loads(txt)
                # arr may be list of {code,name} or dict
                found = []
                if isinstance(arr, list):
                    for item in arr[:2000]:
                        if isinstance(item, dict):
                            code = str(item.get("code", item.get("service", "")))
                            name = str(item.get("name", ""))
                            if "jio" in (code + " " + name).lower():
                                found.append(f"{code} = {name}")
                elif isinstance(arr, dict):
                    for k, v in arr.items():
                        if "jio" in (str(k) + " " + str(v)).lower():
                            found.append(f"{k} = {v}")
                if found:
                    print("Jio-like services found in your account:")
                    for f in found[:20]:
                        print("  ", f)
                else:
                    print("Could not find 'jio' in services list. Try service=anyother or ot.")
                    print(f"Services preview: {txt[:500]}")
            except Exception:
                if "jio" in low:
                    print("Services list contains 'jio'. Use exact code from list.")
                print(f"Services preview: {txt[:500]}")
        else:
            if txt:
                print(f"getServicesList preview: {txt[:500]}")
    except Exception as e:
        print(f"getServicesList failed: {e}")
    print("2) Try country=any (auto-select) if 22 has no stock:")
    print("   service=jio country=any")
    print("3) Workaround for Jio: service=ot (AnyOther) country=22")
    print("   AnyOther numbers can receive Jio OTPs.")
    print("4) Check stock: ?action=getPrices&service=jio&country=22")
    print("------------------------\n")


def grizzly_get_prices(api_key, service="jio", country="22"):
    """Return raw JSON text for stock check."""
    return grizzly_request(
        api_key,
        {
            "action": "getPrices",
            "service": service,
            "country": country,
        },
    )


def grizzly_set_status(api_key, activation_id, status):
    """
    status: 1 = ready/SMS sent, 3 = retry/another SMS,
            6 = finish/confirm, 8 = cancel
    Returns raw response text.
    """
    text = grizzly_request(
        api_key,
        {
            "action": "setStatus",
            "id": activation_id,
            "status": str(status),
        },
    )
    return text


def grizzly_get_status(api_key, activation_id):
    """
    Returns raw text:
      STATUS_WAIT_CODE -> no SMS yet
      STATUS_WAIT_RETRY:<lastcode> -> waiting retry
      STATUS_OK:<code> -> OTP received
      STATUS_CANCEL -> cancelled
    """
    return grizzly_request(
        api_key,
        {
            "action": "getStatus",
            "id": activation_id,
        },
    )


def grizzly_extract_otp(text):
    """
    Extract 4-8 digit OTP from STATUS_OK:xxx or full SMS text.
    Prefers 6-digit match (Jio uses 6 digits).
    """
    if not text:
        return ""
    # STATUS_OK:123456 -> take part after colon first
    if "STATUS_OK:" in text:
        text = text.split("STATUS_OK:", 1)[1]
    codes6 = re.findall(r"\b\d{6}\b", text)
    if codes6:
        return codes6[0]
    codes = re.findall(r"\b\d{4,8}\b", text)
    if codes:
        return codes[0]
    return ""


def grizzly_poll_otp(api_key, activation_id, timeout=180, interval=5):
    """
    Poll getStatus until STATUS_OK:<otp>.
    Returns otp string or "" on timeout/cancel.
    """
    print(
        f"\nWaiting for Jio OTP on Grizzly "
        f"(id={activation_id}, timeout={timeout}s)..."
    )
    deadline = time.time() + timeout
    attempt = 0
    while time.time() < deadline:
        attempt += 1
        text = grizzly_get_status(api_key, activation_id)

        if not text:
            print(f"[{attempt}] empty response, retrying...")
        elif text == "STATUS_WAIT_CODE":
            print(f"[{attempt}] STATUS_WAIT_CODE - waiting for SMS...")
        elif text.startswith("STATUS_WAIT_RETRY:"):
            otp = grizzly_extract_otp(text)
            print(
                f"[{attempt}] STATUS_WAIT_RETRY - "
                f"last code: {otp or text}"
            )
            # If Jio only sends one OTP, this is already usable
            if otp:
                return otp
        elif text.startswith("STATUS_OK:"):
            otp = grizzly_extract_otp(text)
            print(f"[{attempt}] STATUS_OK - OTP: {otp or text}")
            if otp:
                return otp
            # Fallback: return raw after colon even if not digits
            raw = text.split(":", 1)[1].strip()
            if raw:
                return raw
        elif text == "STATUS_CANCEL":
            print("Activation was cancelled (STATUS_CANCEL).")
            return ""
        elif text in ("NO_ACTIVATION", "BAD_ACTION", "BAD_KEY",
                      "ERROR_SQL"):
            print("Grizzly getStatus error:", text)
            return ""
        else:
            # Sometimes full SMS text is returned directly
            otp = grizzly_extract_otp(text)
            if otp:
                print(f"[{attempt}] OTP found: {otp}")
                return otp
            print(f"[{attempt}] Unknown response: {text}")

        remaining = int(deadline - time.time())
        if remaining <= 0:
            break
        time.sleep(min(interval, max(1, remaining)))

    print(f"OTP timeout after {timeout}s.")
    return ""


# =========================================================
# ACTIVATION LINK PARSER
# =========================================================

ACTIVATION_PATTERN = re.compile(
    r"https?://serviceactivation[.]google[.]com/"
    r"subscription/new/"
    r"(?P<token>[A-Za-z0-9_-]{50,})"
    r"(?P<padding>={0,2})",
    re.IGNORECASE,
)


def extract_activation_url(value):
    text = html.unescape(value or "")

    for _ in range(4):
        decoded = unquote(text)

        if decoded == text:
            break

        text = decoded

    match = ACTIVATION_PATTERN.search(text)

    if not match:
        return ""

    return (
        "https://serviceactivation.google.com/"
        "subscription/new/"
        + match.group("token")
        + match.group("padding")
    )


def already_active(value):
    normalized = (
        " ".join(
            (value or "")
            .lower()
            .replace("_", " ")
            .split()
        )
    )

    phrases = (
        "already active",
        "already activated",
        "already redeemed",
        "already claimed",
        "already availed",
    )

    return any(x in normalized for x in phrases)


# =========================================================
# GET GEMINI ACTIVATION
# =========================================================

def get_activation(session):

    dashboard_headers = {
        "Accept": "*/*",
        "Referer": "https://www.jio.com/selfcare/dashboard/",
    }

    offer_headers = {
        "Accept": "*/*",
        "Referer": GOOGLE_PAGE,
    }

    print("\nChecking authenticated Jio session...")

    try:
        response = session.get(
            AUTH_URL,
            headers=dashboard_headers,
            timeout=20,
        )

        data = response_json(response)

        if (
            not response.ok
            or str(data.get("loginFlag", "")).lower()
            != "true"
        ):
            return "session_invalid", ""

        print("Authenticated.")

        # Navigate to subscription area
        session.get(
            NAVIGATE_URL,
            headers=dashboard_headers,
            timeout=20,
        )

        print("Checking Gemini offer...")

        activate_response = session.get(
            ACTIVATE_URL,
            headers=offer_headers,
            timeout=20,
        )

        activate_data = response_json(
            activate_response
        )

        message = api_message(activate_data)

        if already_active(message):
            return "already_active", ""

        if not activate_response.ok:
            return "activation_api_failed", ""

        if str(
            activate_data.get(
                "errorCode",
                "200",
            )
        ) != "200":
            return "activation_api_failed", ""

        # Request Google AI subscription information
        google_response = session.get(
            GOOGLE_URL,
            headers=offer_headers,
            timeout=20,
        )

        google_data = response_json(
            google_response
        )

        message = api_message(google_data)

        if already_active(message):
            return "already_active", ""

        url = extract_activation_url(
            str(
                google_data.get(
                    "redirectionURL",
                    "",
                )
            )
        )

        if not url:
            print(
                "No activation URL returned."
            )

            if message:
                print(
                    "Jio response:",
                    message,
                )

            return "no_activation_url", ""

        # Original script performs this request
        # after obtaining the link.
        try:
            session.get(
                SUBMIT_URL,
                headers=offer_headers,
                timeout=20,
            )
        except requests.RequestException:
            pass

        return "activation_url_found", url

    except requests.RequestException as e:
        print("Network error:", e)
        return "activation_api_failed", ""


# =========================================================
# MAIN
# =========================================================

# =========================================================
# MAIN
# =========================================================

def verify_and_get_link(session, mobile, otp, grizzly=None):
    """
    grizzly: None or (api_key, activation_id).
    Returns True if activation link found.
    Handles Grizzly setStatus 6 (finish) / 8 (cancel).
    """
    if not verify_otp(
        session,
        mobile,
        otp,
    ):
        print(
            "\nOTP verification failed."
        )
        return False

    print(
        "\nOTP verified successfully."
    )

    status, activation_link = (
        get_activation(session)
    )

    print()
    print("=" * 65)
    print("RESULT")
    print("=" * 65)

    print(
        "Status:",
        status,
    )

    if activation_link:

        print()
        print(
            "Activation link:"
        )

        print(
            activation_link
        )

        with open(
            "gemini_activation_link.txt",
            "w",
            encoding="utf-8",
        ) as f:
            f.write(
                activation_link + "\n"
            )

        print(
            "\nSaved to "
            "gemini_activation_link.txt"
        )

        if grizzly:
            api_key, activation_id = grizzly
            try:
                resp = grizzly_set_status(
                    api_key, activation_id, 6
                )
                print(f"Grizzly finish (6): {resp}")
            except Exception:
                pass
        return True

    # No link -> cancel Grizzly to refund if possible
    if grizzly:
        api_key, activation_id = grizzly
        try:
            resp = grizzly_set_status(
                api_key, activation_id, 8
            )
            print(f"Grizzly cancel (8): {resp}")
        except Exception:
            pass
    return False


def run_manual_flow():
    raw_mobile = input(
        "\nEnter your Jio mobile number: "
    ).strip()

    mobile = normalize_mobile(raw_mobile)

    if not mobile:
        print(
            "Invalid Indian mobile number."
        )
        return

    print(
        f"Number: ******{mobile[-4:]}"
    )

    session = create_session()

    if not check_jio_number(
        session,
        mobile,
    ):
        print(
            "\nStopped: number was not "
            "recognized as Jio."
        )
        return

    if not send_otp(
        session,
        mobile,
    ):
        print(
            "\nOTP could not be sent."
        )
        return

    print(
        "\nOTP sent."
    )

    otp = input(
        "Enter the OTP received on your phone: "
    ).strip()

    if not re.fullmatch(
        r"\d{6}",
        otp,
    ):
        print(
            "OTP must contain exactly "
            "6 digits."
        )
        return

    verify_and_get_link(session, mobile, otp, grizzly=None)


def run_grizzly_auto_flow():
    api_key = (
        os.environ.get("GRIZZLY_API_KEY", "").strip()
        or input(
            "\nEnter Grizzly API key "
            "(or put it in .env as GRIZZLY_API_KEY): "
        ).strip()
    )
    if not api_key:
        print("API key is required. Put it in .env as GRIZZLY_API_KEY=xxx")
        return

    default_service = (
        os.environ.get("GRIZZLY_SERVICE", "").strip()
        or DEFAULT_GRIZZLY_SERVICE
    )
    default_country = (
        os.environ.get("GRIZZLY_COUNTRY", "").strip()
        or DEFAULT_GRIZZLY_COUNTRY
    )

    service = (
        input(
            f"Grizzly service code "
            f"[default: {default_service}] "
            f"(jio=MyJio, ot=AnyOther): "
        ).strip()
        or default_service
    )
    country = (
        input(
            f"Grizzly country code "
            f"[default: {default_country}=India]: "
        ).strip()
        or default_country
    )

    ok, bal = grizzly_get_balance(api_key)
    if ok:
        print(f"Grizzly balance: {bal}")
    else:
        print(f"Grizzly balance check: {bal}")
        if bal in ("BAD_KEY",):
            return

    print("\nPrice tiers from your screenshot (India/MyJio):")
    print("  $0.10  (128179 qty) = cheapest tier / lowest success")
    print("  $0.15  (16013 qty)  = middle tier")
    print("  $0.208 (101564 qty) = top tier / best success")
    print("API buys cheapest by default. Set maxPrice to allow higher tier.")
    default_max = os.environ.get("GRIZZLY_MAX_PRICE", "").strip()
    max_price = (
        input(
            f"Max price [default: {default_max or 'cheapest'}, "
            f"e.g. 0.208 to allow all tiers]: "
        ).strip()
        or default_max
        or None
    )
    if max_price:
        print(f"Using maxPrice={max_price}")
    else:
        print("Using cheapest tier (no maxPrice). If Jio rejects numbers, retry with 0.208.")

    try:
        tries = input(
            "How many numbers to try before stopping? [default 0=infinite]: "
        ).strip() or "0"
        max_numbers = int(float(tries))
        if max_numbers < 0:
            max_numbers = 0
    except ValueError:
        max_numbers = 0
    print(
        f"Will auto-retry {'infinite' if max_numbers==0 else str(max_numbers)} "
        f"numbers until valid Jio."
    )

    number_attempt = 0
    wait_timeout = 1800
    wait_interval = 15
    first_round = True

    while True:
        number_attempt += 1
        if max_numbers and number_attempt > max_numbers:
            print(f"\nStopped after {max_numbers} numbers.")
            return

        print(f"\n===== Number attempt {number_attempt} =====")
        if first_round:
            print(f"\nRequesting number: service={service} country={country} ..."
                  + (f" maxPrice={max_price}" if max_price else ""))
            activation_id, phone_raw = grizzly_get_number(
                api_key, service, country, max_price=max_price
            )
            used_service, used_country = service, country
            first_round = False
        else:
            activation_id, phone_raw = "", ""

        if not activation_id or not phone_raw:
            # Build Indian-only combos first (Jio needs +91).
            # Do NOT auto-use country=any - it returns foreign numbers
            # (e.g. 62xxxx Indonesia) that waste balance, as you saw.
            combos = [(service, country)]
            if service == "jio" and country == "22":
                combos.append(("ot", "22"))
            elif service == "ot" and country == "22":
                combos.append(("jio", "22"))
            # Only allow foreign fallback if user explicitly typed any
            allow_any = (country == "any")
            if allow_any and (service, "any") not in combos:
                combos.append((service, "any"))

            # On retry rounds, don't ask again - keep waiting
            if number_attempt == 1:
                wait = (
                    input(
                        "\nNo stock (NO_NUMBERS). Wait until available? [Y/n]: "
                    ).strip().lower()
                )
                if wait not in ("", "y", "yes"):
                    print("\nAborted. Or buy AnyOther/India on site and use mode 3.")
                    return
                try:
                    mins = input(
                        "Wait how long? minutes [default 30, 0=infinite]: "
                    ).strip() or "30"
                    wait_mins = float(mins)
                    wait_timeout = int(wait_mins * 60) if wait_mins > 0 else 86400
                except ValueError:
                    wait_timeout = 1800
                try:
                    interval = input(
                        "Retry every? seconds [default 15]: "
                    ).strip() or "15"
                    wait_interval = max(5, int(float(interval)))
                except ValueError:
                    wait_interval = 15
            else:
                print(f"\nWaiting for next number ({wait_timeout//60}m, every {wait_interval}s)...")

            print(f"Combos to wait for: {combos} (Indian numbers only)")
            activation_id, phone_raw, used_service, used_country = (
                grizzly_wait_for_number(
                    api_key, combos,
                    timeout=wait_timeout, interval=wait_interval,
                    max_price=max_price,
                )
            )
            if activation_id:
                service, country = used_service, used_country
            else:
                print("\nStill NO_NUMBERS.")
                print("Check stock manually:")
                print(f"  ?action=getPrices&service=jio&country=22")
                print(f"  ?action=getPrices&service=ot&country=22")
                print("Or buy AnyOther/India on site and use mode 3.")
                return

        mobile = normalize_mobile(phone_raw)
        if not mobile:
            # Grizzly may return without country code, keep digits
            print(f"Grizzly returned phone: {phone_raw}")
            print("Could not normalize to Indian mobile.")
            print("Cancelling and trying next number...")
            try:
                grizzly_set_status(api_key, activation_id, 8)
            except Exception:
                pass
            time.sleep(3)
            continue

        print(f"\nGrizzly activation id: {activation_id}")
        print(f"Grizzly number: +91 ******{mobile[-4:]} (full hidden)")
        print(f"Full number (for debug): {phone_raw}")

        # Tell Grizzly number is ready / SMS will be sent
        resp = grizzly_set_status(api_key, activation_id, 1)
        print(f"Grizzly ready (1): {resp}")

        session = create_session()

        if not check_jio_number(session, mobile):
            print(f"\nAttempt {number_attempt}: NOT_SUBSCRIBED_USER / not Jio.")
            print("Cancelling Grizzly activation to refund, auto-retrying next number...")
            try:
                grizzly_set_status(api_key, activation_id, 8)
            except Exception:
                pass
            time.sleep(3)
            continue

        if not send_otp(session, mobile):
            print("\nOTP could not be sent.")
            print("Cancelling Grizzly activation to refund, auto-retrying next number...")
            try:
                grizzly_set_status(api_key, activation_id, 8)
            except Exception:
                pass
            time.sleep(3)
            continue

        print("\nOTP sent. Polling Grizzly for OTP...")

        otp = grizzly_poll_otp(api_key, activation_id, timeout=180, interval=5)

        if not otp:
            print("\nNo OTP received from Grizzly.")
            retry = input(
                "Enter OTP manually (or press Enter to auto-try next number): "
            ).strip()
            if not retry:
                try:
                    grizzly_set_status(api_key, activation_id, 8)
                except Exception:
                    pass
                print("Auto-retrying next number...")
                time.sleep(3)
                continue
            otp = retry

        # Jio expects 6 digits - extract if full SMS returned
        otp_digits = grizzly_extract_otp(otp) or otp.strip()
        print(f"Using OTP: {otp_digits}")

        success = verify_and_get_link(
            session, mobile, otp_digits,
            grizzly=(api_key, activation_id),
        )
        if success:
            print(f"\nDone after {number_attempt} number(s).")
            return
        print(
            "\nNo link from this number, auto-retrying next number..."
        )
        time.sleep(3)
        continue


def run_grizzly_otp_only_flow():
    """
    You already bought the number on grizzlysms.com manually:
    paste number + activation ID here, script sends Jio OTP
    then auto-polls Grizzly getStatus for the code.
    """
    api_key = (
        os.environ.get("GRIZZLY_API_KEY", "").strip()
        or input(
            "\nEnter Grizzly API key (or put it in .env): "
        ).strip()
    )
    if not api_key:
        print("API key is required. Put it in .env as GRIZZLY_API_KEY=xxx")
        return

    activation_id = input(
        "Enter Grizzly activation ID (from ACCESS_NUMBER): "
    ).strip()
    if not activation_id:
        print("Activation ID is required.")
        return

    raw_mobile = input(
        "Enter the Grizzly number (paste it here): "
    ).strip()
    mobile = normalize_mobile(raw_mobile)
    if not mobile:
        print("Invalid Indian mobile number.")
        return

    print(f"Number: ******{mobile[-4:]} id={activation_id}")

    resp = grizzly_set_status(api_key, activation_id, 1)
    print(f"Grizzly ready (1): {resp}")

    session = create_session()

    if not check_jio_number(session, mobile):
        print("\nStopped: not recognized as Jio.")
        return

    if not send_otp(session, mobile):
        print("\nOTP could not be sent.")
        return

    print("\nOTP sent. Polling Grizzly for OTP...")
    otp = grizzly_poll_otp(api_key, activation_id, timeout=180, interval=5)

    if not otp:
        print("\nNo OTP received.")
        retry = input(
            "Enter OTP manually (or press Enter to abort): "
        ).strip()
        if not retry:
            return
        otp = retry

    otp_digits = grizzly_extract_otp(otp) or otp.strip()
    print(f"Using OTP: {otp_digits}")

    verify_and_get_link(
        session, mobile, otp_digits,
        grizzly=(api_key, activation_id),
    )


def main():

    print("=" * 65)
    print("Jio Gemini - Grizzly SMS + Manual OTP")
    print("Docs: https://grizzlysms.com/docs")
    print("=" * 65)
    print("\nModes:")
    print("  1 = Manual (paste number, paste OTP)")
    print("  2 = Grizzly AUTO (API gets number + auto OTP -> gemini link)")
    print("  3 = Grizzly OTP only (paste number+ID, auto OTP -> gemini link)")

    choice = input(
        "\nChoose mode [1/2/3] (default 2): "
    ).strip() or "2"

    if choice == "1":
        run_manual_flow()
    elif choice == "3":
        run_grizzly_otp_only_flow()
    else:
        if choice != "2":
            print(f"Unknown choice '{choice}', using 2.")
        run_grizzly_auto_flow()


if __name__ == "__main__":
    main()