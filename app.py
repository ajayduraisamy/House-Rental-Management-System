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

        msg.attach(MIMEText(body, "html"))

        #print("SMTP Connecting...")
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.ehlo()
        server.starttls()
        server.ehlo()

        #print("SMTP Logging in...")
        server.login(SENDER_EMAIL, EMAIL_PASSWORD)

        #print("SMTP Sending email...")
        server.sendmail(SENDER_EMAIL, receiver_email, msg.as_string())
        server.quit()

        print("EMAIL SENT SUCCESSFULLY")

    except smtplib.SMTPAuthenticationError as e:
        print("AUTH ERROR:", e.smtp_error.decode())
        print("CODE:", e.smtp_code)
        raise

    except Exception as e:
        print("GENERAL ERROR:", e)
        raise


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

    if request.method == "GET":
        print("GET /register → Resetting Session")
        session.pop("otp_stage", None)
        session.pop("temp_user", None)
        return render_template("register.html", stage="register")


    if "otp_stage" not in session:

        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")
        number = request.form.get("number")
        role = request.form.get("role")

        print("STEP 2: Received REGISTER form:")
        print("Name:", name, "Email:", email)

    
        conn = get_db()
        existing = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if existing:
            print("Email already exists:", email)
            flash("Email already registered.")
            return render_template("register.html", stage="register")

    
        otp = str(random.randint(100000, 999999))
        print("STEP 2: OTP GENERATED :", otp)

    
        session["temp_user"] = {
            "name": name,
            "email": email,
            "password": password,
            "number": number,
            "role": role,
            "otp": otp
        }

        
        send_otp_email(email, otp)

    
        session["otp_stage"] = True

        flash("OTP sent to your email!")
        return render_template("register.html", stage="verify", email=email)

    if session.get("otp_stage"):

    
        if request.form.get("resend"):
            new_otp = str(random.randint(100000, 999999))
            session["temp_user"]["otp"] = new_otp
            print("STEP 3: RESEND OTP:", new_otp)

            send_otp_email(session["temp_user"]["email"], new_otp)

            flash("New OTP sent!")
            return render_template("register.html", stage="verify", email=session["temp_user"]["email"])

    
        entered_otp = request.form.get("otp")
        real_otp = session["temp_user"]["otp"]

        print("STEP 3: ENTERED:", entered_otp, "REAL:", real_otp)

        if entered_otp == real_otp:
            user = session["temp_user"]

            conn = get_db()
            conn.execute("""
                INSERT INTO users(name, email, password, number, role, otp, is_verified)
                VALUES (?,?,?,?,?,?,1)
            """, (user["name"], user["email"], user["password"], user["number"], user["role"], real_otp))
            conn.commit()
            conn.close()

            session.pop("temp_user")
            session.pop("otp_stage")

            print("STEP 3: OTP VERIFIED → USER REGISTERED")
            flash("Registration successful!")
            return redirect(url_for("login"))

        else:
            print("STEP 3: WRONG OTP")
            flash("Invalid OTP!")
            return render_template("register.html", stage="verify", email=session["temp_user"]["email"])


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
            flash("Invalid email or password.")
            return redirect(url_for("login"))

    
        if user["is_verified"] == 0:
            flash("Your email is not verified yet. Please complete OTP verification.")
            return redirect(url_for("register"))

        
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
# forgot password
# -----------------------
@app.route("/forgot", methods=["GET", "POST"])
def forgot():

    
    if request.method == "GET":
        session.pop("reset_stage", None)
        session.pop("reset_data", None)
        return render_template("forgot.html", stage="email")



    if "reset_stage" not in session:

        email = request.form.get("email")

        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        conn.close()

        if not user:
            flash("Email not found!")
            return render_template("forgot.html", stage="email")

        
        otp = str(random.randint(100000, 999999))

        
        session["reset_data"] = {
            "email": email,
            "otp": otp
        }

        send_otp_email(email, otp)

        session["reset_stage"] = "otp"

        flash("OTP has been sent to your email!")
        return render_template("forgot.html", stage="otp", email=email)


    
    if session["reset_stage"] == "otp":

    
        if request.form.get("resend"):
            new_otp = str(random.randint(100000, 999999))
            session["reset_data"]["otp"] = new_otp
            send_otp_email(session["reset_data"]["email"], new_otp)

            flash("New OTP sent!")
            return render_template("forgot.html", stage="otp", email=session["reset_data"]["email"])

        
        entered_otp = request.form.get("otp")
        real_otp = session["reset_data"]["otp"]

        if entered_otp != real_otp:
            flash("Invalid OTP!")
            return render_template("forgot.html", stage="otp", email=session["reset_data"]["email"])

        
        session["reset_stage"] = "reset_pass"
        flash("OTP Verified! Enter your new password.")
        return render_template("forgot.html", stage="reset_pass")



    if session["reset_stage"] == "reset_pass":

        new_pass = request.form.get("password")
        email = session["reset_data"]["email"]

        conn = get_db()
        conn.execute("UPDATE users SET password=? WHERE email=?", (new_pass, email))
        conn.commit()
        conn.close()

        session.pop("reset_data")
        session.pop("reset_stage")

        flash("Password updated successfully! Login now.")
        return redirect(url_for("login"))




