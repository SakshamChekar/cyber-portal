from flask import Flask, render_template, request, redirect, url_for, session, flash
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash
from config import db_config
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)

# ✅ Better secret key
app.secret_key = "cyber_portal_secret_2026"

# ✅ Upload config
UPLOAD_FOLDER = os.path.join('static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf', 'docx'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


# ---------------------- Helper Functions ----------------------
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_db_connection():
    return mysql.connector.connect(**db_config)


# ---------------------- Routes ----------------------

@app.route('/')
def index():
    return render_template('index.html')


# ---------- Register ----------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']

        hashed_password = generate_password_hash(password)

        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                "INSERT INTO users (name, email, password, role) VALUES (%s, %s, %s, %s)",
                (name, email, hashed_password, 'user')
            )
            conn.commit()
            flash("Registration successful! Please login.")
            return redirect(url_for("login"))

        except mysql.connector.Error as err:
            flash(f"Error: {err}")
            return redirect(url_for("register"))

        finally:
            cursor.close()
            conn.close()

    return render_template('register.html')


# ---------- Login ----------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()

        cursor.close()
        conn.close()

        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['role'] = user['role']
            session['name'] = user['name']
            flash("Login successful!")
            return redirect(url_for("index"))
        else:
            flash("Invalid credentials.")
            return redirect(url_for("login"))

    return render_template('login.html')


# ---------- Logout ----------
@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully.")
    return redirect(url_for("index"))


# ---------- Awareness ----------
@app.route('/awareness')
def awareness():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # ✅ FIXED TABLE NAME
    cursor.execute("SELECT * FROM awareness_posts ORDER BY date_posted DESC")
    posts = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('awareness.html', awareness_posts=posts)


# ---------- Add Awareness ----------
@app.route('/add_awareness', methods=['GET', 'POST'])
def add_awareness():
    if 'user_id' not in session or session.get('role') != 'admin':
        flash("Only admins can add awareness posts.")
        return redirect(url_for('awareness'))

    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        category = request.form['category']

        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO awareness_posts (title, content, category, date_posted)
                VALUES (%s, %s, %s, NOW())
            """, (title, content, category))

            conn.commit()
            flash("Awareness post added successfully!")
            return redirect(url_for('awareness'))

        finally:
            cursor.close()
            conn.close()

    return render_template('add_awareness.html')


# ---------- Report ----------
@app.route('/report', methods=['GET', 'POST'])
def report():
    if 'user_id' not in session:
        flash("Please login first.")
        return redirect(url_for('login'))

    if request.method == 'POST':
        category = request.form['category']
        description = request.form['description']
        file = request.files.get('attachment')
        filename = None

        # ✅ Better file handling
        if file:
            if allowed_file(file.filename):
                if not os.path.exists(app.config['UPLOAD_FOLDER']):
                    os.makedirs(app.config['UPLOAD_FOLDER'])

                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            else:
                flash("Invalid file type.")
                return redirect(url_for('report'))

        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO reports (user_id, category, description, attachment)
                VALUES (%s, %s, %s, %s)
            """, (session['user_id'], category, description, filename))

            conn.commit()
            flash("Report submitted successfully!")

        except Exception as e:
            flash(f"Error: {e}")

        finally:
            cursor.close()
            conn.close()

        return redirect(url_for('report'))

    return render_template('report.html')


# ---------- Contact ----------
@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        flash("Thank you! We will contact you soon.")
        return redirect(url_for('contact'))

    return render_template('contact.html')


# ---------- Admin Reports ----------
@app.route('/admin/reports')
def admin_reports():
    if 'user_id' not in session or session.get('role') != 'admin':
        flash("Access denied.")
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT r.report_id, r.category, r.description, r.attachment, 
               r.date_reported, r.status, u.name, u.email
        FROM reports r
        JOIN users u ON r.user_id = u.id
        ORDER BY r.date_reported DESC
    """)

    reports = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('admin_reports.html', reports=reports)


# ---------- Update Status ----------
@app.route('/admin/update_status/<int:report_id>', methods=['POST'])
def update_status(report_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        flash("Access denied.")
        return redirect(url_for('login'))

    new_status = request.form.get('status', '').strip()

    # ✅ FIXED STATUS MATCH
    allowed = {'Pending', 'Reviewed', 'Resolved'}

    if new_status not in allowed:
        flash("Invalid status.")
        return redirect(url_for('admin_reports'))

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "UPDATE reports SET status=%s WHERE report_id=%s",
            (new_status, report_id)
        )
        conn.commit()
        flash("Status updated.")

    except Exception as e:
        conn.rollback()
        flash(f"Error: {e}")

    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('admin_reports'))


# ---------- Delete Report ----------
@app.route('/delete_report/<int:report_id>', methods=['POST', 'GET'])
def delete_report(report_id):
    if 'user_id' not in session:
        flash("Login required.")
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        if session.get('role') == 'admin':
            cursor.execute("DELETE FROM reports WHERE report_id = %s", (report_id,))
        else:
            cursor.execute(
                "DELETE FROM reports WHERE report_id = %s AND user_id = %s",
                (report_id, session['user_id'])
            )

        conn.commit()

        if cursor.rowcount:
            flash("Deleted successfully.")
        else:
            flash("Not allowed.")

    except Exception as e:
        flash(f"Error: {e}")

    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('admin_reports' if session.get('role') == 'admin' else 'my_reports'))


# ---------- My Reports ----------
@app.route('/my_reports')
def my_reports():
    if 'user_id' not in session:
        flash("Please login.")
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if session.get('role') == 'admin':
        cursor.execute("""
            SELECT r.report_id, r.category, r.description, r.attachment, 
                   r.date_reported, r.status, u.name
            FROM reports r
            JOIN users u ON r.user_id = u.id
            ORDER BY r.date_reported DESC
        """)
    else:
        cursor.execute("""
            SELECT report_id, category, description, attachment, date_reported, status
            FROM reports
            WHERE user_id = %s
            ORDER BY date_reported DESC
        """, (session['user_id'],))

    reports = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('my_reports.html', reports=reports)


# ---------------------- Run ----------------------
if __name__ == '__main__':
    app.run(debug=True)