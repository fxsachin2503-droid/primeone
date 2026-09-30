import io
import json
import os
from copy import deepcopy
import smtplib
import uuid
from copy import deepcopy
from datetime import datetime, timedelta
from email.message import EmailMessage
from email.utils import formataddr

from dotenv import load_dotenv
from flask import (
    Flask,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash
from authlib.integrations.flask_client import OAuth

try:
    from PIL import Image, ImageDraw, ImageFont
except Exception:
    Image = ImageDraw = ImageFont = None

load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-this-before-production")
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=30)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("SESSION_COOKIE_SECURE", "True").lower() == "true"
app.config["UPLOAD_FOLDER"] = os.path.join(app.root_path, "static", "uploads")
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

oauth = OAuth(app)

DATA_FILE = os.path.join(app.root_path, "data.json")
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "change-this-admin-password")
DISCORD_LINK_DEFAULT = os.environ.get("DISCORD_LINK", "https://discord.gg/Hm5V2bNxeq").strip()
DISCORD_CLIENT_ID = os.environ.get("DISCORD_CLIENT_ID", "").strip()
DISCORD_CLIENT_SECRET = os.environ.get("DISCORD_CLIENT_SECRET", "").strip()
DISCORD_REDIRECT_URI = os.environ.get("DISCORD_REDIRECT_URI", "").strip()
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()
GMAIL_SMTP_USER = os.environ.get("GMAIL_SMTP_USER", "").strip()
GMAIL_SMTP_APP_PASSWORD = os.environ.get("GMAIL_SMTP_APP_PASSWORD", "").strip()
AGREEMENT_RECEIVER_EMAIL = os.environ.get("AGREEMENT_RECEIVER_EMAIL", "").strip()
SUPPORT_EMAIL = os.environ.get("SUPPORT_EMAIL", "support.primeharbour@gmail.com").strip()

if GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET:
    oauth.register(
        name="google",
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )

if DISCORD_CLIENT_ID and DISCORD_CLIENT_SECRET:
    oauth.register(
        name="discord",
        client_id=DISCORD_CLIENT_ID,
        client_secret=DISCORD_CLIENT_SECRET,
        access_token_url="https://discord.com/api/oauth2/token",
        authorize_url="https://discord.com/oauth2/authorize",
        api_base_url="https://discord.com/api/",
        client_kwargs={"scope": "identify email"},
    )

DEFAULT_POLICY = (
    "Trading and market activity involves significant risk. Market conditions can change quickly because of "
    "economic events, liquidity, volatility, news and unexpected price movements. Historical information and "
    "illustrative calculations should not be treated as an indication of future results. Capital committed to a "
    "trading activity may be exposed to partial or substantial loss.\n\n"
    "PrimeHarbour presents a one-month capital term. Where the applicable written agreement provides for it, the "
    "capital-based percentage displayed on the website may be applied to the starting capital for that term. The "
    "exact calculation, timing, eligibility and treatment are controlled by the applicable written agreement.\n\n"
    "PrimeHarbour also presents a loss-refund percentage for qualifying losses, where applicable. Eligibility, "
    "calculation method, maximum applicable amount, timing, exclusions and documentation requirements are governed by "
    "the written agreement. A stated refund percentage does not mean that every loss is automatically reimbursed.\n\n"
    "Before participating, review the complete agreement, understand the risks, verify the applicable terms and make "
    "sure you are comfortable with the possibility of losing capital. Participation is voluntary. The website "
    "acknowledgement records a request for review and does not itself confirm acceptance of funds."
)

DEFAULT_SETTINGS = {
    "announcement": "",
    "monthly_growth": "",
    "monthly_slides": "JAN | Demo +7%\nFEB | Demo +1.4%\nMAR | Demo +5%\nAPR | Demo —\nMAY | Demo +4%\nJUN | Demo —\nJUL | Demo —\nAUG | Demo +7.2%",
    "profit_share": 40,
    "loss_refund": 40,
    "discord_link": DISCORD_LINK_DEFAULT,
    "discord_ticket_url": "",
    "support_email": os.environ.get("SUPPORT_EMAIL", "support@primeharbour.com"),
    "agreement_version": "1.0",
    "policy_text": DEFAULT_POLICY,
    "tagline": "Invest Smarter. Live Better.",
}

DEFAULT_DATA = {
    "settings": deepcopy(DEFAULT_SETTINGS),
    "users": [],
    "investment_requests": [],
}


