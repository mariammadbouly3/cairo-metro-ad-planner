"""Email verification: send a 6-digit code, check it, and remember the verified address for this visit.

Needs these app secrets (Streamlit Cloud → app → Settings → Secrets):
    SMTP_USER = "you@gmail.com"          # the address the codes are sent from
    SMTP_PASSWORD = "xxxx xxxx xxxx xxxx" # a Gmail *App password*, not the normal password
Optional: SMTP_HOST (default smtp.gmail.com), SMTP_PORT (default 465).
Without them, the forms still work and simply skip verification.
"""
from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import smtplib
import ssl
import time
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


def configured() -> bool:
    return bool(_secret("SMTP_USER") and _secret("SMTP_PASSWORD"))


def _hash(email: str, code: str) -> str:
    return hashlib.sha256(f"{email.lower()}|{code}".encode()).hexdigest()


def _send(to: str, code: str):
    user = _secret("SMTP_USER")
    msg = EmailMessage()
    msg["Subject"] = f"{code} كود التأكيد · Your verification code"
    msg["From"] = f"Cairo Metro Ad Planner <{user}>"
    msg["To"] = to
    msg.set_content(f"كود التأكيد بتاعك: {code}\nYour verification code: {code}\n\n"
                    "الكود صالح لمدة 10 دقايق. لو مش انت اللي طلبته، تجاهل الرسالة دي.\n"
                    "It works for 10 minutes. If you didn't ask for it, ignore this email.")
    msg.add_alternative(f"""
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
    </div>""", subtype="html")
    host, port = _secret("SMTP_HOST", "smtp.gmail.com"), int(_secret("SMTP_PORT", 465))
    with smtplib.SMTP_SSL(host, port, context=ssl.create_default_context(), timeout=20) as s:
        s.login(user, _secret("SMTP_PASSWORD"))
        s.send_message(msg)


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
            except Exception:  # noqa: BLE001
                st.error(T("مقدرناش نبعت الإيميل دلوقتي. اتأكد من العنوان وجرب تاني.",
                           "We couldn't send the email right now. Check the address and try again."))
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
