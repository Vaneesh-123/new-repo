from flask import Flask, render_template, request, redirect, url_for, session, flash, make_response
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import secrets
from captcha.image import ImageCaptcha
import sqlite3
from flask_mail import Mail, Message
from datetime import datetime, timedelta
import io
import os
import sqlite3


app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

# ---------- EMAIL CONFIG ----------
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'vaneeshbandari@gmail.com'
app.config['MAIL_PASSWORD'] = 'gwub xggk yabr vwnj'
app.config['MAIL_DEFAULT_SENDER'] = 'vaneeshbandari@gmail.com'

mail = Mail(app)

# ---------- DATABASE (SQLite) ----------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database.db")



def get_db():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row   # ✅ VERY IMPORTANT
    return conn

# ---------- CAPTCHA ----------
image = ImageCaptcha(width=280, height=90)

# ---------- LOGIN REQUIRED ----------
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to access this page', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ---------- CONTACT ----------
@app.route("/contact")
def contact():
    return render_template("contact.html")

# ---------- FORGOT PASSWORD ----------
@app.route('/forgot', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')

        conn = get_db()
        cur = conn.cursor()

        cur.execute("SELECT id FROM users WHERE email=?", (email,))
        user = cur.fetchone()

        if not user:
            flash("Email not registered", "danger")
            return redirect(url_for('forgot_password'))

        token = secrets.token_urlsafe(32)
        expiry = datetime.now() + timedelta(minutes=30)

        cur.execute(
            "UPDATE users SET reset_token=?, reset_token_expiry=? WHERE email=?",
            (token, expiry, email)
        )
        conn.commit()
        conn.close()

        reset_link = url_for('reset_password', token=token, _external=True)

        msg = Message(
            "Password Reset Request",
            recipients=[email],
            body=f"Click the link to reset your password:\n{reset_link}\n\nLink valid for 30 minutes."
        )
        mail.send(msg)

        flash("Password reset link sent to your email", "info")
        return redirect(url_for('login'))

    return render_template('forgot_password.html')

# ---------- RESET PASSWORD ----------
@app.route('/reset/<token>', methods=['GET', 'POST'])
def reset_password(token):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT id, reset_token_expiry FROM users WHERE reset_token=?",
        (token,)
    )
    user = cur.fetchone()

    if not user or datetime.fromisoformat(user['reset_token_expiry']) < datetime.now():
        conn.close()
        flash("Reset link expired or invalid", "danger")
        return redirect(url_for('login'))

    if request.method == 'POST':
        new_password = request.form['password']
        hashed = generate_password_hash(new_password)

        cur.execute(
            "UPDATE users SET password=?, reset_token=NULL, reset_token_expiry=NULL WHERE id=?",
            (hashed, user['id'])
        )
        conn.commit()
        conn.close()

        flash("Password reset successful", "success")
        return redirect(url_for('login'))

    conn.close()
    return render_template('reset_password.html')

# ---------- CAPTCHA ----------
@app.route('/captcha')
def captcha():
    captcha_text = ''.join(secrets.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789') for _ in range(6))
    session['captcha'] = captcha_text

    data = image.generate(captcha_text)
    response = make_response(data.getvalue())
    response.headers['Content-Type'] = 'image/png'
    return response

# ---------- ABOUT ----------
@app.route('/about')
def about():
    return render_template('about.html')

# ---------- DASHBOARD ----------
@app.route('/')
@app.route('/view_all')
@login_required
def view_all():
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT * FROM notes WHERE user_id=? ORDER BY created_at DESC",
        (session['user_id'],)
    )
    notes = cur.fetchall()
    conn.close()

    return render_template('view_all.html', notes=notes, username=session.get('username'))