def load_data():
    data = deepcopy(DEFAULT_DATA)
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as fh:
                loaded = json.load(fh)
            if isinstance(loaded, dict):
                # Keep useful existing account/request data while dropping the old public-content model.
                for key in ("users", "investment_requests"):
                    if isinstance(loaded.get(key), list):
                        data[key] = loaded[key]
                loaded_settings = loaded.get("settings") if isinstance(loaded.get("settings"), dict) else {}
                merged = deepcopy(DEFAULT_SETTINGS)
                merged.update(loaded_settings)
                data["settings"] = merged
        except (OSError, json.JSONDecodeError):
            pass
    for key in ("users", "investment_requests"):
        if not isinstance(data.get(key), list):
            data[key] = []
    return data


def save_data(data):
    clean = {
        "settings": data.get("settings", deepcopy(DEFAULT_SETTINGS)),
        "users": data.get("users", []),
        "investment_requests": data.get("investment_requests", []),
    }
    temp = DATA_FILE + ".tmp"
    with open(temp, "w", encoding="utf-8") as fh:
        json.dump(clean, fh, indent=2, ensure_ascii=False)
    os.replace(temp, DATA_FILE)


def now_text():
    return datetime.now().strftime("%d %B %Y, %I:%M %p")


def current_user():
    return session.get("username")


def is_admin():
    return bool(session.get("is_admin"))


def login_user(username, admin=False, provider="local"):
    session.clear()
    session.permanent = True
    session["username"] = username
    session["is_admin"] = admin
    session["provider"] = provider


def require_admin():
    if not is_admin():
        flash("Admin access only.")
        return False
    return True


def create_unique_username(data, preferred_name):
    base = str(preferred_name or "user").strip().replace(" ", "_")
    base = "".join(ch for ch in base if ch.isalnum() or ch in "_-") or "user"
    username = base
    counter = 1
    existing = {str(u.get("username", "")).lower() for u in data["users"]}
    while username.lower() in existing:
        counter += 1
        username = f"{base}{counter}"
    return username


def find_or_create_oauth_user(provider, provider_id, email, preferred_name):
    data = load_data()
    provider_id = str(provider_id)
    for user in data["users"]:
        if user.get("provider") == provider and str(user.get("provider_id", "")) == provider_id:
            return user
    if email:
        for user in data["users"]:
            if str(user.get("email", "")).lower() == email.lower():
                user["provider"] = provider
                user["provider_id"] = provider_id
                save_data(data)
                return user
    username = create_unique_username(data, preferred_name)
    user = {
        "id": uuid.uuid4().hex,
        "username": username,
        "email": email or "",
        "password": "",
        "provider": provider,
        "provider_id": provider_id,
        "joined": now_text(),
    }
    data["users"].append(user)
    save_data(data)
    return user


def bounded_number(value, default, minimum=0, maximum=100):
    try:
        n = float(value)
    except (TypeError, ValueError):
        return default
    n = max(minimum, min(maximum, n))
    return int(n) if n.is_integer() else n


