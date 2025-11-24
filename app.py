from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory
import sqlite3
import os
from datetime import datetime
from dotenv import load_dotenv
import random
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


app = Flask(__name__)
app.secret_key = "supersecretkey"

load_dotenv()

# -----------------------
#SEND EMAIL CONFIG WITH ENVIRONMENT VARIABLES
# -----------------------


SENDER_EMAIL = os.getenv("SENDER_EMAIL")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")


def send_otp_email(receiver_email, otp):
    try:
        msg = MIMEMultipart()
        msg["From"] = SENDER_EMAIL
        msg["To"] = receiver_email
        msg["Subject"] = "Your OTP Verification Code"

        body = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        .box {{
            background: #f4f4f7;
            padding: 20px;
            border-radius: 8px;
            font-family: Arial, sans-serif;
            color: #333;
            border: 1px solid #ddd;
        }}
        .otp {{
            font-size: 32px;
            font-weight: bold;
            color: #0d6efd;
            text-align: center;
            margin: 20px 0;
        }}
        .title {{
            font-size: 20px;
            font-weight: 600;
            margin-bottom: 10px;
        }}
        .footer {{
            margin-top: 20px;
            font-size: 12px;
            color: #777;
            text-align: center;
        }}
    </style>
</head>
<body>

    <div class="box">
        <div class="title">OTP Verification</div>

        <p>Hello,</p>
        <p>Your One-Time Password (OTP) for account verification is:</p>

        <div class="otp">{otp}</div>

        <p>This OTP is valid for <b>5 minutes</b>. Do not share it with anyone.</p>

        <p>If you did not request this, please ignore this email.</p>

        <div class="footer">
            &copy; 2025 House Rental Management System
        </div>
    </div>

