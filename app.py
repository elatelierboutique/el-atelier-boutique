
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from werkzeug.utils import secure_filename
from functools import wraps
from pathlib import Path
import sqlite3, os, json, uuid

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "atelier.db"
UPLOAD_DIR = BASE_DIR / "static" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)
app.secret_key = os.environ.get("ATELIER_SECRET_KEY", "atelier-v3-cambiar-en-produccion")

ADMIN_USER = os.environ.get("ATELIER_ADMIN_USER", "admin")
ADMIN_PASSWORD = os.environ.get("ATELIER_ADMIN_PASSWORD", "Atelier2026!")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ref TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        subtitle TEXT DEFAULT '',
        description TEXT DEFAULT '',
        price INTEGER NOT NULL,
        category TEXT NOT NULL DEFAULT 'Ropa',
        sizes TEXT DEFAULT '[]',
        colors TEXT DEFAULT '[]',
        image TEXT DEFAULT '',
        active INTEGER DEFAULT 1,
        featured INTEGER DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS product_images (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL,
        image TEXT NOT NULL,
        color TEXT DEFAULT '',
        sort_order INTEGER DEFAULT 0,
        is_primary INTEGER DEFAULT 0,
        FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE CASCADE
    );
    """)
    # Seed gallery table from legacy main image when absent.
    products = conn.execute("SELECT id, image FROM products").fetchall()
    for p in products:
        c = conn.execute("SELECT COUNT(*) c FROM product_images WHERE product_id=?", (p["id"],)).fetchone()["c"]
        if c == 0 and p["image"]:
            conn.execute(
                "INSERT INTO product_images(product_id,image,color,sort_order,is_primary) VALUES(?,?,?,?,1)",
                (p["id"], p["image"], "", 0)
            )
    conn.commit()
    conn.close()

def product_to_dict(conn, row):
    imgs = conn.execute(
        "SELECT id,image,color,sort_order,is_primary FROM product_images WHERE product_id=? ORDER BY is_primary DESC, sort_order ASC, id ASC",
        (row["id"],)
    ).fetchall()
    gallery = [dict(x) for x in imgs]
    main = gallery[0]["image"] if gallery else row["image"]
    return {
        "id": row["id"], "ref": row["ref"], "name": row["name"], "subtitle": row["subtitle"],
        "description": row["description"], "price": row["price"], "category": row["category"],
        "sizes": json.loads(row["sizes"] or "[]"), "colors": json.loads(row["colors"] or "[]"),
        "image": main, "gallery": gallery,
        "active": bool(row["active"]), "featured": bool(row["featured"])
    }

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("admin"):
            return redirect(url_for("admin_login"))
        return fn(*args, **kwargs)
    return wrapper

@app.route("/")
def shop():
    return render_template("shop.html")

@app.route("/api/products")
def api_products():
    conn = get_db()
    rows = conn.execute("SELECT * FROM products WHERE active=1 ORDER BY featured DESC, id DESC").fetchall()
    data = [product_to_dict(conn, r) for r in rows]
    conn.close()
    return jsonify(data)

@app.route("/admin/login", methods=["GET","POST"])
def admin_login():
    if request.method == "POST":
        if request.form.get("username") == ADMIN_USER and request.form.get("password") == ADMIN_PASSWORD:
            session["admin"] = True
            return redirect(url_for("admin"))
        flash("Usuario o contraseña incorrectos.")
    return render_template("login.html")

@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))

@app.route("/admin")
@login_required
def admin():
    conn = get_db()
    rows = conn.execute("SELECT * FROM products ORDER BY id DESC").fetchall()
    data = [product_to_dict(conn, r) for r in rows]
    conn.close()
    return render_template("admin.html", products=data)

def save_uploaded_file(file):
    ext = Path(secure_filename(file.filename)).suffix.lower()
    if ext not in [".jpg",".jpeg",".png",".webp"]:
        raise ValueError("Formato de imagen no permitido.")
    filename = f"{uuid.uuid4().hex[:14]}{ext}"
    file.save(UPLOAD_DIR / filename)
    return f"uploads/{filename}"

def split_csv(value):
    return [x.strip() for x in (value or "").split(",") if x.strip()]

@app.route("/admin/product/new", methods=["POST"])
@login_required
def admin_new():
    return save_product(None)

@app.route("/admin/product/<int:pid>", methods=["POST"])
@login_required
def admin_update(pid):
    return save_product(pid)

def save_product(pid):
    form = request.form
    ref = form.get("ref","").strip()
    name = form.get("name","").strip()
    subtitle = form.get("subtitle","").strip()
    description = form.get("description","").strip()
    category = form.get("category","Ropa").strip() or "Ropa"
    price = int((form.get("price","0") or "0").replace(".","").replace(",",""))
    sizes = split_csv(form.get("sizes",""))
    colors = split_csv(form.get("colors",""))
    active = 1 if form.get("active") == "on" else 0
    featured = 1 if form.get("featured") == "on" else 0

    conn = get_db()
    try:
        if pid is None:
            cur = conn.execute("""INSERT INTO products
                (ref,name,subtitle,description,price,category,sizes,colors,image,active,featured)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (ref,name,subtitle,description,price,category,
                 json.dumps(sizes,ensure_ascii=False),json.dumps(colors,ensure_ascii=False),
                 "",active,featured))
            pid = cur.lastrowid
        else:
            conn.execute("""UPDATE products SET
                ref=?,name=?,subtitle=?,description=?,price=?,category=?,sizes=?,colors=?,active=?,featured=?
                WHERE id=?""",
                (ref,name,subtitle,description,price,category,
                 json.dumps(sizes,ensure_ascii=False),json.dumps(colors,ensure_ascii=False),
                 active,featured,pid))

        # Optional new cover image.
        cover = request.files.get("cover_image")
        if cover and cover.filename:
            image_path = save_uploaded_file(cover)
            conn.execute("UPDATE product_images SET is_primary=0 WHERE product_id=?", (pid,))
            conn.execute(
                "INSERT INTO product_images(product_id,image,color,sort_order,is_primary) VALUES(?,?,?,?,1)",
                (pid, image_path, form.get("cover_color","").strip(), -1)
            )
            conn.execute("UPDATE products SET image=? WHERE id=?", (image_path, pid))

        # Additional gallery images, with colors mapped in upload order.
        gallery_files = [f for f in request.files.getlist("gallery_images") if f and f.filename]
        gallery_colors = split_csv(form.get("gallery_colors",""))
        max_sort = conn.execute(
            "SELECT COALESCE(MAX(sort_order),0) m FROM product_images WHERE product_id=?",
            (pid,)
        ).fetchone()["m"]
        for idx, f in enumerate(gallery_files):
            image_path = save_uploaded_file(f)
            color = gallery_colors[idx] if idx < len(gallery_colors) else ""
            conn.execute(
                "INSERT INTO product_images(product_id,image,color,sort_order,is_primary) VALUES(?,?,?,?,0)",
                (pid, image_path, color, max_sort + idx + 1)
            )

        # Remove selected existing gallery images.
        remove_ids = request.form.getlist("remove_image")
        for rid in remove_ids:
            try:
                rid_int = int(rid)
            except:
                continue
            row = conn.execute("SELECT image,is_primary FROM product_images WHERE id=? AND product_id=?", (rid_int,pid)).fetchone()
            if row:
                conn.execute("DELETE FROM product_images WHERE id=?", (rid_int,))

        # Ensure there is one primary image.
        imgs = conn.execute(
            "SELECT id,image,is_primary FROM product_images WHERE product_id=? ORDER BY is_primary DESC, sort_order ASC, id ASC",
            (pid,)
        ).fetchall()
        if imgs:
            if not any(x["is_primary"] for x in imgs):
                conn.execute("UPDATE product_images SET is_primary=1 WHERE id=?", (imgs[0]["id"],))
            first = conn.execute(
                "SELECT image FROM product_images WHERE product_id=? ORDER BY is_primary DESC, sort_order ASC, id ASC LIMIT 1",
                (pid,)
            ).fetchone()
            conn.execute("UPDATE products SET image=? WHERE id=?", (first["image"],pid))
        else:
            conn.execute("UPDATE products SET image='' WHERE id=?", (pid,))

        conn.commit()
        flash("Producto guardado correctamente.")
    except Exception as e:
        conn.rollback()
        flash(f"No se pudo guardar: {e}")
    finally:
        conn.close()
    return redirect(url_for("admin"))

@app.route("/admin/product/<int:pid>/delete", methods=["POST"])
@login_required
def admin_delete(pid):
    conn = get_db()
    conn.execute("DELETE FROM product_images WHERE product_id=?", (pid,))
    conn.execute("DELETE FROM products WHERE id=?", (pid,))
    conn.commit()
    conn.close()
    flash("Producto eliminado.")
    return redirect(url_for("admin"))

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