def build_agreement_png(info):
    if Image is None:
        return None
    width, margin = 1400, 90
    try:
        title_font = ImageFont.load_default(size=42)
        body_font = ImageFont.load_default(size=28)
        small_font = ImageFont.load_default(size=23)
    except TypeError:
        title_font = body_font = small_font = ImageFont.load_default()

    paragraphs = [
        "PRIMEHARBOUR — PARTICIPATION ACKNOWLEDGEMENT",
        f"Agreement version: {info['agreement_version']}",
        "",
        f"Participant: {info['full_name']}",
        f"Email: {info['email']}",
        f"Requested amount: {info['amount_display']}",
        f"Website account: {info['username'] or 'Guest'}",
        f"Submitted: {info['submitted_at']}",
        f"Request ID: {info['request_id']}",
        "",
        "Participant acknowledgement:",
        "I confirm that I reviewed the PrimeHarbour participation information and the applicable written terms.",
        "I understand that market activity involves risk and that profit-share and loss-refund treatment is subject to the applicable agreement and eligibility conditions.",
        "I understand that this acknowledgement records my request and does not by itself confirm acceptance of funds.",
    ]
    wrapped = []
    for text in paragraphs:
        if not text:
            wrapped.append("")
            continue
        line = ""
        for word in text.split():
            candidate = (line + " " + word).strip()
            if body_font.getlength(candidate) > width - margin * 2:
                wrapped.append(line)
                line = word
            else:
                line = candidate
        if line:
            wrapped.append(line)
    height = max(900, margin * 2 + len(wrapped) * 46 + 140)
    img = Image.new("RGB", (width, height), "#f5f0e5")
    draw = ImageDraw.Draw(img)
    y = margin
    draw.text((margin, y), wrapped[0], fill="#101513", font=title_font)
    y += 85
    for line in wrapped[1:]:
        if not line:
            y += 22
            continue
        draw.text((margin, y), line, fill="#252922", font=body_font)
        y += 46
    draw.line((margin, height - 90, width - margin, height - 90), fill="#c6a75a", width=3)
    draw.text((margin, height - 70), "PrimeHarbour · website-generated record", fill="#6d675c", font=small_font)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def send_agreement_email(info, png_bytes):
    if not (GMAIL_SMTP_USER and GMAIL_SMTP_APP_PASSWORD and AGREEMENT_RECEIVER_EMAIL):
        return False, "Request saved. Email delivery is not configured."
    msg = EmailMessage()
    msg["Subject"] = f"PrimeHarbour Agreement — {info['full_name']}"
    msg["From"] = formataddr(("PrimeHarbour", GMAIL_SMTP_USER))
    msg["To"] = AGREEMENT_RECEIVER_EMAIL
    msg.set_content(
        "A PrimeHarbour participation acknowledgement was submitted.\n\n"
        f"Participant: {info['full_name']}\n"
        f"Email: {info['email']}\n"
        f"Amount: {info['amount_display']}\n"
        f"Username: {info['username'] or 'Guest'}\n"
        f"Agreement version: {info['agreement_version']}\n"
        f"Profit-share at request: {info['profit_share_at_request']}%\n"
        f"Loss-refund at request: {info['loss_refund_at_request']}%\n"
        f"Submitted: {info['submitted_at']}\n"
        f"Request ID: {info['request_id']}\n"
    )
    if png_bytes:
        msg.add_attachment(png_bytes, maintype="image", subtype="png", filename="primeharbour-agreement.png")
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=20) as smtp:
            smtp.login(GMAIL_SMTP_USER, GMAIL_SMTP_APP_PASSWORD)
            smtp.send_message(msg)
        return True, "Request saved and acknowledgement emailed."
    except Exception:
        app.logger.exception("Gmail delivery failed")
        return False, "Request saved, but acknowledgement email delivery failed."



def send_support_email(info):
    if not (GMAIL_SMTP_USER and GMAIL_SMTP_APP_PASSWORD and SUPPORT_EMAIL):
        return False, "Support request could not be emailed because Gmail support is not configured yet."

    msg = EmailMessage()
    msg["Subject"] = f"PrimeHarbour Support — {info['subject']}"
    msg["From"] = formataddr(("PrimeHarbour Support", GMAIL_SMTP_USER))
    msg["To"] = SUPPORT_EMAIL
    msg["Reply-To"] = info["email"]
    msg.set_content(
        "A new PrimeHarbour support request was submitted.\n\n"
        f"Name: {info['name']}\n"
        f"Email: {info['email']}\n"
        f"Subject: {info['subject']}\n"
        f"Submitted: {info['submitted_at']}\n"
        f"Website username: {info['username'] or 'Guest'}\n\n"
        "Message:\n"
        f"{info['message']}\n\n"
        "Please reply to the visitor's email address using Reply-To."
    )

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=20) as smtp:
            smtp.login(GMAIL_SMTP_USER, GMAIL_SMTP_APP_PASSWORD)
            smtp.send_message(msg)
        return True, "Your support request has been sent. The PrimeHarbour team will contact you by email."
    except Exception:
        app.logger.exception("Support email delivery failed")
        return False, "The support request could not be delivered right now. Please try again later."


@app.context_processor
def inject_globals():
    data = load_data()
    settings = data["settings"]
    return {
        "brand": "PrimeHarbour",
        "current_username": current_user(),
        "current_is_admin": is_admin(),
        "discord_link": settings.get("discord_link", DISCORD_LINK_DEFAULT),
        "settings": settings,
        "current_year": datetime.now().year,
        "google_login_enabled": bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET),
        "discord_login_enabled": bool(DISCORD_CLIENT_ID and DISCORD_CLIENT_SECRET and DISCORD_REDIRECT_URI),
    }


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/about")
def about():
    return render_template("about.html")



@app.route("/discord")
def discord():
    return render_template("discord.html")


@app.route("/invest")
def invest():
    return render_template("invest.html")


@app.route("/invest/model")
def model_detail():
    return render_template("plan_detail.html")


