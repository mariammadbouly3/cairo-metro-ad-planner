"""Email verification: send a 6-digit code, check it, and remember the verified address for this visit.

Streamlit Community Cloud blocks outgoing SMTP (ports 465/587), so codes go through the Brevo email API over
HTTPS (free: 300 emails a day). App secrets (Streamlit Cloud → app → Settings → Secrets):
    BREVO_API_KEY = "xkeysib-..."        # Brevo → SMTP & API → API keys
    EMAIL_FROM = "you@gmail.com"         # a sender you verified in Brevo → Senders
SMTP_USER / SMTP_PASSWORD (Gmail app password) still work where SMTP isn't blocked, e.g. on a laptop.
Without any of them, the forms still work and simply skip verification.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
import smtplib
import ssl
import time
import urllib.error
import urllib.request
from email.message import EmailMessage

import streamlit as st

import common as cm
from common import T

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")
CODE_TTL = 10 * 60      # a code works for 10 minutes
COOLDOWN = 60           # seconds between two sends
MAX_SENDS = 5           # per visit
MAX_TRIES = 5           # wrong codes before a new one is needed


def _secret(name, default=None):
    try:
        return st.secrets.get(name, default)
    except Exception:  # noqa: BLE001
        return default


def _brevo() -> bool:
    return bool(_secret("BREVO_API_KEY") and _secret("EMAIL_FROM"))


def configured() -> bool:
    return _brevo() or bool(_secret("SMTP_USER") and _secret("SMTP_PASSWORD"))


def sender() -> str:
    return str(_secret("EMAIL_FROM") or _secret("SMTP_USER") or "").strip()


class BrevoError(Exception):
    def __init__(self, status, body):
        super().__init__(f"{status} {body}")
        self.status, self.body = status, body


def _send_brevo(to, subject, text, html):
    payload = {"sender": {"name": "Cairo Metro Ad Planner", "email": sender()}, "to": [{"email": to}],
               "subject": subject, "textContent": text, "htmlContent": html}
    req = urllib.request.Request("https://api.brevo.com/v3/smtp/email", data=json.dumps(payload).encode(),
                                 method="POST", headers={"api-key": str(_secret("BREVO_API_KEY")).strip(),
                                                         "content-type": "application/json", "accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            r.read()
    except urllib.error.HTTPError as e:
        raise BrevoError(e.code, e.read().decode("utf-8", "ignore")[:300]) from None


def _hash(email: str, code: str) -> str:
    return hashlib.sha256(f"{email.lower()}|{code}".encode()).hexdigest()


def _send(to: str, code: str):
    subject = f"{code} كود التأكيد · Your verification code"
    text = (f"كود التأكيد بتاعك: {code}\nYour verification code: {code}\n\n"
            "الكود صالح لمدة 10 دقايق. لو مش انت اللي طلبته، تجاهل الرسالة دي.\n"
            "It works for 10 minutes. If you didn't ask for it, ignore this email.")
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:460px;margin:auto;padding:24px;border-radius:16px;
                background:#0E1630;color:#F3F5FA">
      <div><span style="display:inline-block;width:60px;height:6px;border-radius:3px;background:#2A78D6"></span>
           <span style="display:inline-block;width:40px;height:6px;border-radius:3px;background:#E3572E"></span>
           <span style="display:inline-block;width:50px;height:6px;border-radius:3px;background:#1B9E6B"></span></div>
      <h2 style="margin:16px 0 4px">Cairo Metro Ad Planner</h2>
      <p dir="rtl" style="margin:0;color:#AEB7C8">كود تأكيد الإيميل</p>
      <p style="font-size:34px;letter-spacing:8px;font-weight:bold;margin:18px 0;color:#F2C14E">{code}</p>
      <p dir="rtl" style="color:#AEB7C8;font-size:14px">الكود صالح لمدة 10 دقايق. لو مش انت اللي طلبته، تجاهل الرسالة دي.</p>
      <p style="color:#AEB7C8;font-size:14px">This code works for 10 minutes. If you didn't ask for it, ignore this email.</p>
    </div>"""
    if _brevo():
        _send_brevo(to, subject, text, html)
        return
    user = _secret("SMTP_USER")
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = subject, f"Cairo Metro Ad Planner <{user}>", to
    msg.set_content(text)
    msg.add_alternative(html, subtype="html")
    host = _secret("SMTP_HOST", "smtp.gmail.com")
    password = str(_secret("SMTP_PASSWORD")).replace(" ", "")  # Gmail shows app passwords in groups of 4
    port = int(_secret("SMTP_PORT", 465))
    try:
        with smtplib.SMTP_SSL(host, port, context=ssl.create_default_context(), timeout=20) as s:
            s.login(str(user).strip(), password)
            s.send_message(msg)
    except smtplib.SMTPAuthenticationError:
        raise
    except (OSError, smtplib.SMTPException):
        # some networks block port 465: try the other standard port (587 + STARTTLS)
        with smtplib.SMTP(host, 587, timeout=20) as s:
            s.starttls(context=ssl.create_default_context())
            s.login(str(user).strip(), password)
            s.send_message(msg)


