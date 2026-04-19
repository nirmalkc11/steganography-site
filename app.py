import sqlite3
import time
from pathlib import Path

from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

from stego import embed_message, extract_message

app = Flask(__name__)
app.secret_key = "change_this_secret_key_12345"

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_FOLDER = BASE_DIR / "uploads"
MESSAGE_FOLDER = BASE_DIR / "hidden_messages"
GENERATED_FOLDER = BASE_DIR / "generated"
DB_PATH = BASE_DIR / "users.db"

ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "bmp", "webp"}
ALLOWED_ALL_EXTENSIONS = {
    "png", "jpg", "jpeg", "gif", "bmp", "webp",
    "txt", "pdf", "mp3", "mp4", "wav", "doc", "docx"
}

for folder in [UPLOAD_FOLDER, MESSAGE_FOLDER, GENERATED_FOLDER]:
    folder.mkdir(exist_ok=True)


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_ALL_EXTENSIONS


def is_image_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            original_filename TEXT NOT NULL,
            message_filename TEXT NOT NULL,
            generated_filename TEXT NOT NULL,
            s_value INTEGER NOT NULL,
            l_value INTEGER NOT NULL,
            c_value TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()


@app.route("/")
def home():
    return redirect(url_for("gallery"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            flash("Username and password are required.")
            return redirect(url_for("register"))

        password_hash = generate_password_hash(password)

        conn = get_db()
        try:
            conn.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (username, password_hash)
            )
            conn.commit()
            flash("Registration successful. Please log in.")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Username already exists.")
            return redirect(url_for("register"))
        finally:
            conn.close()

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE username = ?",
            (username,)
        ).fetchone()
        conn.close()

        if user and check_password_hash(user["password_hash"], password):
            session["username"] = username
            flash("Logged in successfully.")
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid username or password.")
            return redirect(url_for("login"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully.")
    return redirect(url_for("gallery"))


@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    if "username" not in session:
        flash("Please log in first.")
        return redirect(url_for("login"))

    if request.method == "POST":
        carrier_file = request.files.get("carrier_file")
        message_file = request.files.get("message_file")
        typed_message = request.form.get("typed_message", "").strip()

        s_value = request.form.get("s_value", "").strip()
        l_value = request.form.get("l_value", "").strip()
        c_value = request.form.get("c_value", "").strip()

        if not carrier_file or carrier_file.filename == "":
            flash("Please upload a carrier file.")
            return redirect(url_for("dashboard"))

        has_uploaded_message = message_file and message_file.filename != ""
        has_typed_message = typed_message != ""

        if not has_uploaded_message and not has_typed_message:
            flash("Please either upload a secret message file or type a secret message.")
            return redirect(url_for("dashboard"))

        if has_uploaded_message and has_typed_message:
            flash("Please use only one message input: either upload a file or type a message.")
            return redirect(url_for("dashboard"))

        if not s_value or not l_value or not c_value:
            flash("Please provide S, L, and C values.")
            return redirect(url_for("dashboard"))

        try:
            s_value = int(s_value)
            l_value = int(l_value)
        except ValueError:
            flash("S and L must be integers.")
            return redirect(url_for("dashboard"))

        if c_value not in ["fixed", "alternate", "cycle3"]:
            flash("Mode C must be fixed, alternate, or cycle3.")
            return redirect(url_for("dashboard"))

        if not allowed_file(carrier_file.filename):
            flash("Carrier file type not allowed.")
            return redirect(url_for("dashboard"))

        carrier_name = secure_filename(carrier_file.filename)
        unique_prefix = str(int(time.time()))

        saved_carrier_name = f"{unique_prefix}_{carrier_name}"
        generated_name = f"stego_{unique_prefix}_{carrier_name}"

        carrier_path = UPLOAD_FOLDER / saved_carrier_name
        generated_path = GENERATED_FOLDER / generated_name

        carrier_file.save(carrier_path)

        if has_uploaded_message:
            if not allowed_file(message_file.filename):
                flash("Message file type not allowed.")
                return redirect(url_for("dashboard"))

            message_name = secure_filename(message_file.filename)
            saved_message_name = f"{unique_prefix}_{message_name}"
            message_path = MESSAGE_FOLDER / saved_message_name
            message_file.save(message_path)

        else:
            saved_message_name = f"{unique_prefix}_typed_message.txt"
            message_path = MESSAGE_FOLDER / saved_message_name
            message_path.write_text(typed_message, encoding="utf-8")

        try:
            embed_message(
                carrier_path=str(carrier_path),
                message_path=str(message_path),
                output_path=str(generated_path),
                S=s_value,
                L=l_value,
                mode=c_value
            )
        except Exception as e:
            flash(f"Embedding failed: {e}")
            return redirect(url_for("dashboard"))

        conn = get_db()
        conn.execute("""
            INSERT INTO posts (
                username,
                original_filename,
                message_filename,
                generated_filename,
                s_value,
                l_value,
                c_value
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            session["username"],
            saved_carrier_name,
            saved_message_name,
            generated_name,
            s_value,
            l_value,
            c_value
        ))
        conn.commit()
        conn.close()

        flash("File embedded and posted successfully.")
        return redirect(url_for("gallery"))

    return render_template("dashboard.html", username=session["username"])


@app.route("/gallery")
def gallery():
    conn = get_db()
    posts = conn.execute("""
        SELECT * FROM posts
        ORDER BY id DESC
    """).fetchall()
    conn.close()

    return render_template("gallery.html", posts=posts, is_image_file=is_image_file)


@app.route("/generated/<path:filename>")
def generated_file(filename):
    return send_from_directory(GENERATED_FOLDER, filename)

@app.route("/download/<path:filename>")
def download_file(filename):
    return send_from_directory(
        GENERATED_FOLDER,
        filename,
        as_attachment=True
    )

@app.route("/post/<int:post_id>")
def view_post(post_id):
    conn = get_db()
    post = conn.execute(
        "SELECT * FROM posts WHERE id = ?",
        (post_id,)
    ).fetchone()
    conn.close()

    if not post:
        flash("Post not found.")
        return redirect(url_for("gallery"))

    return render_template(
        "view_post.html",
        post=post,
        is_image_file=is_image_file
    )

@app.route("/extract", methods=["GET", "POST"])
def extract_view():
    if "username" not in session:
        flash("Please log in first.")
        return redirect(url_for("login"))

    extracted_file = None

    if request.method == "POST":
        stego_file = request.files.get("stego_file")
        s_value = request.form.get("s_value", "").strip()
        l_value = request.form.get("l_value", "").strip()
        c_value = request.form.get("c_value", "").strip()

        if not stego_file or stego_file.filename == "":
            flash("Please upload a stego file.")
            return redirect(url_for("extract_view"))

        if not s_value or not l_value or not c_value:
            flash("Please provide S, L, and C values.")
            return redirect(url_for("extract_view"))

        try:
            s_value = int(s_value)
            l_value = int(l_value)
        except ValueError:
            flash("S and L must be integers.")
            return redirect(url_for("extract_view"))

        if c_value not in ["fixed", "alternate", "cycle3"]:
            flash("Mode C must be fixed, alternate, or cycle3.")
            return redirect(url_for("extract_view"))

        stego_name = secure_filename(stego_file.filename)
        unique_prefix = str(int(time.time()))
        saved_stego_name = f"{unique_prefix}_{stego_name}"
        saved_stego_path = GENERATED_FOLDER / saved_stego_name

        stego_file.save(saved_stego_path)

        try:
            recovered_base = str(GENERATED_FOLDER / f"recovered_{unique_prefix}")
            extracted_path = extract_message(
                stego_path=str(saved_stego_path),
                output_base_path=recovered_base,
                S=s_value,
                L=l_value,
                mode=c_value
            )
            extracted_file = Path(extracted_path).name
            flash("Message extracted successfully.")
        except Exception as e:
            flash(f"Extraction failed: {e}")
            return redirect(url_for("extract_view"))

    return render_template("extract.html", extracted_file=extracted_file)

with app.app_context():
    init_db()

if __name__ == "__main__":
    app.run(debug=True)