@app.route("/invest/<path:legacy>")
def legacy_plan(legacy):
    return redirect(url_for("invest") + "#model")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if len(username) < 3 or "@" not in email or len(password) < 6:
            flash("Use a username of at least 3 characters, a valid email and a password of at least 6 characters.")
            return redirect(url_for("signup"))
        data = load_data()
        if any(str(u.get("username", "")).lower() == username.lower() for u in data["users"]):
            flash("Username already exists.")
            return redirect(url_for("signup"))
        if any(str(u.get("email", "")).lower() == email for u in data["users"]):
            flash("Email already exists.")
            return redirect(url_for("signup"))
        data["users"].append({
            "id": uuid.uuid4().hex,
            "username": username,
            "email": email,
            "password": generate_password_hash(password),
            "provider": "local",
            "provider_id": "",
            "joined": now_text(),
        })
        save_data(data)
        login_user(username, provider="local")
        flash("Account created successfully.")
        return redirect(url_for("home"))
    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            login_user(ADMIN_USERNAME, admin=True, provider="admin")
            flash("Admin login successful.")
            return redirect(url_for("admin"))
        data = load_data()
        for user in data["users"]:
            stored = user.get("password", "")
            if stored and str(user.get("username", "")).lower() == username.lower() and check_password_hash(stored, password):
                login_user(user["username"], provider=user.get("provider", "local"))
                flash("Login successful.")
                return redirect(url_for("home"))
        flash("Invalid username or password.")
        return redirect(url_for("login"))
    return render_template("login.html")


@app.route("/login/google")
def login_google():
    if not (GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET):
        flash("Google login is not configured yet.")
        return redirect(url_for("login"))
    return oauth.google.authorize_redirect(url_for("auth_google", _external=True), prompt="select_account")


@app.route("/auth/google")
def auth_google():
    try:
        token = oauth.google.authorize_access_token()
        info = token.get("userinfo") or oauth.google.parse_id_token(token)
        if not info or not info.get("sub"):
            raise RuntimeError("Google account information was not returned.")
        email = info.get("email", "")
        name = info.get("name") or info.get("given_name") or (email.split("@")[0] if email else "GoogleUser")
        user = find_or_create_oauth_user("google", info["sub"], email, name)
        login_user(user["username"], provider="google")
        flash("Google login successful.")
    except Exception:
        app.logger.exception("Google login failed")
        flash("Google login failed. Please try again.")
    return redirect(url_for("home"))


@app.route("/login/discord")
def login_discord():
    if not (DISCORD_CLIENT_ID and DISCORD_CLIENT_SECRET and DISCORD_REDIRECT_URI):
        flash("Discord login is not configured yet.")
        return redirect(url_for("login"))
    session.clear()
    session.permanent = True
    try:
        return oauth.discord.authorize_redirect(DISCORD_REDIRECT_URI)
    except Exception:
        app.logger.exception("Discord authorize failed")
        flash("Could not start Discord login.")
        return redirect(url_for("login"))


@app.route("/auth/discord/callback")
def auth_discord():
    if request.args.get("error"):
        flash("Discord login was cancelled or denied.")
        return redirect(url_for("login"))
    try:
        token = oauth.discord.authorize_access_token()
        response = oauth.discord.get("users/@me", token=token)
        if response.status_code != 200:
            raise RuntimeError("Discord user request failed.")
        info = response.json()
        if not info.get("id"):
            raise RuntimeError("Discord user ID was not returned.")
        email = info.get("email", "")
        name = info.get("global_name") or info.get("username") or "DiscordUser"
        user = find_or_create_oauth_user("discord", info["id"], email, name)
        login_user(user["username"], provider="discord")
        flash("Discord login successful.")
    except Exception:
        app.logger.exception("Discord login failed")
        flash("Discord login failed. Please try again.")
    return redirect(url_for("home"))


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.")
    return redirect(url_for("home"))


@app.post("/investment-request")
def investment_request():
    full_name = request.form.get("full_name", "").strip()[:120]
    email = request.form.get("email", "").strip().lower()[:160]
    amount_raw = request.form.get("amount", "").strip()
    accepted = request.form.get("agreement_ack") == "on"
    if len(full_name) < 2 or "@" not in email or not accepted:
        flash("Please enter your name and email and accept the acknowledgement before continuing.")
        return redirect(url_for("home") + "#participate")
    try:
        amount_value = float(amount_raw)
        if amount_value <= 0 or amount_value > 1_000_000_000:
            raise ValueError
    except ValueError:
        flash("Please enter a valid requested amount.")
        return redirect(url_for("home") + "#participate")

    data = load_data()
    settings = data["settings"]
    request_id = uuid.uuid4().hex
    record = {
        "id": request_id,
        "status": "New",
        "full_name": full_name,
        "email": email,
        "amount": amount_value,
        "amount_display": f"${amount_value:,.2f}",
        "username": current_user() or "",
        "provider": session.get("provider", ""),
        "submitted_at": now_text(),
        "agreement_version": settings.get("agreement_version", "1.0"),
        "agreement_acknowledged": True,
        "profit_share_at_request": settings.get("profit_share", 40),
        "loss_refund_at_request": settings.get("loss_refund", 40),
    }
    data["investment_requests"].insert(0, record)
    save_data(data)

    sent, message = send_agreement_email(record, build_agreement_png(record))
    flash(message)
    ticket_url = settings.get("discord_ticket_url") or settings.get("discord_link") or DISCORD_LINK_DEFAULT
    return redirect(ticket_url)