</body>
</html>
"""

        #msg.attach(MIMEText(body, "plain"))
        msg.attach(MIMEText(body, "html"))


        
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.ehlo()
        server.starttls()
        server.ehlo()

        

        server.login(SENDER_EMAIL, EMAIL_PASSWORD)


        server.sendmail(SENDER_EMAIL, receiver_email, msg.as_string())
        server.quit()

        print("Email sent successfully")

    except smtplib.SMTPAuthenticationError as e:
        print("AUTH ERROR:", e.smtp_error.decode())
        print("CODE:", e.smtp_code)
        raise

    except Exception as e:
        print("GENERAL ERROR:", e)
        raise



# -----------------------


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# -----------------------
# Database helper
# -----------------------
def get_db():
    conn = sqlite3.connect(os.path.join(BASE_DIR, "rental.db"))
    conn.row_factory = sqlite3.Row
    return conn



# -----------------------
# Home
# -----------------------
@app.route("/")
def home():
    return render_template("index.html")


# -----------------------
# Register
# -----------------------
@app.route("/register", methods=["GET", "POST"])
def register():

    # ---------------------------------------------
    # STEP 1 — FIRST TIME USER OPENS REGISTER PAGE
    # ---------------------------------------------
    if request.method == "GET":
        return render_template("register.html", stage="register")



    # ---------------------------------------------
    # STEP 2 — USER SUBMITS REGISTER FORM (NAME, EMAIL, etc.)
    # ---------------------------------------------
    if "otp_stage" not in session:

        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")
        number = request.form.get("number")
        role = request.form.get("role")

        # Generate OTP
        otp = str(random.randint(100000, 999999))

        # Store temporary user data in session
        session["temp_user"] = {
            "name": name,
            "email": email,
            "password": password,
            "number": number,
            "role": role,
            "otp": otp
        }

        # Send OTP email
        send_otp_email(email, otp)

        # Enable OTP stage
        session["otp_stage"] = True

        flash("OTP sent to your email! Enter the OTP below.")
        return render_template("register.html", stage="verify", email=email)



    # ---------------------------------------------
    # STEP 3 — OTP STAGE (VERIFY OR RESEND)
    # ---------------------------------------------
    if session.get("otp_stage"):

        # ------------------------
        # USER CLICKED RESEND OTP
        # ------------------------
        if request.form.get("resend"):
            new_otp = str(random.randint(100000, 999999))
            session["temp_user"]["otp"] = new_otp

            send_otp_email(session["temp_user"]["email"], new_otp)

            flash("A new OTP has been sent to your email!")
            return render_template(
                "register.html",
                stage="verify",
                email=session["temp_user"]["email"]
            )

        # ------------------------
        # NORMAL OTP VERIFICATION
        # ------------------------
        entered_otp = request.form.get("otp")
        real_otp = session["temp_user"]["otp"]

        if entered_otp == real_otp:

            user = session["temp_user"]

            conn = get_db()
            conn.execute("""
                INSERT INTO users(name, email, password, number, role, otp, is_verified)
                VALUES (?,?,?,?,?,?,1)
            """, (
                user["name"],
                user["email"],
                user["password"],
                user["number"],
                user["role"],
                real_otp
            ))
            conn.commit()
            conn.close()

            # Clear session temp data
            session.pop("temp_user")
            session.pop("otp_stage")

            flash("Registration completed! You can now log in.")
            return redirect(url_for("login"))

        else:
            flash("Invalid OTP! Try again.")
            return render_template(
                "register.html",
                stage="verify",
                email=session["temp_user"]["email"]
            )

# -----------------------
# Login
# -----------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE email=? AND password=?", (email, password)).fetchone()
        conn.close()

        if not user:
            flash("Invalid credentials")
            return redirect(url_for("login"))

        session["user_id"] = user["id"]
        session["role"] = user["role"]
        session["name"] = user["name"]

        if user["role"] == "admin":
            return redirect(url_for("admin_dashboard"))
        elif user["role"] == "owner":
            return redirect(url_for("owner_dashboard"))
        else:
            return redirect(url_for("user_dashboard"))
    return render_template("login.html")


# -----------------------
# Logout
# -----------------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# -----------------------
# Admin Dashboard
# -----------------------
@app.route("/admin/dashboard")
def admin_dashboard():
    if session.get("role") != "admin":
        return redirect(url_for("login"))

    conn = get_db()
    users = conn.execute("SELECT * FROM users").fetchall()
    properties = conn.execute("SELECT p.*, u.name as owner_name FROM properties p LEFT JOIN users u ON p.owner_id=u.id").fetchall()
    rents = conn.execute(
        "SELECT r.*, p.title as property_title, u_t.name as tenant_name, u_o.name as owner_name "
        "FROM rent_payments r "
        "LEFT JOIN properties p ON r.property_id=p.id "
        "LEFT JOIN users u_t ON r.tenant_id=u_t.id "
        "LEFT JOIN users u_o ON p.owner_id=u_o.id"
    ).fetchall()
    complaints = conn.execute(
        "SELECT c.*, p.title as property_title, u_t.name as tenant_name, u_o.name as owner_name "
        "FROM complaints c "
        "LEFT JOIN properties p ON c.property_id=p.id "
        "LEFT JOIN users u_t ON c.tenant_id=u_t.id "
        "LEFT JOIN users u_o ON p.owner_id=u_o.id"
    ).fetchall()
    conn.close()

    return render_template("admin_dashboard.html", users=users, properties=properties, rents=rents, complaints=complaints)


# -----------------------
# Owner Dashboard
# -----------------------
@app.route("/owner/dashboard")
def owner_dashboard():
    if session.get("role") != "owner":
        return redirect(url_for("login"))

    conn = get_db()
    properties = conn.execute("SELECT * FROM properties WHERE owner_id=?", (session["user_id"],)).fetchall()
    rents = conn.execute(
        "SELECT r.*, p.title as property_title, u.name as tenant_name "
        "FROM rent_payments r "
        "LEFT JOIN properties p ON r.property_id=p.id "
        "LEFT JOIN users u ON r.tenant_id=u.id "
        "WHERE p.owner_id=?",
        (session["user_id"],)
    ).fetchall()
    complaints = conn.execute(
        "SELECT c.*, p.title as property_title, u.name as tenant_name "
        "FROM complaints c LEFT JOIN properties p ON c.property_id=p.id LEFT JOIN users u ON c.tenant_id=u.id "
        "WHERE p.owner_id=?",
        (session["user_id"],)
    ).fetchall()
    conn.close()

    return render_template("owner_dashboard.html", properties=properties, rents=rents, complaints=complaints)


# -----------------------
# Add Property (Owner) - CREATE
# -----------------------
@app.route("/owner/add-property", methods=["GET", "POST"])
def add_property():
    if session.get("role") != "owner":
        return redirect(url_for("login"))

    if request.method == "POST":
        title = request.form.get("title")
        price = request.form.get("price")
        location = request.form.get("location")
        size = request.form.get("size")
        description = request.form.get("description")

        file = request.files.get("image")
        image_path = ""
        if file and file.filename:
            filename = f"{int(datetime.now().timestamp())}_{file.filename}"
            image_path = os.path.join("static", "uploads", filename)
            file.save(os.path.join(BASE_DIR, image_path))

        conn = get_db()
        conn.execute(
            "INSERT INTO properties (title, price, location, size, description, image, owner_id) VALUES (?,?,?,?,?,?,?)",
            (title, price, location, size, description, image_path, session["user_id"])
        )
        conn.commit()
        conn.close()

        flash("Property added.")
        return redirect(url_for("owner_dashboard"))

    return render_template("add_property.html")


# -----------------------
# Edit Property (Owner) - UPDATE
# -----------------------
@app.route("/owner/edit/<int:pid>", methods=["GET", "POST"])
def edit_property(pid):
    if session.get("role") != "owner":
        return redirect(url_for("login"))

    conn = get_db()
    prop = conn.execute("SELECT * FROM properties WHERE id=? AND owner_id=?", (pid, session["user_id"])).fetchone()
    if not prop:
        conn.close()
        flash("Property not found or unauthorized.")
        return redirect(url_for("owner_dashboard"))

    if request.method == "POST":
        title = request.form.get("title")
        price = request.form.get("price")
        location = request.form.get("location")
        size = request.form.get("size")
        description = request.form.get("description")

        file = request.files.get("image")
        image_path = prop["image"]
        if file and file.filename:
            filename = f"{int(datetime.now().timestamp())}_{file.filename}"
            image_path = os.path.join("static", "uploads", filename)
            file.save(os.path.join(BASE_DIR, image_path))

        conn.execute(
            "UPDATE properties SET title=?, price=?, location=?, size=?, description=?, image=? WHERE id=?",
            (title, price, location, size, description, image_path, pid)
        )
        conn.commit()
        conn.close()

        flash("Property updated.")
        return redirect(url_for("owner_dashboard"))

    conn.close()
    return render_template("edit_property.html", property=prop)


# -----------------------
# Delete Property (Owner) - DELETE
# -----------------------
@app.route("/owner/delete/<int:pid>")
def delete_property(pid):
    if session.get("role") != "owner":
        return redirect(url_for("login"))

    conn = get_db()
    # verify owner
    prop = conn.execute("SELECT * FROM properties WHERE id=? AND owner_id=?", (pid, session["user_id"])).fetchone()
    if not prop:
        conn.close()
        flash("Property not found or unauthorized.")
        return redirect(url_for("owner_dashboard"))

    conn.execute("DELETE FROM properties WHERE id=?", (pid,))
    conn.execute("DELETE FROM rent_payments WHERE property_id=?", (pid,))
    conn.execute("DELETE FROM complaints WHERE property_id=?", (pid,))
    conn.commit()
    conn.close()

    flash("Property and related records deleted.")
    return redirect(url_for("owner_dashboard"))


# -----------------------
# Owner: Add Monthly Rent for a Tenant
# -----------------------
@app.route("/owner/add-rent/<int:pid>", methods=["GET", "POST"])
def add_rent(pid):
    if session.get("role") != "owner":
        return redirect(url_for("login"))

    conn = get_db()
    prop = conn.execute("SELECT * FROM properties WHERE id=? AND owner_id=?", (pid, session["user_id"])).fetchone()
    if not prop:
        conn.close()
        flash("Property not found or unauthorized.")
        return redirect(url_for("owner_dashboard"))

    if request.method == "POST":
        tenant_id = request.form.get("tenant_id")  # tenant user id
        month = request.form.get("month")  # e.g., "March"
        year = int(request.form.get("year"))
        amount = float(request.form.get("amount"))

        conn.execute(
            "INSERT INTO rent_payments (property_id, tenant_id, month, year, amount, status, created_at) VALUES (?,?,?,?,?,?,?)",
            (pid, tenant_id, month, year, amount, "Unpaid", datetime.now().isoformat())
        )
        conn.commit()
        conn.close()
        flash("Monthly rent record added.")
        return redirect(url_for("owner_dashboard"))

    tenants = conn.execute("SELECT * FROM users WHERE role='user'").fetchall()
    conn.close()
    return render_template("add_rent.html", property=prop, tenants=tenants)


# -----------------------
# Tenant Dashboard (User)
# -----------------------
@app.route("/user/dashboard")
def user_dashboard():
    if session.get("role") != "user":
        return redirect(url_for("login"))

    conn = get_db()
    properties = conn.execute("SELECT * FROM properties").fetchall()
    rents = conn.execute(
        "SELECT r.*, p.title as property_title, u_o.name as owner_name "
        "FROM rent_payments r LEFT JOIN properties p ON r.property_id=p.id LEFT JOIN users u_o ON p.owner_id=u_o.id "
        "WHERE r.tenant_id=? ORDER BY r.year DESC, r.month DESC",
        (session["user_id"],)
    ).fetchall()
    conn.close()
    return render_template("user_dashboard.html", properties=properties, rents=rents)


# -----------------------
# Tenant: Pay Rent (simulate mark as paid)
# -----------------------
@app.route("/user/pay-rent/<int:rid>", methods=["POST"])
def pay_rent(rid):
    if session.get("role") != "user":
        return redirect(url_for("login"))

    conn = get_db()
    rent = conn.execute("SELECT * FROM rent_payments WHERE id=? AND tenant_id=?", (rid, session["user_id"])).fetchone()
    if not rent:
        conn.close()
        flash("Rent record not found or unauthorized.")
        return redirect(url_for("user_dashboard"))

    # For demo: we simply mark as Paid. Integrate payment gateway if needed.
    conn.execute("UPDATE rent_payments SET status='Paid', paid_at=? WHERE id=?", (datetime.now().isoformat(), rid))
    conn.commit()
    conn.close()

    flash("Payment recorded (marked as Paid).")
    return redirect(url_for("user_dashboard"))


# -----------------------
# Complaint: Tenant raises complaint
# -----------------------
@app.route("/user/complaint/<int:pid>", methods=["GET", "POST"])
def raise_complaint(pid):
    if session.get("role") != "user":
        return redirect(url_for("login"))

    if request.method == "POST":
        title = request.form.get("title")
        details = request.form.get("details")

        conn = get_db()
        conn.execute(
            "INSERT INTO complaints (property_id, tenant_id, title, details, status, created_at) VALUES (?,?,?,?,?,?)",
            (pid, session["user_id"], title, details, "Pending", datetime.now().isoformat())
        )
        conn.commit()
        conn.close()

        flash("Complaint submitted.")
        return redirect(url_for("user_dashboard"))

    conn = get_db()
    prop = conn.execute("SELECT * FROM properties WHERE id=?", (pid,)).fetchone()
    conn.close()
    return render_template("raise_complaint.html", property=prop)


# -----------------------
# Owner/Admin: Update Complaint Status
# -----------------------
@app.route("/complaint/update/<int:cid>", methods=["POST"])
def update_complaint(cid):
    role = session.get("role")
    if role not in ("owner", "admin"):
        return redirect(url_for("login"))

    new_status = request.form.get("status")  # Pending / In Progress / Resolved
    conn = get_db()

    # If owner, ensure complaint belongs to their property
    if role == "owner":
        c = conn.execute("SELECT c.* FROM complaints c JOIN properties p ON c.property_id=p.id WHERE c.id=? AND p.owner_id=?", (cid, session["user_id"])).fetchone()
        if not c:
            conn.close()
            flash("Unauthorized.")
            return redirect(url_for("owner_dashboard"))

    conn.execute("UPDATE complaints SET status=?, updated_at=? WHERE id=?", (new_status, datetime.now().isoformat(), cid))
    conn.commit()
    conn.close()

    flash("Complaint status updated.")
    if role == "admin":
        return redirect(url_for("admin_dashboard"))
    else:
        return redirect(url_for("owner_dashboard"))


# -----------------------
# Admin: Update Rent Status (mark Paid/Unpaid) or correct mistakes
# -----------------------
@app.route("/admin/update-rent/<int:rid>", methods=["POST"])
def admin_update_rent(rid):
    if session.get("role") != "admin":
        return redirect(url_for("login"))

    new_status = request.form.get("status")  # Paid / Unpaid
    conn = get_db()
    if new_status == "Paid":
        conn.execute("UPDATE rent_payments SET status='Paid', paid_at=? WHERE id=?", (datetime.now().isoformat(), rid))
    else:
        conn.execute("UPDATE rent_payments SET status='Unpaid', paid_at=NULL WHERE id=?", (rid,))
    conn.commit()
    conn.close()

    flash("Rent status updated.")
    return redirect(url_for("admin_dashboard"))


# -----------------------
# Serve uploaded images (optional)
# -----------------------
@app.route("/static/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)


# -----------------------
# Utility: view single property
# -----------------------
@app.route("/property/<int:pid>")
def view_property(pid):
    conn = get_db()
    prop = conn.execute("SELECT p.*, u.name as owner_name FROM properties p LEFT JOIN users u ON p.owner_id=u.id WHERE p.id=?", (pid,)).fetchone()
    conn.close()
    if not prop:
        flash("Property not found.")
        return redirect(url_for("home"))
    return render_template("view_property.html", property=prop)


# -----------------------
# Init DB (create tables) and run
# -----------------------
def init_db():
    db_file = os.path.join(BASE_DIR, "rental.db")
    if os.path.exists(db_file):
        return

    conn = sqlite3.connect(db_file)
    cur = conn.cursor()

    # users
    cur.execute("""
    CREATE TABLE users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        email TEXT UNIQUE,
        password TEXT,
        number TEXT,
        role TEXT,
        otp TEXT,
        is_verified INTEGER DEFAULT 0
    )
    """)

    # properties
    cur.execute("""
    CREATE TABLE properties (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        price TEXT,
        location TEXT,
        size TEXT,
        description TEXT,
        image TEXT,
        owner_id INTEGER
    )
    """)

    # rent payments
    cur.execute("""
    CREATE TABLE rent_payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        property_id INTEGER,
        tenant_id INTEGER,
        month TEXT,
        year INTEGER,
        amount REAL,
        status TEXT,         -- Paid / Unpaid
        created_at TEXT,
        paid_at TEXT
    )
    """)

    # complaints
    cur.execute("""
    CREATE TABLE complaints (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        property_id INTEGER,
        tenant_id INTEGER,
        title TEXT,
        details TEXT,
        status TEXT,        -- Pending / In Progress / Resolved
        created_at TEXT,
        updated_at TEXT
    )
    """)

    
    cur.execute("INSERT INTO users (name, email, password, role) VALUES (?,?,?,?)",
                ("Admin", "admin@gmail.com", "admin", "admin"))

    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    # set debug=False in production
    app.run(debug=True)