# -----------------------------------------
# OWNER DASHBOARD
# -----------------------------------------
@app.route("/owner/dashboard")
def owner_dashboard():
    if session.get("role") != "owner":
        return redirect(url_for("login"))

    conn = get_db()

    
    properties = conn.execute(
        "SELECT * FROM properties WHERE owner_id=?",
        (session["user_id"],)
    ).fetchall()

    
    rents = conn.execute("""
        SELECT r.*, p.title AS property_title, u.name AS tenant_name
        FROM rent_payments r
        JOIN properties p ON r.property_id = p.id
        JOIN users u ON r.tenant_id = u.id
        WHERE p.owner_id = ?
        ORDER BY r.year DESC, r.month DESC
    """, (session["user_id"],)).fetchall()

    
    complaints = conn.execute("""
        SELECT c.*, p.title AS property_title, u.name AS tenant_name
        FROM complaints c
        JOIN properties p ON c.property_id = p.id
        JOIN users u ON c.tenant_id = u.id
        WHERE p.owner_id = ?
        ORDER BY c.id DESC
    """, (session["user_id"],)).fetchall()

    conn.close()

    return render_template(
        "owner_dashboard.html",
        properties=properties,
        rents=rents,
        complaints=complaints
    )


# -----------------------
# Onwer create property
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
           file.save(os.path.join(UPLOAD_FOLDER, filename))
           image_path = filename  


        conn = get_db()
        conn.execute("""
            INSERT INTO properties(title, price, location, size, description, image, owner_id)
            VALUES (?,?,?,?,?,?,?)
        """, (title, price, location, size, description, image_path, session["user_id"]))
        conn.commit()
        conn.close()

        flash("Property added successfully.")
        return redirect(url_for("owner_dashboard"))

    return render_template("add_property.html")


# -----------------------
# onwer edit propery
# -----------------------

@app.route("/owner/edit/<int:pid>", methods=["GET", "POST"])
def edit_property(pid):
    if session.get("role") != "owner":
        return redirect(url_for("login"))

    conn = get_db()
    prop = conn.execute(
        "SELECT * FROM properties WHERE id=? AND owner_id=?",
        (pid, session["user_id"])
    ).fetchone()

    if not prop:
        flash("Unauthorized or property not found.")
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
            file.save(os.path.join(UPLOAD_FOLDER, filename))
            image_path = filename   

        conn.execute("""
            UPDATE properties
            SET title=?, price=?, location=?, size=?, description=?, image=?
            WHERE id=?
        """, (title, price, location, size, description, image_path, pid))

        conn.commit()
        conn.close()

        flash("Property updated successfully.")
        return redirect(url_for("owner_dashboard"))

    conn.close()
    return render_template("edit_property.html", property=prop)




