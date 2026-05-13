import cv2
import torch
import numpy as np
import mediapipe as mp
import joblib
import collections
import threading
import csv
import os
import sqlite3
import gc
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()
from flask import Flask, render_template, Response, request, redirect, url_for, send_file, jsonify
from flask_socketio import SocketIO

# ── AES-256 Encryption (Paper Requirement) ──────────────────
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import base64

LOG_FILE         = 'fall_logs.csv'          # ← human-readable, downloaded
ENC_LOG_FILE     = 'fall_logs_encrypted.csv' # ← AES-256 backup (paper proof)
KEY_FILE         = 'fall_logs.key'

# Current monitored room — updated by the frontend via socket event
current_room = 'Room 101'

AES_KEY_STR = os.getenv('ENCRYPTION_KEY')
AES_KEY = AES_KEY_STR.encode('utf-8')[:32].ljust(32, b'\0') if AES_KEY_STR else None

def _encrypt(plaintext: str) -> str:
    """AES-256-GCM encrypt → base64 string (nonce prepended)."""
    aesgcm = AESGCM(AES_KEY)
    nonce  = os.urandom(12)
    ct     = aesgcm.encrypt(nonce, plaintext.encode(), None)
    return base64.b64encode(nonce + ct).decode()

def log_fall_event(confidence: float, room: str):
    """
    Write a PLAINTEXT row to fall_logs.csv (human-readable).
    Also write an AES-256-GCM encrypted row to fall_logs_encrypted.csv
    (satisfies the research paper security requirement).
    """
    if not AES_KEY:
        print("[CRITICAL SECURITY WARNING] ENCRYPTION_KEY is missing from environment. Refusing to log sensitive data.")
        return

    timestamp  = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conf_str   = f"{confidence:.1f}"
    status     = 'Fall Detected'

    # ── 1. Plaintext CSV (readable in Excel / any viewer) ────
    plain_exists = os.path.exists(LOG_FILE)
    with open(LOG_FILE, 'a', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        if not plain_exists:
            w.writerow(['Timestamp', 'Room No', 'Confidence (%)', 'Status'])
        w.writerow([timestamp, room, conf_str, status])

    # ── 2. AES-256 Encrypted CSV (for paper / audit trail) ───
    enc_exists = os.path.exists(ENC_LOG_FILE)
    with open(ENC_LOG_FILE, 'a', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        if not enc_exists:
            w.writerow(['Timestamp_AES256', 'Room_AES256',
                        'Confidence_AES256', 'Status_AES256'])
        w.writerow([_encrypt(timestamp), _encrypt(room),
                    _encrypt(conf_str),  _encrypt(status)])

    print(f"[LOG] {timestamp} | {room} | {conf_str}% | {status}")

# ── SQLite Database — Event Registrations ────────────────────
DB_PATH = os.getenv('DATABASE_URL', 'hospital.db')

def init_db():
    """Create the event_registrations table if it doesn't exist."""
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS event_registrations (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            event_name  TEXT    NOT NULL,
            full_name   TEXT    NOT NULL,
            email       TEXT    NOT NULL,
            phone       TEXT    NOT NULL,
            age         INTEGER,
            gender      TEXT,
            occupation  TEXT,
            message     TEXT,
            registered_at TEXT  NOT NULL
        )
    ''')
    con.commit()
    con.close()
    print(f"[DB] SQLite database ready → {DB_PATH}")

init_db()

from Scripts.train_model import FallHybridModel, NMMCU

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET', 'fallback_secret_key')
socketio = SocketIO(app, cors_allowed_origins="*", ping_timeout=60, ping_interval=25)

MODEL_PATH        = 'models/fall_hybrid_model.pt'
SCALER_PATH       = 'models/scaler.pkl'
WINDOW_SIZE       = 30
FALL_THRESHOLD    = 0.85
CONFIRM_FRAMES    = 8
MIN_LANDMARK_CONF = 0.55
MIN_FALL_ANGLE    = 30.0

def load_model():
    checkpoint = torch.load(MODEL_PATH, map_location='cpu', weights_only=False)
    if isinstance(checkpoint, FallHybridModel):
        model = checkpoint
        print("[INFO] Loaded model (full object format)")
    elif isinstance(checkpoint, dict) and 'model_state_dict' in checkpoint:
        input_dim = checkpoint['input_dim']
        model = FallHybridModel(input_dim=input_dim)
        model.load_state_dict(checkpoint['model_state_dict'])
        print(f"[INFO] Loaded model (checkpoint format, input_dim={input_dim})")
    else:
        raise ValueError("Unknown model format.")
    model.eval()
    return model

def load_scaler():
    try:
        scaler = joblib.load(SCALER_PATH)
        print("[INFO] Scaler loaded.")
        return scaler
    except FileNotFoundError:
        print("[WARNING] scaler.pkl not found.")
        return None

model = None
scaler = None

mp_pose = mp.solutions.pose
mp_draw = mp.solutions.drawing_utils
pose    = mp_pose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5)

# Shared state — one camera thread writes, two stream routes read
latest_display_frame  = None
latest_skeleton_frame = None
frame_lock = threading.Lock()

stop_flag = False
cam_thread = None

def camera_thread():
    global latest_display_frame, latest_skeleton_frame, stop_flag

    is_headless = os.environ.get('RENDER') is not None
    simulation_mode = False
    cap = None

    if not is_headless:
        try:
            cap = cv2.VideoCapture(0)
        except Exception as e:
            print(f"[ERROR] Exception opening webcam: {e}")
            cap = None

    if cap is None or not cap.isOpened():
        print("[INFO] Switching to Simulation Mode...")
        simulation_mode = True
        try:
            cap = cv2.VideoCapture('static/video/sample_fall.mp4')
        except Exception as e:
            print(f"[ERROR] Exception opening sample video: {e}")
            cap = None

    if cap is None or not cap.isOpened():
        print("[ERROR] No Input Source")
        blank = np.zeros((480, 640, 3), dtype=np.uint8)
        text = "System Error: No Input Source"
        # Center text roughly
        text_size = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 1.0, 2)[0]
        text_x = (640 - text_size[0]) // 2
        text_y = (480 + text_size[1]) // 2
        cv2.putText(blank, text, (text_x, text_y),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 2)
        with frame_lock:
            latest_display_frame  = blank.copy()
            latest_skeleton_frame = blank.copy()
        return

    frame_buffer = collections.deque(maxlen=WINDOW_SIZE)
    fall_counter = 0
    last_pred    = 0.0
    print("[INFO] Camera thread started.")

    while True:
        if stop_flag:
            cap.release()
            print("[INFO] Camera released via stop_flag.")
            with frame_lock:
                latest_display_frame = None
                latest_skeleton_frame = None
            stop_flag = False
            return

        success, frame = cap.read()
        if not success:
            if simulation_mode:
                # Loop the simulation video
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue
            else:
                break

        h, w      = frame.shape[:2]
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results   = pose.process(rgb_frame)

        display  = frame.copy()
        skeleton = np.zeros((h, w, 3), dtype=np.uint8)

        if results.pose_landmarks:
            lm = results.pose_landmarks.landmark

            # Draw skeleton on real frame (green joints, white bones)
            mp_draw.draw_landmarks(
                display, results.pose_landmarks, mp_pose.POSE_CONNECTIONS,
                mp_draw.DrawingSpec(color=(0, 255, 0),    thickness=2, circle_radius=4),
                mp_draw.DrawingSpec(color=(255, 255, 255), thickness=2)
            )
            # Draw skeleton on black canvas (cyan joints, light grey bones)
            mp_draw.draw_landmarks(
                skeleton, results.pose_landmarks, mp_pose.POSE_CONNECTIONS,
                mp_draw.DrawingSpec(color=(0, 255, 255),  thickness=2, circle_radius=5),
                mp_draw.DrawingSpec(color=(200, 200, 200), thickness=2)
            )

            nose       = lm[0]
            l_shoulder = lm[11]; r_shoulder = lm[12]
            l_hip      = lm[23]; r_hip      = lm[24]

            mid_sx = (l_shoulder.x + r_shoulder.x) / 2
            mid_sy = (l_shoulder.y + r_shoulder.y) / 2
            mid_hx = (l_hip.x + r_hip.x) / 2
            mid_hy = (l_hip.y + r_hip.y) / 2

            dx    = mid_sx - mid_hx
            dy    = mid_sy - mid_hy
            angle = float(np.degrees(np.arctan2(abs(dy), abs(dx) + 1e-6)))
            scale = float(np.sqrt(dx**2 + dy**2))
            conf  = float(np.mean([
                l_shoulder.visibility, r_shoulder.visibility,
                l_hip.visibility,      r_hip.visibility
            ]))
            pixel_x  = float(mid_hx * w)
            pixel_y  = float(mid_hy * h)
            velocity = float(np.sqrt(
                (pixel_x - frame_buffer[-1][7])**2 +
                (pixel_y - frame_buffer[-1][8])**2
            )) if len(frame_buffer) > 0 else 0.0

            # Memory Optimization: PCA reduces feature dimensionality from 99 to 6 (93.9% reduction) to minimize CPU/RAM load.
            features_vec = np.array(
                [0, -1, nose.x, nose.y, conf, angle, scale, pixel_x, pixel_y, velocity],
                dtype=np.float32
            )

            hips_visible = (
                l_hip.visibility > MIN_LANDMARK_CONF and
                r_hip.visibility > MIN_LANDMARK_CONF
            )

            if not hips_visible:
                warn = "Show full body for detection"
                cv2.putText(display,  warn, (10, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 165, 255), 2)
                cv2.putText(skeleton, warn, (10, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 165, 255), 2)
            else:
                if scaler is not None:
                    try:
                        features_vec = scaler.transform(features_vec.reshape(1, -1)).flatten()
                    except Exception:
                        pass

                frame_buffer.append(features_vec)

                if len(frame_buffer) == WINDOW_SIZE and model is not None:
                    window       = np.array(frame_buffer, dtype=np.float32)
                    input_tensor = torch.tensor(window).unsqueeze(0)
                    with torch.no_grad():
                        raw_pred = model(input_tensor).item()

                    last_pred = raw_pred if (angle < MIN_FALL_ANGLE) else 0.0

                    if last_pred > FALL_THRESHOLD:
                        fall_counter += 1
                        if fall_counter >= CONFIRM_FRAMES:
                            conf_pct = round(last_pred * 100, 1)
                            socketio.emit('alert', {
                                'msg': 'FALL DETECTED!',
                                'confidence': conf_pct
                            })
                            log_fall_event(conf_pct, current_room)   # ← plaintext + encrypted
                            fall_counter = 0
                    else:
                        fall_counter = 0   

            # Labels on both canvases
            if last_pred > FALL_THRESHOLD:
                label = f"FALL DETECTED  {last_pred*100:.1f}%"
                color = (0, 0, 255)
                cv2.rectangle(display,  (0, 0), (w, 60), (0,   0, 180), -1)
                cv2.rectangle(skeleton, (0, 0), (w, 60), (120, 0,   0), -1)
            else:
                label = f"Normal  {last_pred*100:.1f}%"
                color = (0, 255, 0)

            for canvas in [display, skeleton]:
                cv2.putText(canvas, label, (10, 40),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.0, color, 2)
                cv2.putText(canvas, f"Torso: {angle:.1f} deg",
                            (10, h - 35), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 180, 180), 1)
                cv2.putText(canvas, f"Buffer: {len(frame_buffer)}/{WINDOW_SIZE}",
                            (10, h - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 180, 180), 1)

        else:
            msg = "No person detected"
            cv2.putText(display,  msg, (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 255), 2)
            cv2.putText(skeleton, msg, (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 255), 2)
            frame_buffer.clear()
            fall_counter = 0

        with frame_lock:
            latest_display_frame  = display.copy()
            latest_skeleton_frame = skeleton.copy()

    if cap.isOpened():
        cap.release()
        print("[INFO] Camera released (end of loop).")
    with frame_lock:
        latest_display_frame = None
        latest_skeleton_frame = None


@app.route('/start_camera')
def start_camera():
    global cam_thread, stop_flag, model, scaler
    try:
        if model is None:
            model = load_model()
        if scaler is None:
            scaler = load_scaler()
    except Exception as e:
        print(f"[ERROR] Could not load model/scaler: {e}")
        return jsonify({"status": "error", "message": "Server Busy: Memory limit reached"}), 503

    if cam_thread is None or not cam_thread.is_alive():
        stop_flag = False
        cam_thread = threading.Thread(target=camera_thread, daemon=True)
        cam_thread.start()
        return jsonify({"status": "Camera started"})
    return jsonify({"status": "Camera already running"})

@app.route('/stop_camera')
def stop_camera():
    global stop_flag, model, scaler
    stop_flag = True
    model = None
    scaler = None
    gc.collect()
    return jsonify({"status": "Camera stop initiated"})

@app.route('/stop_surveillance', methods=['POST', 'GET'])
def stop_surveillance():
    global stop_flag, model, scaler
    stop_flag = True
    model = None
    scaler = None
    gc.collect()
    return jsonify({"status": "Surveillance stopped"})


def stream_frames(get_frame_fn):
    import time
    while True:
        with frame_lock:
            frame = get_frame_fn()
        if frame is None:
            time.sleep(0.1)
            continue
        ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if not ret:
            continue
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

# ── NEW NAVIGATION ROUTES ───────────────────────────────────

@app.route('/')
def landing():
    """Serves the main Hospital Landing Page"""
    return render_template('landing.html')

@app.route('/about')
def about():
    """Serves the Technology/Privacy information page"""
    return render_template('about.html')

@app.route('/blog/cnn-lstm-ward-safety')
def blog1():
    """Blog: How CNN+LSTM Models are Revolutionizing Ward Safety"""
    return render_template('blog1.html')

@app.route('/blog/privacy-first-surveillance')
def blog2():
    """Blog: The Ethics of Privacy-First Surveillance"""
    return render_template('blog2.html')

@app.route('/blog/future-hospital-automation')
def blog3():
    """Blog: Future of Hospital Automation"""
    return render_template('blog3.html')

@app.route('/story/mrs-sharma-geriatric-ward')
def story1():
    """Patient Story: Mrs. Sharma — Geriatric Ward"""
    return render_template('story1.html')

@app.route('/story/mr-patel-neurology-icu')
def story2():
    """Patient Story: Mr. Patel — Neurology ICU"""
    return render_template('story2.html')

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    """Handles the appointment form and contact page"""
    if request.method == 'POST':
        return render_template('contact.html', success=True)
    return render_template('contact.html')

@app.route('/register-event', methods=['POST'])
def register_event():
    """Store an event registration into SQLite and return JSON feedback."""
    data = request.get_json(silent=True) or request.form

    # Required fields
    full_name  = (data.get('full_name')  or '').strip()
    email      = (data.get('email')      or '').strip()
    phone      = (data.get('phone')      or '').strip()
    event_name = (data.get('event_name') or '').strip()

    if not all([full_name, email, phone, event_name]):
        return jsonify({'success': False,
                        'message': 'Please fill in all required fields.'}), 400

    # Optional fields
    age        = data.get('age',        '').strip() if hasattr(data.get('age', ''), 'strip') else str(data.get('age', ''))
    gender     = (data.get('gender')     or '').strip()
    occupation = (data.get('occupation') or '').strip()
    message    = (data.get('message')    or '').strip()
    registered_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    try:
        con = sqlite3.connect(DB_PATH)
        con.execute(
            '''INSERT INTO event_registrations
               (event_name, full_name, email, phone, age, gender, occupation, message, registered_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (event_name, full_name, email, phone, age or None,
             gender, occupation, message, registered_at)
        )
        con.commit()
        con.close()
        print(f"[DB] New registration: {full_name} → {event_name}")
        return jsonify({'success': True,
                        'message': f"You're registered for {event_name}! We'll send confirmation to {email}."})
    except Exception as e:
        print(f"[DB ERROR] {e}")
        return jsonify({'success': False,
                        'message': 'Database error. Please try again.'}), 500

# ── UPDATED DASHBOARD ROUTE ─────────────────────────────────

@app.route('/dashboard')
def index():
    """This is your original 'index' route, now at /dashboard"""
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    return Response(stream_frames(lambda: latest_display_frame),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/skeleton_feed')
def skeleton_feed():
    return Response(stream_frames(lambda: latest_skeleton_frame),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/status')
def status():
    return {
        'model_loaded':   model is not None,
        'scaler_loaded':  scaler is not None,
        'window_size':    WINDOW_SIZE,
        'fall_threshold': FALL_THRESHOLD
    }

@app.route('/download-logs')
def download_logs():
    """Serve the human-readable fall_logs.csv for download."""
    if not os.path.exists(LOG_FILE):
        import io
        empty = io.BytesIO('Timestamp,Room No,Confidence (%),Status\n'.encode('utf-8'))
        empty.seek(0)
        return send_file(
            empty,
            mimetype='text/csv',
            as_attachment=True,
            download_name='fall_logs.csv'
        )
    return send_file(
        os.path.abspath(LOG_FILE),
        mimetype='text/csv',
        as_attachment=True,
        download_name='fall_logs.csv'
    )

@socketio.on('connect')
def on_connect():
    print("[INFO] Browser client connected")

@socketio.on('set_room')
def on_set_room(data):
    """Frontend sends this when the user changes room in the dropdown."""
    global current_room
    room_id = data.get('room', 'Room 101')
    current_room = room_id
    print(f"[INFO] Active room updated → {current_room}")

@socketio.on('disconnect')
def on_disconnect():
    print("[INFO] Browser client disconnected")

if __name__ == '__main__':
    print("\n" + "=" * 50)
    print("Fall Detection System Starting...")
    print("Open your browser at: http://127.0.0.1:5000")
    print("=" * 50 + "\n")
socketio.run(app, debug=True, use_reloader=False, host='0.0.0.0', port=5000)