import os
import sqlite3
from flask import Flask, render_template_string, request, jsonify, redirect, session, url_for
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")

DATABASE_URL = os.environ.get("DATABASE_URL", "")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
DATABASE_URL = DATABASE_URL or None
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "petition.db")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "colledge2026")


# --- Database helpers (PostgreSQL on Render, SQLite locally) ---

def get_db():
    if DATABASE_URL:
        import psycopg2
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    else:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn


def db_fetchall(conn, query):
    if DATABASE_URL:
        import psycopg2.extras
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(query)
        rows = cur.fetchall()
        return [dict(r) for r in rows]
    else:
        cur = conn.cursor()
        cur.execute(query)
        rows = cur.fetchall()
        return [dict(r) for r in rows]


def db_execute(conn, query, params):
    cur = conn.cursor()
    cur.execute(query, params)
    conn.commit()


def init_db():
    conn = get_db()
    cur = conn.cursor()
    if DATABASE_URL:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS signatures (
                id SERIAL PRIMARY KEY,
                printed_name TEXT NOT NULL,
                address TEXT NOT NULL,
                signature_data TEXT NOT NULL,
                signed_at TIMESTAMP DEFAULT NOW()
            )
        """)
    else:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS signatures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                printed_name TEXT NOT NULL,
                address TEXT NOT NULL,
                signature_data TEXT NOT NULL,
                signed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    conn.commit()
    cur.close()
    conn.close()


# --- Auth decorator for admin ---

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin"):
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return decorated


# --- Templates ---

PETITION_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Colledge Farms HOA Petition</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }

        body {
            font-family: Georgia, 'Times New Roman', serif;
            background: #f5f5f0;
            color: #2c2c2c;
            line-height: 1.6;
        }

        .container {
            max-width: 800px;
            margin: 0 auto;
            background: #fff;
            min-height: 100vh;
            box-shadow: 0 0 30px rgba(0,0,0,0.1);
        }

        .header {
            text-align: center;
            padding: 40px 40px 0;
        }

        .header h1 {
            font-size: 28px;
            font-weight: bold;
            color: #1a1a2e;
            margin-bottom: 6px;
        }

        .header .subtitle {
            font-size: 15px;
            color: #555;
            letter-spacing: 0.5px;
        }

        .divider {
            border: none;
            border-top: 3px solid #2d3748;
            margin: 20px 40px;
        }

        .content {
            padding: 0 40px 30px;
        }

        .intro {
            font-size: 14.5px;
            margin-bottom: 20px;
            text-align: justify;
        }

        .item {
            margin-bottom: 18px;
        }

        .item h3 {
            font-size: 15px;
            font-weight: bold;
            color: #1a1a2e;
            margin-bottom: 6px;
        }

        .item p {
            font-size: 14.5px;
            margin-left: 16px;
            text-align: justify;
        }

        .item p strong {
            font-weight: bold;
        }

        .confirm-text {
            font-size: 14.5px;
            margin: 20px 0 8px;
            text-align: justify;
        }

        .instruction {
            font-style: italic;
            text-align: center;
            font-size: 14px;
            color: #555;
            margin-bottom: 24px;
        }

        .sig-count {
            background: #2d3748;
            color: #fff;
            text-align: center;
            padding: 12px;
            font-size: 16px;
            font-family: Arial, sans-serif;
        }

        .sig-count span {
            font-weight: bold;
            font-size: 20px;
        }

        .sign-form {
            background: #f8f9fa;
            border: 2px solid #2d3748;
            border-radius: 8px;
            margin: 24px 40px;
            padding: 28px;
        }

        .sign-form h2 {
            text-align: center;
            font-size: 20px;
            color: #2d3748;
            margin-bottom: 20px;
            font-family: Arial, sans-serif;
        }

        .form-group {
            margin-bottom: 16px;
        }

        .form-group label {
            display: block;
            font-weight: bold;
            font-size: 14px;
            margin-bottom: 5px;
            color: #2d3748;
            font-family: Arial, sans-serif;
        }

        .form-group input {
            width: 100%;
            padding: 10px 14px;
            border: 1px solid #ccc;
            border-radius: 5px;
            font-size: 16px;
            font-family: Georgia, serif;
        }

        .form-group input:focus {
            outline: none;
            border-color: #2d3748;
            box-shadow: 0 0 0 2px rgba(45,55,72,0.15);
        }

        .signature-area label {
            display: block;
            font-weight: bold;
            font-size: 14px;
            margin-bottom: 5px;
            color: #2d3748;
            font-family: Arial, sans-serif;
        }

        .signature-pad-wrapper {
            border: 1px solid #ccc;
            border-radius: 5px;
            background: #fff;
            position: relative;
        }

        #signatureCanvas {
            width: 100%;
            height: 150px;
            cursor: crosshair;
            display: block;
            border-radius: 5px;
        }

        .sig-actions {
            display: flex;
            justify-content: flex-end;
            padding: 4px 8px;
            background: #f0f0f0;
            border-radius: 0 0 5px 5px;
        }

        .sig-actions button {
            background: none;
            border: none;
            color: #888;
            cursor: pointer;
            font-size: 13px;
            font-family: Arial, sans-serif;
        }

        .sig-actions button:hover { color: #c00; }

        .submit-btn {
            display: block;
            width: 100%;
            padding: 14px;
            background: #2d3748;
            color: #fff;
            border: none;
            border-radius: 5px;
            font-size: 17px;
            font-weight: bold;
            cursor: pointer;
            margin-top: 20px;
            font-family: Arial, sans-serif;
            transition: background 0.2s;
        }

        .submit-btn:hover { background: #1a202c; }
        .submit-btn:disabled { background: #999; cursor: not-allowed; }

        .toast {
            position: fixed;
            top: 20px;
            right: 20px;
            background: #38a169;
            color: #fff;
            padding: 14px 24px;
            border-radius: 6px;
            font-family: Arial, sans-serif;
            font-size: 15px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.2);
            transform: translateX(120%);
            transition: transform 0.3s;
            z-index: 1000;
        }

        .toast.show { transform: translateX(0); }
        .toast.error { background: #c53030; }

        .success-message {
            background: #f0fff4;
            border: 2px solid #38a169;
            border-radius: 8px;
            margin: 24px 40px;
            padding: 28px;
            text-align: center;
        }

        .success-message h2 {
            color: #38a169;
            font-family: Arial, sans-serif;
            margin-bottom: 8px;
        }

        .success-message p {
            color: #555;
            font-size: 15px;
        }

        @media (max-width: 600px) {
            .header { padding: 24px 20px 0; }
            .header h1 { font-size: 22px; }
            .divider { margin: 16px 20px; }
            .content { padding: 0 20px 20px; }
            .sign-form { margin: 20px; padding: 20px; }
            .success-message { margin: 20px; padding: 20px; }
        }
    </style>
</head>
<body>

<div class="container">
    <div class="header">
        <h1>Colledge Farms HOA Petition</h1>
        <p class="subtitle">New Lot Annexation &amp; Community Amenity Fund</p>
    </div>

    <hr class="divider">

    <div class="content">
        <p class="intro">
            As homeowners in our community, we're asking you to review and vote on the two items below. By signing this
            petition, you're confirming that you live in the Colledge Farms HOA and that you support both measures.
        </p>

        <div class="item">
            <h3>Item 1 &mdash; Bring the 8 New Lots into Our HOA</h3>
            <p>
                Symphony is currently developing 8 lots north of River Park Way along 1500 N next to our neighborhood. This vote is to officially bring those 8
                lots into our HOA boundary. Once annexed, the new homeowners on those lots would follow the same rules,
                covenants, and dues as everyone else in the HOA.
            </p>
        </div>

        <div class="item">
            <h3>Item 2 &mdash; Support a 9th Lot in Exchange for a $65,000 Community Amenity Fund</h3>
            <p>
                We've negotiated a deal with Symphony: if we help them get city approval to develop a 9th lot (carved out of the
                existing 8-lot area, and sized to match the rest of our homes), Symphony will contribute <strong>$65,000 to our HOA
                fund</strong>. That money would go toward a new amenity on our HOA property &mdash; with the Colledge Farms HOA members deciding
                together what that amenity will be at a future date.
            </p>
        </div>

        <p class="confirm-text">
            By signing below, you confirm you are a homeowner in the Colledge Farms HOA and that you've read and support both items above.
        </p>

        <p class="instruction">Please fill out all fields and sign.</p>
    </div>

    <div class="sig-count">
        <span id="totalCount">{{ total }}</span> homeowner{{ 's' if total != 1 else '' }} ha{{ 's' if total == 1 else 've' }} signed this petition
    </div>

    {% if just_signed %}
    <div class="success-message">
        <h2>Thank you for signing!</h2>
        <p>Your signature has been recorded. Share this page with your neighbors so they can sign too.</p>
    </div>
    {% else %}
    <div class="sign-form">
        <h2>Sign the Petition</h2>
        <form id="petitionForm" onsubmit="return submitForm(event)">
            <div class="form-group">
                <label for="printedName">PRINTED NAME</label>
                <input type="text" id="printedName" name="printed_name" required placeholder="Your full name">
            </div>
            <div class="form-group">
                <label for="address">ADDRESS</label>
                <input type="text" id="address" name="address" required placeholder="Your home address">
            </div>
            <div class="signature-area">
                <label>SIGNATURE</label>
                <div class="signature-pad-wrapper">
                    <canvas id="signatureCanvas"></canvas>
                    <div class="sig-actions">
                        <button type="button" onclick="clearSignature()">Clear signature</button>
                    </div>
                </div>
            </div>
            <button type="submit" class="submit-btn" id="submitBtn">Sign Petition</button>
        </form>
    </div>
    {% endif %}
</div>

<div class="toast" id="toast"></div>

<script>
    const canvas = document.getElementById('signatureCanvas');
    if (canvas) {
        const ctx = canvas.getContext('2d');
        let drawing = false;
        let hasSigned = false;

        function resizeCanvas() {
            const wrapper = canvas.parentElement;
            const ratio = window.devicePixelRatio || 1;
            canvas.width = wrapper.clientWidth * ratio;
            canvas.height = 150 * ratio;
            canvas.style.height = '150px';
            ctx.scale(ratio, ratio);
            ctx.strokeStyle = '#1a1a2e';
            ctx.lineWidth = 2;
            ctx.lineCap = 'round';
            ctx.lineJoin = 'round';
        }

        resizeCanvas();
        window.addEventListener('resize', resizeCanvas);

        function getPos(e) {
            const rect = canvas.getBoundingClientRect();
            const touch = e.touches ? e.touches[0] : e;
            return {
                x: touch.clientX - rect.left,
                y: touch.clientY - rect.top
            };
        }

        canvas.addEventListener('mousedown', (e) => {
            drawing = true;
            const pos = getPos(e);
            ctx.beginPath();
            ctx.moveTo(pos.x, pos.y);
        });

        canvas.addEventListener('mousemove', (e) => {
            if (!drawing) return;
            hasSigned = true;
            const pos = getPos(e);
            ctx.lineTo(pos.x, pos.y);
            ctx.stroke();
        });

        canvas.addEventListener('mouseup', () => drawing = false);
        canvas.addEventListener('mouseleave', () => drawing = false);

        canvas.addEventListener('touchstart', (e) => {
            e.preventDefault();
            drawing = true;
            const pos = getPos(e);
            ctx.beginPath();
            ctx.moveTo(pos.x, pos.y);
        });

        canvas.addEventListener('touchmove', (e) => {
            e.preventDefault();
            if (!drawing) return;
            hasSigned = true;
            const pos = getPos(e);
            ctx.lineTo(pos.x, pos.y);
            ctx.stroke();
        });

        canvas.addEventListener('touchend', () => drawing = false);

        window.clearSignature = function() {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            hasSigned = false;
        };

        function getSignatureData() {
            const tempCanvas = document.createElement('canvas');
            tempCanvas.width = canvas.width;
            tempCanvas.height = canvas.height;
            const tempCtx = tempCanvas.getContext('2d');
            tempCtx.drawImage(canvas, 0, 0);
            return tempCanvas.toDataURL('image/png');
        }

        function showToast(msg, isError) {
            const toast = document.getElementById('toast');
            toast.textContent = msg;
            toast.className = 'toast' + (isError ? ' error' : '');
            toast.classList.add('show');
            setTimeout(() => toast.classList.remove('show'), 3500);
        }

        window.submitForm = async function(e) {
            e.preventDefault();

            if (!hasSigned) {
                showToast('Please draw your signature before submitting.', true);
                return false;
            }

            const btn = document.getElementById('submitBtn');
            btn.disabled = true;
            btn.textContent = 'Submitting...';

            const data = {
                printed_name: document.getElementById('printedName').value.trim(),
                address: document.getElementById('address').value.trim(),
                signature_data: getSignatureData()
            };

            try {
                const resp = await fetch('/sign', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                });
                const result = await resp.json();

                if (result.success) {
                    showToast('Thank you for signing the petition!', false);
                    setTimeout(() => window.location.href = '/?signed=1', 1500);
                } else {
                    showToast(result.error || 'Something went wrong.', true);
                    btn.disabled = false;
                    btn.textContent = 'Sign Petition';
                }
            } catch (err) {
                showToast('Network error. Please try again.', true);
                btn.disabled = false;
                btn.textContent = 'Sign Petition';
            }

            return false;
        };
    }
</script>

</body>
</html>
"""