# -----------------------------------------
# OWNER APPROVES USER BOOKING (AUTO CREATE RENT)
# -----------------------------------------
@app.route("/owner/approve-booking/<int:bid>")
def approve_booking(bid):
    if session.get("role") != "owner":
        return redirect(url_for("login"))

    conn = get_db()
    booking = conn.execute("""
        SELECT b.*, p.price, p.owner_id
        FROM bookings b
        JOIN properties p ON b.property_id = p.id
        WHERE b.id = ?
    """, (bid,)).fetchone()

    if not booking or booking["owner_id"] != session["user_id"]:
        flash("Unauthorized or invalid booking.")
        conn.close()
        return redirect(url_for("owner_bookings"))

    # Approve booking (keeps status Approved)
    conn.execute("UPDATE bookings SET status='Approved' WHERE id=?", (bid,))

    conn.commit()
    conn.close()

    flash("Booking approved. Please create an agreement for the tenant.")
    # Redirect owner to create agreement page immediately
    return redirect(url_for("owner_create_agreement", bid=bid))

# Owner: create agreement for a booking
@app.route("/owner/create-agreement/<int:bid>", methods=["GET", "POST"])
def owner_create_agreement(bid):
    if session.get("role") != "owner":
        return redirect(url_for("login"))

    conn = get_db()
    booking = conn.execute("""
        SELECT b.*, p.title AS property_title, p.id AS property_id, p.price AS prop_price, p.owner_id, u.name AS tenant_name, u.id as tenant_id
        FROM bookings b
        JOIN properties p ON b.property_id = p.id
        JOIN users u ON b.tenant_id = u.id
        WHERE b.id=?
    """, (bid,)).fetchone()

    if not booking or booking["owner_id"] != session["user_id"]:
        conn.close()
        flash("Invalid booking or unauthorized.")
        return redirect(url_for("owner_bookings"))

    if request.method == "POST":
        years = int(request.form.get("years") or 1)
        advance = float(request.form.get("advance") or 0)
        monthly_rent = float(request.form.get("monthly_rent") or booking["prop_price"] or 0)
        terms = request.form.get("terms") or ""
        pdf_file = request.files.get("agreement_pdf")
        pdf_path = None

        if pdf_file and pdf_file.filename:
            filename = f"agreement_{int(datetime.now().timestamp())}_{pdf_file.filename}"
            pdf_file.save(os.path.join(UPLOAD_FOLDER, filename))
            pdf_path = filename

        conn.execute("""
            INSERT INTO agreements(booking_id, property_id, owner_id, tenant_id, years, advance_amount, monthly_rent, terms, pdf_path, status, created_at)
            VALUES(?,?,?,?,?,?,?,?,?, 'Pending', ?)
        """, (bid, booking["property_id"], booking["owner_id"], booking["tenant_id"], years, advance, monthly_rent, terms, pdf_path, datetime.now().isoformat()))

        conn.commit()
        conn.close()

        flash("Agreement created and sent to tenant. Waiting for their acceptance.")
        return redirect(url_for("owner_bookings"))

    conn.close()
    return render_template("owner_create_agreement.html", booking=booking)


# -----------------------
# onwer bookings particulor user
# -----------------------
@app.route("/owner/bookings")
def owner_bookings():
    if session.get("role") != "owner":
        return redirect(url_for("login"))

    conn = get_db()
    bookings = conn.execute("""
        SELECT b.*, 
               p.title AS property_title,
               u.name AS tenant_name
        FROM bookings b
        JOIN properties p ON b.property_id = p.id
        JOIN users u ON b.tenant_id = u.id
        WHERE p.owner_id=?
        ORDER BY b.id DESC
    """, (session["user_id"],)).fetchall()
    conn.close()

    return render_template("owner_bookings.html", bookings=bookings)

# -----------------------
# onwer booking reject
# -----------------------
@app.route("/owner/reject-booking/<int:bid>")
def reject_booking(bid):
    if session.get("role") != "owner":
        return redirect(url_for("login"))

    conn = get_db()


    booking = conn.execute("""
        SELECT b.*, p.owner_id
        FROM bookings b
        JOIN properties p ON b.property_id = p.id
        WHERE b.id=?
    """, (bid,)).fetchone()

    if not booking or booking["owner_id"] != session["user_id"]:
        flash("Unauthorized or invalid booking.")
        return redirect(url_for("owner_bookings"))

    # mark as rejected
    conn.execute("UPDATE bookings SET status='Rejected' WHERE id=?", (bid,))
    conn.commit()
    conn.close()

    flash("Booking rejected.")
    return redirect(url_for("owner_bookings"))