# ---------- REGISTER ----------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm = request.form['confirm_password']
        captcha_input = request.form['captcha']

        if captcha_input.upper() != session.get('captcha', ''):
            flash('Invalid CAPTCHA', 'danger')
            return redirect(url_for('register'))

        if password != confirm:
            flash('Passwords do not match', 'danger')
            return redirect(url_for('register'))

        conn = get_db()
        cur = conn.cursor()

        cur.execute(
            "SELECT id FROM users WHERE username=? OR email=?",
            (username, email)
        )
        if cur.fetchone():
            flash('User already exists', 'danger')
            conn.close()
            return redirect(url_for('register'))

        hashed = generate_password_hash(password)

        cur.execute(
            "INSERT INTO users (username, email, password) VALUES (?,?,?)",
            (username, email, hashed)
        )
        conn.commit()
        conn.close()

        flash('Registration successful', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')

# ---------- LOGIN ----------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        captcha_input = request.form['captcha']

        if captcha_input.upper() != session.get('captcha', ''):
            flash('Invalid CAPTCHA', 'danger')
            return redirect(url_for('login'))

        conn = get_db()
        cur = conn.cursor()

        cur.execute("SELECT * FROM users WHERE username=?", (username,))
        user = cur.fetchone()
        conn.close()

        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['email'] = user['email']
            return redirect(url_for('view_all'))

        flash('Invalid login credentials', 'danger')

    return render_template('login.html')

# ---------- LOGOUT ----------
@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully', 'info')
    return redirect(url_for('login'))

# ---------- ADD NOTE ----------
@app.route('/add_note', methods=['GET', 'POST'])
@login_required
def add_note():
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        category = request.form.get('category', 'General')

        conn = get_db()
        cur = conn.cursor()

        cur.execute(
            "INSERT INTO notes (user_id, title, content, category) VALUES (?,?,?,?)",
            (session['user_id'], title, content, category)
        )
        conn.commit()
        conn.close()

        return redirect(url_for('view_all'))

    return render_template('add_note.html')

# ---------- DELETE NOTE ----------
@app.route('/delete_note/<int:note_id>')
@login_required
def delete_note(note_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "DELETE FROM notes WHERE id=? AND user_id=?",
        (note_id, session['user_id'])
    )
    conn.commit()
    conn.close()

    return redirect(url_for('view_all'))

# ---------- PROFILE ----------
@app.route('/profile')
@login_required
def profile():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM users WHERE id=?", (session['user_id'],))
    user = cur.fetchone()

    cur.execute("SELECT COUNT(*) FROM notes WHERE user_id=?", (session['user_id'],))
    note_count = cur.fetchone()[0]

    conn.close()

    return render_template(
        'profile.html',
        user=user,
        note_count=note_count
    )



# ---------- SEARCH ----------
@app.route("/search")
@login_required
def search():
    query = request.args.get("q", "").strip()

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT * FROM notes
        WHERE user_id=?
        AND (title LIKE ? OR content LIKE ?)
        ORDER BY created_at DESC
        """,
        (session["user_id"], f"%{query}%", f"%{query}%")
    )

    notes = cur.fetchall()
    conn.close()

    return render_template(
        "view_all.html",
        notes=notes,
        username=session.get("username"),
        search_query=query
    )

# ---------- VIEW NOTE ----------
@app.route("/note/<int:note_id>")
@login_required
def view_note(note_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT * FROM notes WHERE id=? AND user_id=?",
        (note_id, session["user_id"])
    )
    note = cur.fetchone()
    conn.close()

    if not note:
        return redirect("/view_all")

    return render_template("view_note.html", note=note)

# ---------- EDIT NOTE ----------
@app.route("/note/edit/<int:note_id>", methods=["GET", "POST"])
@login_required
def edit_note(note_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT * FROM notes WHERE id=? AND user_id=?",
        (note_id, session["user_id"])
    )
    note = cur.fetchone()

    if not note:
        conn.close()
        return redirect("/view_all")

    if request.method == "POST":
        title = request.form["title"]
        content = request.form["content"]

        cur.execute(
            "UPDATE notes SET title=?, content=? WHERE id=? AND user_id=?",
            (title, content, note_id, session["user_id"])
        )
        conn.commit()
        conn.close()
        return redirect(url_for("view_note", note_id=note_id))

    conn.close()
    return render_template("edit_note.html", note=note)

# ---------- RUN ----------
if __name__ == '__main__':
    app.run(debug=True)