ADMIN_LOGIN_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Admin Login - Colledge Farms Petition</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: Arial, sans-serif; background: #f5f5f0; display: flex; justify-content: center; align-items: center; min-height: 100vh; }
        .login-box { background: #fff; padding: 40px; border-radius: 8px; box-shadow: 0 0 20px rgba(0,0,0,0.1); width: 100%; max-width: 400px; }
        .login-box h1 { font-size: 22px; color: #2d3748; margin-bottom: 6px; }
        .login-box p { color: #666; font-size: 14px; margin-bottom: 24px; }
        .login-box label { display: block; font-weight: bold; font-size: 13px; color: #2d3748; margin-bottom: 5px; }
        .login-box input { width: 100%; padding: 10px 14px; border: 1px solid #ccc; border-radius: 5px; font-size: 16px; margin-bottom: 16px; }
        .login-box input:focus { outline: none; border-color: #2d3748; }
        .login-box button { width: 100%; padding: 12px; background: #2d3748; color: #fff; border: none; border-radius: 5px; font-size: 16px; font-weight: bold; cursor: pointer; }
        .login-box button:hover { background: #1a202c; }
        .error { background: #fed7d7; color: #c53030; padding: 10px; border-radius: 5px; margin-bottom: 16px; font-size: 14px; }
    </style>
</head>
<body>
<div class="login-box">
    <h1>Petition Admin</h1>
    <p>View and manage petition signatures</p>
    {% if error %}<div class="error">{{ error }}</div>{% endif %}
    <form method="POST">
        <label>Password</label>
        <input type="password" name="password" autofocus required>
        <button type="submit">Log In</button>
    </form>
</div>
</body>
</html>
"""

ADMIN_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Admin Dashboard - Colledge Farms Petition</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: Arial, sans-serif; background: #f5f5f0; color: #2c2c2c; }

        .topbar {
            background: #2d3748; color: #fff; padding: 14px 30px;
            display: flex; justify-content: space-between; align-items: center;
        }
        .topbar h1 { font-size: 18px; }
        .topbar a { color: #cbd5e0; text-decoration: none; font-size: 14px; }
        .topbar a:hover { color: #fff; }

        .stats {
            display: flex; gap: 20px; padding: 24px 30px; flex-wrap: wrap;
        }
        .stat-card {
            background: #fff; border-radius: 8px; padding: 20px 28px;
            box-shadow: 0 1px 4px rgba(0,0,0,0.08); flex: 1; min-width: 200px;
        }
        .stat-card .label { font-size: 13px; color: #888; text-transform: uppercase; letter-spacing: 0.5px; }
        .stat-card .value { font-size: 36px; font-weight: bold; color: #2d3748; margin-top: 4px; }

        .section {
            background: #fff; margin: 0 30px 24px; border-radius: 8px;
            box-shadow: 0 1px 4px rgba(0,0,0,0.08); overflow: hidden;
        }
        .section-header {
            padding: 16px 20px; border-bottom: 1px solid #e2e8f0;
            display: flex; justify-content: space-between; align-items: center;
        }
        .section-header h2 { font-size: 16px; color: #2d3748; }
        .export-btn {
            background: #38a169; color: #fff; border: none; padding: 8px 16px;
            border-radius: 5px; cursor: pointer; font-size: 13px; font-weight: bold;
            text-decoration: none;
        }
        .export-btn:hover { background: #2f855a; }

        table { width: 100%; border-collapse: collapse; }
        th { background: #f7fafc; padding: 10px 16px; text-align: left; font-size: 12px; color: #888; text-transform: uppercase; letter-spacing: 0.5px; border-bottom: 1px solid #e2e8f0; }
        td { padding: 12px 16px; border-bottom: 1px solid #f0f0f0; font-size: 14px; vertical-align: middle; }
        tr:hover { background: #f7fafc; }
        .sig-num { width: 50px; text-align: center; color: #888; font-weight: bold; }
        .sig-img { height: 45px; border: 1px solid #e2e8f0; border-radius: 3px; background: #fff; }
        .timestamp { color: #888; font-size: 13px; }
        .no-sigs { text-align: center; padding: 40px; color: #999; }

        @media (max-width: 600px) {
            .stats { padding: 16px; }
            .section { margin: 0 16px 16px; }
            td, th { padding: 8px 10px; font-size: 13px; }
            .sig-img { height: 35px; }
        }
    </style>
</head>
<body>

<div class="topbar">
    <h1>Petition Admin Dashboard</h1>
    <div>
        <a href="/" style="margin-right: 16px;">View Petition</a>
        <a href="/admin/logout">Log Out</a>
    </div>
</div>

<div class="stats">
    <div class="stat-card">
        <div class="label">Total Signatures</div>
        <div class="value">{{ total }}</div>
    </div>
    <div class="stat-card">
        <div class="label">Latest Signature</div>
        <div class="value" style="font-size: 18px;">{{ latest_name if latest_name else 'None yet' }}</div>
    </div>
</div>

<div class="section">
    <div class="section-header">
        <h2>All Signatures</h2>
        <a href="/admin/export" class="export-btn">Export CSV</a>
    </div>
    {% if signatures %}
    <table>
        <thead>
            <tr>
                <th>#</th>
                <th>Printed Name</th>
                <th>Address</th>
                <th>Signature</th>
                <th>Signed At</th>
            </tr>
        </thead>
        <tbody>
            {% for sig in signatures %}
            <tr>
                <td class="sig-num">{{ sig['id'] }}</td>
                <td>{{ sig['printed_name'] }}</td>
                <td>{{ sig['address'] }}</td>
                <td><img class="sig-img" src="{{ sig['signature_data'] }}" alt="Signature"></td>
                <td class="timestamp">{{ sig['signed_at'] }}</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
    {% else %}
    <p class="no-sigs">No signatures yet.</p>
    {% endif %}
</div>

</body>
</html>
"""


# --- Routes ---

@app.route("/")
def index():
    conn = get_db()
    signatures = db_fetchall(conn, "SELECT id FROM signatures ORDER BY id")
    total = len(signatures)
    conn.close()
    just_signed = request.args.get("signed") == "1"
    return render_template_string(PETITION_TEMPLATE, total=total, just_signed=just_signed)


@app.route("/sign", methods=["POST"])
def sign():
    data = request.get_json()
    name = (data.get("printed_name") or "").strip()
    address = (data.get("address") or "").strip()
    sig = data.get("signature_data", "")

    if not name or not address or not sig:
        return jsonify({"success": False, "error": "All fields are required."})

    conn = get_db()
    if DATABASE_URL:
        db_execute(conn, "INSERT INTO signatures (printed_name, address, signature_data) VALUES (%s, %s, %s)", (name, address, sig))
    else:
        db_execute(conn, "INSERT INTO signatures (printed_name, address, signature_data) VALUES (?, ?, ?)", (name, address, sig))
    conn.close()
    return jsonify({"success": True})


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    error = None
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session["admin"] = True
            return redirect(url_for("admin_dashboard"))
        error = "Incorrect password."
    return render_template_string(ADMIN_LOGIN_TEMPLATE, error=error)


@app.route("/admin/logout")
def admin_logout():
    session.pop("admin", None)
    return redirect(url_for("index"))


@app.route("/admin")
@admin_required
def admin_dashboard():
    conn = get_db()
    signatures = db_fetchall(conn, "SELECT * FROM signatures ORDER BY id")
    total = len(signatures)
    latest_name = signatures[-1]["printed_name"] if signatures else None
    conn.close()
    return render_template_string(ADMIN_TEMPLATE, signatures=signatures, total=total, latest_name=latest_name)


@app.route("/admin/export")
@admin_required
def admin_export():
    conn = get_db()
    signatures = db_fetchall(conn, "SELECT id, printed_name, address, signed_at FROM signatures ORDER BY id")
    conn.close()

    import csv
    import io
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["#", "Printed Name", "Address", "Signed At"])
    for sig in signatures:
        writer.writerow([sig["id"], sig["printed_name"], sig["address"], sig["signed_at"]])

    from flask import Response
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=petition_signatures.csv"}
    )


@app.route("/api/signatures")
def api_signatures():
    conn = get_db()
    rows = db_fetchall(conn, "SELECT id, printed_name, address, signed_at FROM signatures ORDER BY id")
    conn.close()
    return jsonify(rows)


# Initialize database on import (needed for gunicorn)
try:
    init_db()
except Exception as e:
    print(f"Warning: Could not initialize database: {e}")


@app.route("/health")
def health():
    try:
        conn = get_db()
        conn.close()
        return jsonify({"status": "ok", "db": "connected", "db_url": bool(DATABASE_URL)})
    except Exception as e:
        return jsonify({"status": "error", "error": str(e), "db_url": bool(DATABASE_URL)}), 500

if __name__ == "__main__":
    print("Starting Colledge Farms HOA Petition App...")
    port = int(os.environ.get("PORT", 5000))
    print(f"Open http://localhost:{port} in your browser")
    print(f"Admin dashboard: http://localhost:{port}/admin")
    app.run(debug=True, port=port)