# -----------------------
# delete property
# -----------------------
@app.route("/owner/delete/<int:pid>")
def delete_property(pid):
    if session.get("role") != "owner":
        return redirect(url_for("login"))

    conn = get_db()

    prop = conn.execute("""
        SELECT * FROM properties WHERE id=? AND owner_id=?
    """, (pid, session["user_id"])).fetchone()

    if not prop:
        flash("Unauthorized.")
        return redirect(url_for("owner_dashboard"))

    conn.execute("DELETE FROM properties WHERE id=?", (pid,))
    conn.execute("DELETE FROM rent_payments WHERE property_id=?", (pid,))
    conn.execute("DELETE FROM complaints WHERE property_id=?", (pid,))
    conn.commit()
    conn.close()

    flash("Property deleted.")
    return redirect(url_for("owner_dashboard"))


# -----------------------
# ownser complaint display
# -----------------------
@app.route("/owner/complaints")
def owner_complaints():
    if session.get("role") != "owner":
        return redirect(url_for("login"))

    conn = get_db()
    complaints = conn.execute("""
        SELECT c.*, p.title AS property_title, u.name AS tenant_name
        FROM complaints c
        JOIN properties p ON c.property_id = p.id
        JOIN users u ON c.tenant_id = u.id
        WHERE p.owner_id = ?
        ORDER BY c.id DESC
    """, (session["user_id"],)).fetchall()
    conn.close()

    return render_template("owner_complaints.html", complaints=complaints)


# -----------------------
# owner payments display 
# -----------------------
@app.route("/owner/rent-payments")
def owner_rent_payments():
    if session.get("role") != "owner":
        return redirect(url_for("login"))

    conn = get_db()
    rents = conn.execute("""
        SELECT r.*, 
               p.title AS property_title,
               u.name AS tenant_name
        FROM rent_payments r
        JOIN properties p ON r.property_id = p.id
        JOIN users u ON r.tenant_id = u.id
        WHERE p.owner_id=?
        ORDER BY r.year DESC, r.month DESC
    """, (session["user_id"],)).fetchall()

    conn.close()
    return render_template("owner_rent_payments.html", rents=rents)

# -----------------------
#  Onwer Complaints update
# -----------------------
@app.route("/owner/complaint/update/<int:cid>", methods=["POST"])
def owner_update_complaint(cid):
    if session.get("role") != "owner":
        return redirect(url_for("login"))

    new_status = request.form.get("status")
    conn = get_db()

    valid = conn.execute("""
        SELECT c.* FROM complaints c
        JOIN properties p ON c.property_id=p.id
        WHERE c.id=? AND p.owner_id=?
    """, (cid, session["user_id"])).fetchone()

    if not valid:
        flash("Unauthorized.")
        return redirect(url_for("owner_dashboard"))

    conn.execute("""
        UPDATE complaints SET status=?, updated_at=?
        WHERE id=?
    """, (new_status, datetime.now().isoformat(), cid))

    conn.commit()
    conn.close()

    flash("Complaint updated.")
    return redirect(url_for("owner_dashboard"))



# -----------------------
# Tenant Dashboard (User)
# -----------------------
@app.route("/user/dashboard")
def user_dashboard():
    if session.get("role") != "user":
        return redirect(url_for("login"))

    conn = get_db()

    properties = conn.execute("""
        SELECT p.*, u.name AS owner_name
        FROM properties p
        LEFT JOIN users u ON p.owner_id = u.id
        WHERE p.id NOT IN (
            SELECT property_id FROM bookings WHERE status = 'Approved'
        )
    """).fetchall()

    rents = conn.execute("""
        SELECT r.*, p.title AS property_title, u.name AS owner_name
        FROM rent_payments r
        LEFT JOIN properties p ON r.property_id = p.id
        LEFT JOIN users u ON p.owner_id = u.id
        WHERE r.tenant_id=?
        ORDER BY r.year DESC, r.month DESC
    """, (session["user_id"],)).fetchall()

    conn.close()

    locations = sorted(list({p["location"] for p in properties}))

    return render_template("user_dashboard.html",
                           properties=properties,
                           rents=rents,
                           locations=locations)