@app.route("/support", methods=["GET", "POST"])
def support():
    if request.method == "POST":
        name = request.form.get("name", "").strip()[:120]
        email = request.form.get("email", "").strip()[:160]
        subject = request.form.get("subject", "").strip()[:160]
        message = request.form.get("message", "").strip()[:5000]
        website = request.form.get("website", "").strip()  # honeypot

        if website:
            flash("Your support request could not be submitted.")
            return redirect(url_for("support"))

        if (
            len(name) < 2
            or "@" not in email
            or "\r" in email
            or "\n" in email
            or len(subject) < 2
            or len(message) < 10
        ):
            flash("Please provide a valid name, email, subject and message.")
            return redirect(url_for("support"))

        info = {
            "name": name,
            "email": email,
            "subject": subject,
            "message": message,
            "username": current_user() or "",
            "submitted_at": now_text(),
        }

        sent, message_text = send_support_email(info)
        flash(message_text)
        return redirect(url_for("support"))

    return render_template(
        "support.html",
        support_email=SUPPORT_EMAIL or "support.primeharbour@gmail.com",
    )

@app.route("/admin", methods=["GET", "POST"])
def admin():
    if not require_admin():
        return redirect(url_for("login"))
    data = load_data()
    if request.method == "POST":
        action = request.form.get("action", "save_settings")
        if action == "save_settings":
            settings = data["settings"]
            settings["announcement"] = request.form.get("announcement", "").strip()[:500]
            settings["monthly_growth"] = request.form.get("monthly_growth", "").strip()[:80]
            settings["monthly_slides"] = request.form.get("monthly_slides", "").strip()[:2000]
            settings["profit_share"] = bounded_number(request.form.get("profit_share"), settings.get("profit_share", 40))
            settings["loss_refund"] = bounded_number(request.form.get("loss_refund"), settings.get("loss_refund", 40))
            settings["discord_link"] = request.form.get("discord_link", "").strip() or DISCORD_LINK_DEFAULT
            settings["discord_ticket_url"] = request.form.get("discord_ticket_url", "").strip()
            settings["support_email"] = request.form.get("support_email", "").strip() or "support@primeharbour.com"
            settings["agreement_version"] = request.form.get("agreement_version", "1.0").strip()[:30] or "1.0"
            settings["tagline"] = request.form.get("tagline", "Invest Smarter. Live Better.").strip()[:120]
            settings["policy_text"] = request.form.get("policy_text", "").strip()[:7000] or DEFAULT_POLICY
            save_data(data)
            flash("PrimeHarbour settings saved.")
            return redirect(url_for("admin"))
        if action == "update_request":
            request_id = request.form.get("request_id", "")
            status = request.form.get("status", "New")
            allowed = {"New", "Reviewing", "Approved", "Declined", "Completed"}
            if status in allowed:
                for item in data["investment_requests"]:
                    if item.get("id") == request_id:
                        item["status"] = status
                        item["status_updated_at"] = now_text()
                        break
                save_data(data)
                flash("Request status updated.")
            return redirect(url_for("admin") + "#requests")
    return render_template("admin.html", requests=data["investment_requests"])


@app.route("/health")
def health():
    return jsonify({"ok": True, "service": "PrimeHarbour"})


@app.route("/service-worker.js")
def service_worker():
    return send_from_directory(os.path.join(app.root_path, "static"), "service-worker.js", mimetype="application/javascript")


# Old URLs are kept only as harmless redirects so old bookmarks do not create template errors.
@app.route("/news")
def old_news():
    return redirect(url_for("home"))


@app.route("/journal")
def old_journal():
    return redirect(url_for("home"))


@app.route("/trades")
def old_trades():
    return redirect(url_for("home"))


@app.errorhandler(404)
def not_found(error):
    return render_template("404.html"), 404


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)