def explain(err: Exception) -> str:
    """A plain reason for a failed send, without any secret in it."""
    text = str(err)
    if isinstance(err, BrevoError):
        body = err.body.lower()
        if err.status == 401 or "key not found" in body or "unauthorized" in body:
            return T("Brevo رفض المفتاح: اتأكدي إن BREVO_API_KEY منسوخ كامل (بيبدأ بـ xkeysib-) ومن غير مسافات.",
                     "Brevo refused the key: make sure BREVO_API_KEY is copied in full (starts with xkeysib-) with no spaces.")
        if "sender" in body:
            return T(f"Brevo مش معتبر {sender()} مرسل مؤكَّد: من Brevo ← Senders ضيفيه ودوسي على لينك التأكيد اللي يوصلك.",
                     f"Brevo doesn't treat {sender()} as a verified sender: add it in Brevo → Senders and click the confirmation link.")
        if "not yet activated" in body or "activate" in body or err.status == 403:
            return T("حساب Brevo لسه محتاج تفعيل للإرسال (Transactional). افتحي Brevo وكمّلي خطوات التفعيل.",
                     "The Brevo account still needs transactional sending activated. Open Brevo and finish the activation steps.")
        return f"Brevo {err.status}: {err.body[:160]}"
    if isinstance(err, urllib.error.URLError):
        return T("مقدرناش نوصل لـ Brevo دلوقتي. جربي تاني بعد شوية.", "Couldn't reach Brevo right now. Try again shortly.")
    if isinstance(err, smtplib.SMTPAuthenticationError) or "535" in text or "534" in text:
        return T("Gmail رفض الدخول: SMTP_PASSWORD لازم يكون **App Password** (16 حرف) مش باسورد Gmail العادي، "
                 "و SMTP_USER لازم يكون نفس الإيميل اللي عملتي منه الـ App Password، و2-Step Verification مفعّل.",
                 "Gmail refused the login: SMTP_PASSWORD must be an **App password** (16 letters), not the normal "
                 "Gmail password, SMTP_USER must be the account that created it, and 2-Step Verification must be on.")
    if isinstance(err, smtplib.SMTPRecipientsRefused):
        return T("Gmail رفض عنوان المستلم. اتأكد من الإيميل.", "Gmail refused the recipient address. Check the email.")
    if isinstance(err, (TimeoutError, ConnectionError, OSError)):
        return T("مقدرناش نوصل لسيرفر Gmail: Streamlit Cloud بيقفل SMTP. استخدمي Brevo (BREVO_API_KEY و EMAIL_FROM).",
                 "Couldn't reach the Gmail server: Streamlit Cloud blocks SMTP. Use Brevo (BREVO_API_KEY and EMAIL_FROM).")
    return f"{type(err).__name__}"