# User: list agreements sent to them
@app.route("/user/agreements")
def user_agreements():
    if session.get("role") != "user":
        return redirect(url_for("login"))
    conn = get_db()
    agreements = conn.execute("""
        SELECT a.*, p.title AS property_title, u_o.name AS owner_name
        FROM agreements a
        JOIN properties p ON a.property_id = p.id
        LEFT JOIN users u_o ON a.owner_id = u_o.id
        WHERE a.tenant_id = ?
        ORDER BY a.id DESC
    """, (session["user_id"],)).fetchall()
    conn.close()
    return render_template("user_agreements.html", agreements=agreements)


# User: view single agreement and accept/reject
@app.route("/user/agreement/<int:aid>", methods=["GET", "POST"])
def user_view_agreement(aid):
    if session.get("role") != "user":
        return redirect(url_for("login"))

    conn = get_db()
    agreement = conn.execute("""
        SELECT a.*, p.title AS property_title, u_o.name AS owner_name
        FROM agreements a
        JOIN properties p ON a.property_id = p.id
        LEFT JOIN users u_o ON a.owner_id = u_o.id
        WHERE a.id = ? AND a.tenant_id = ?
    """, (aid, session["user_id"])).fetchone()

    if not agreement:
        conn.close()
        flash("Agreement not found.")
        return redirect(url_for("user_agreements"))

    if request.method == "POST":
        action = request.form.get("action")  
        if action == "accept":
        
            conn.execute("""
                UPDATE agreements SET status='Accepted', accepted_at=?, updated_at=?
                WHERE id=?
            """, (datetime.now().isoformat(), datetime.now().isoformat(), aid))

        
            conn.execute("""
                INSERT INTO rent_payments(property_id, tenant_id, month, year, amount, status, created_at)
                VALUES (?, ?, ?, ?, ?, 'Unpaid', ?)
            """, (
                agreement["property_id"],
                agreement["tenant_id"],
                datetime.now().strftime("%B"),
                datetime.now().year,
                agreement["monthly_rent"],
                datetime.now().isoformat()
            ))

        
            conn.execute("UPDATE bookings SET status='Pending' WHERE id=?", (agreement["booking_id"],))

            conn.commit()
            conn.close()

            flash("Agreement accepted. Rent created.")
            return redirect(url_for("user_dashboard"))

        else:
            
            conn.execute("UPDATE agreements SET status='Rejected', updated_at=? WHERE id=?", (datetime.now().isoformat(), aid))
        
            conn.execute("UPDATE bookings SET status='Rejected' WHERE id=?", (agreement["booking_id"],))
            conn.commit()
            conn.close()
            flash("Agreement rejected. Booking cancelled.")
            return redirect(url_for("user_agreements"))

    conn.close()
    return render_template("user_view_agreement.html", agreement=agreement)


# -----------------------
# User rents and payments dsiplay
# -----------------------
@app.route("/user/rents")
def user_rents():
    if session.get("role") != "user":
        return redirect(url_for("login"))

    conn = get_db()
    rents = conn.execute("""
        SELECT r.*, p.title AS property_title, u.name AS owner_name
        FROM rent_payments r
        LEFT JOIN properties p ON r.property_id = p.id
        LEFT JOIN users u ON p.owner_id = u.id
        WHERE r.tenant_id=?
        ORDER BY r.year DESC, r.month DESC
    """, (session["user_id"],)).fetchall()
    conn.close()

    return render_template("user_rents.html", rents=rents)


# -----------------------
# User booking property
# -----------------------
@app.route("/user/book/<int:pid>", methods=["POST"])
def book_property(pid):
    if session.get("role") != "user":
        return redirect(url_for("login"))

    conn = get_db()

    
    check = conn.execute("""
        SELECT * FROM bookings 
        WHERE property_id=? AND tenant_id=? AND status IN ('Pending','Approved')
    """, (pid, session["user_id"])).fetchone()

    if check:
        flash("You already requested this property.")
        return redirect(url_for("user_dashboard"))

    conn.execute("""
        INSERT INTO bookings(property_id, tenant_id, status, created_at)
        VALUES(?,?, 'Pending', ?)
    """, (pid, session["user_id"], datetime.now().isoformat()))

    conn.commit()
    conn.close()

    flash("Booking request sent to Owner!")
    return redirect(url_for("user_dashboard"))


# -----------------------
# Make complaint user side
# -----------------------
@app.route("/user/complaint/<int:pid>", methods=["GET", "POST"])
def raise_complaint(pid):
    if session.get("role") != "user":
        return redirect(url_for("login"))

    conn = get_db()


    is_tenant = conn.execute("""
        SELECT * FROM bookings
        WHERE property_id=? AND tenant_id=? AND status='Approved'
    """, (pid, session["user_id"])).fetchone()

    if not is_tenant:
        conn.close()
        flash("You are not a tenant of this property.")
        return redirect(url_for("user_dashboard"))

    if request.method == "POST":
        title = request.form.get("title")
        details = request.form.get("details")

        conn.execute("""
            INSERT INTO complaints(property_id, tenant_id, title, details, status, created_at)
            VALUES (?,?,?,?, 'Pending', ?)
        """, (pid, session["user_id"], title, details, datetime.now().isoformat()))

        conn.commit()
        conn.close()
        flash("Complaint submitted.")
        return redirect(url_for("user_dashboard"))

    prop = conn.execute("SELECT * FROM properties WHERE id=?", (pid,)).fetchone()
    conn.close()

    return render_template("raise_complaint.html", property=prop)

# -----------------------
# user complaints display 
# -----------------------
@app.route("/user/complaints")
def user_complaints():
    if session.get("role") != "user":
        return redirect(url_for("login"))

    conn = get_db()

    complaints = conn.execute("""
        SELECT c.*, p.title AS property_title
        FROM complaints c
        JOIN properties p ON c.property_id = p.id
        WHERE c.tenant_id=?
        ORDER BY c.id DESC
    """, (session["user_id"],)).fetchall()

    properties = conn.execute("""
        SELECT p.*
        FROM properties p
        JOIN bookings b ON p.id=b.property_id
        WHERE b.tenant_id=? AND b.status='Approved'
    """, (session["user_id"],)).fetchall()

    conn.close()

    return render_template("user_complaints.html",
                           complaints=complaints,
                           properties=properties)


# -----------------------
# user payrent
# -----------------------
@app.route("/user/pay-rent/<int:rid>", methods=["POST"])
def pay_rent(rid):
    if session.get("role") != "user":
        return redirect(url_for("login"))

    conn = get_db()
    rent = conn.execute(
        "SELECT * FROM rent_payments WHERE id=? AND tenant_id=?",
        (rid, session["user_id"])
    ).fetchone()

    if not rent:
        conn.close()
        flash("Rent record not found or unauthorized.")
        return redirect(url_for("user_dashboard"))

    conn.execute("""
        UPDATE rent_payments
        SET status='Paid', paid_at=?
        WHERE id=?
    """, (datetime.now().isoformat(), rid))

    conn.commit()
    conn.close()

    flash("Rent paid successfully!")
    return redirect(url_for("user_dashboard"))


# -----------------------
# Complaints
# -----------------------
@app.route("/complaint/update/<int:cid>", methods=["POST"])
def update_complaint(cid):
    role = session.get("role")
    if role not in ("owner", "admin"):
        return redirect(url_for("login"))

    new_status = request.form.get("status")  
    conn = get_db()


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
# Serve uploaded images 
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
# Admin Dashboard
# -----------------------
@app.route("/admin/dashboard")
def admin_dashboard():
    if session.get("role") != "admin":
        return redirect(url_for("login"))

    conn = get_db()

    # Fetch all data for dashboard analytics
    users = conn.execute("SELECT * FROM users").fetchall()
    owners = conn.execute("""
        SELECT * FROM users WHERE role='owner'
    """).fetchall()
    tenants = conn.execute("""
        SELECT * FROM users WHERE role='user'
    """).fetchall()

    properties = conn.execute("SELECT * FROM properties").fetchall()
    bookings = conn.execute("SELECT * FROM bookings").fetchall()
    complaints = conn.execute("SELECT * FROM complaints").fetchall()

    rents = conn.execute("""
        SELECT * FROM rent_payments
    """).fetchall()

    # Stats for dashboard
    total_revenue = conn.execute("""
        SELECT COALESCE(SUM(amount), 0)
        FROM rent_payments
        WHERE status='Paid'
    """).fetchone()[0]

    pending_complaints = conn.execute("""
        SELECT COUNT(*) FROM complaints WHERE status='Pending'
    """).fetchone()[0]

    conn.close()

    return render_template(
        "admin_dashboard.html",
        users=users,
        owners=owners,
        tenants=tenants,
        properties=properties,
        bookings=bookings,
        complaints=complaints,
        rents=rents,
        total_revenue=total_revenue,
        pending_complaints=pending_complaints
    )