def send_test() -> str | None:
    """Admin check: send a test code to the sender address. Returns None on success, else the reason."""
    try:
        _send(sender(), "123456")
        return None
    except Exception as e:  # noqa: BLE001
        return explain(e)


def email_field(key: str, label: str, required: bool = True):
    """An email input with a 'send code' / 'check code' step. Returns (email, verified).
    When the app has no SMTP settings, verification is skipped and verified is None."""
    stt = st.session_state.setdefault(f"ev_{key}", {"sends": 0, "last": 0.0, "tries": 0, "hash": None,
                                                       "expires": 0.0, "verified": None})
    email = (st.text_input(label, placeholder="name@company.com", key=f"ev_{key}_email") or "").strip()

    if not configured():
        return email, None
    if not email:
        return email, False
    if stt["verified"] and stt["verified"].lower() == email.lower():
        cm.html('<p class="note" style="color:#5CC79C">✅ ' + T("الإيميل ده اتأكد.", "This email is verified.") + "</p>")
        return email, True
    if not EMAIL_RE.match(email):
        st.caption(T("الإيميل شكله مش مظبوط.", "That email doesn't look right."))
        return email, False

    c1, c2, c3 = st.columns([1.2, 1, 1], vertical_alignment="bottom")
    wait = int(COOLDOWN - (time.time() - stt["last"]))
    if c1.button(T("📧 ابعت كود التأكيد", "📧 Send code") if not stt["hash"] else T("📧 ابعت كود جديد", "📧 Send a new code"),
                 key=f"ev_{key}_send", use_container_width=True):
        if stt["sends"] >= MAX_SENDS:
            st.error(T("بعتنا أكواد كتير. حدّث الصفحة وجرب تاني بعد شوية.", "Too many codes sent. Reload the page and try again later."))
        elif wait > 0:
            st.warning(T(f"استنى {wait} ثانية قبل ما تطلب كود جديد.", f"Wait {wait} seconds before asking for a new code."))
        else:
            code = f"{secrets.randbelow(10 ** 6):06d}"
            try:
                _send(email, code)
            except Exception as e:  # noqa: BLE001
                st.error(T("مقدرناش نبعت الإيميل دلوقتي. ", "We couldn't send the email right now. ") + explain(e))
            else:
                stt.update(hash=_hash(email, code), expires=time.time() + CODE_TTL, last=time.time(), tries=0,
                           sends=stt["sends"] + 1, sent_to=email.lower())
                st.success(T(f"بعتنا كود من 6 أرقام لـ {email}. بص في الـ Inbox أو الـ Spam.",
                             f"We sent a 6-digit code to {email}. Check your inbox or spam folder."))
    code_in = c2.text_input(T("الكود", "Code"), max_chars=6, key=f"ev_{key}_code", placeholder="123456",
                            disabled=not stt["hash"])
    if c3.button(T("✔️ تأكيد", "✔️ Verify"), key=f"ev_{key}_check", use_container_width=True, disabled=not stt["hash"]):
        if time.time() > stt["expires"] or stt.get("sent_to") != email.lower():
            st.error(T("الكود ده انتهى أو اتبعت لإيميل تاني. اطلب كود جديد.", "That code expired or was sent to another email. Ask for a new one."))
        elif stt["tries"] >= MAX_TRIES:
            st.error(T("محاولات كتير غلط. اطلب كود جديد.", "Too many wrong tries. Ask for a new code."))
        elif hmac.compare_digest(_hash(email, (code_in or "").strip()), stt["hash"]):
            stt.update(verified=email, hash=None)
            st.rerun()
        else:
            stt["tries"] += 1
            st.error(T(f"الكود غلط. فاضل {MAX_TRIES - stt['tries']} محاولات.", f"Wrong code. {MAX_TRIES - stt['tries']} tries left."))
    if required:
        st.caption(T("لازم تأكد الإيميل قبل ما تبعت.", "You need to verify the email before sending."))
    return email, False