@app.route("/admin/agreements")
def admin_agreements():
    if session.get("role") != "admin":
        return redirect(url_for("login"))
    conn = get_db()
    agreements = conn.execute("""
        SELECT a.*, p.title AS property_title, u_t.name AS tenant_name, u_o.name AS owner_name
        FROM agreements a
        LEFT JOIN properties p ON a.property_id = p.id
        LEFT JOIN users u_t ON a.tenant_id = u_t.id
        LEFT JOIN users u_o ON a.owner_id = u_o.id
        ORDER BY a.id DESC
    """).fetchall()
    conn.close()
    return render_template("admin_agreements.html", agreements=agreements)

@app.route("/admin/users")
def admin_users():
    if session.get("role") != "admin":
        return redirect(url_for("login"))

    conn = get_db()
    users = conn.execute("SELECT * FROM users").fetchall()
    conn.close()
    return render_template("admin_users.html", users=users)

@app.route("/admin/owners")
def admin_owners():
    if session.get("role") != "admin":
        return redirect(url_for("login"))

    conn = get_db()
    owners = conn.execute("SELECT * FROM users WHERE role='owner'").fetchall()
    conn.close()
    return render_template("admin_owners.html", owners=owners)

@app.route("/admin/properties")
def admin_properties():
    if session.get("role") != "admin":
        return redirect(url_for("login"))

    conn = get_db()
    properties = conn.execute("""
        SELECT p.*, u.name AS owner_name 
        FROM properties p 
        LEFT JOIN users u ON p.owner_id = u.id
    """).fetchall()
    conn.close()
    return render_template("admin_properties.html", properties=properties)

@app.route("/admin/complaints")
def admin_complaints():
    if session.get("role") != "admin":
        return redirect(url_for("login"))

    conn = get_db()
    complaints = conn.execute("""
        SELECT c.*, p.title AS property_title, u.name AS tenant_name
        FROM complaints c
        JOIN properties p ON c.property_id = p.id
        JOIN users u ON c.tenant_id = u.id
    """).fetchall()
    conn.close()
    return render_template("admin_complaints.html", complaints=complaints)

@app.route("/admin/payments")
def admin_payments():
    if session.get("role") != "admin":
        return redirect(url_for("login"))

    conn = get_db()
    payments = conn.execute("""
        SELECT r.*, p.title AS property_title, u.name AS tenant_name
        FROM rent_payments r
        JOIN properties p ON r.property_id = p.id
        JOIN users u ON r.tenant_id = u.id
    """).fetchall()
    conn.close()
    return render_template("admin_payments.html", rents=payments)

@app.route("/admin/bookings")
def admin_bookings():
    if session.get("role") != "admin":
        return redirect(url_for("login"))

    conn = get_db()
    bookings = conn.execute("""
        SELECT b.*, p.title AS property_title, u.name AS tenant_name
        FROM bookings b
        JOIN properties p ON b.property_id = p.id
        JOIN users u ON b.tenant_id = u.id
    """).fetchall()
    conn.close()
    return render_template("admin_bookings.html", bookings=bookings)




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

    cur.execute("""
CREATE TABLE IF NOT EXISTS agreements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    booking_id INTEGER,
    property_id INTEGER,
    owner_id INTEGER,
    tenant_id INTEGER,
    years INTEGER,
    advance_amount REAL,
    monthly_rent REAL,
    terms TEXT,
    pdf_path TEXT,
    status TEXT DEFAULT 'Pending',  
    created_at TEXT,
    updated_at TEXT,
    accepted_at TEXT
)
""")
    
    # bookings
    cur.execute("""
    CREATE TABLE bookings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        property_id INTEGER,
        tenant_id INTEGER,
        status TEXT,          -- Pending / Approved / Rejected
        created_at TEXT
    )
    """)
  
    conn.commit()
    conn.close()

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

if __name__ == "__main__":
    init_db()

    app.run(debug=True)
