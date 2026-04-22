import cv2
import torch
import numpy as np
import mediapipe as mp
import joblib
import collections
import threading
from flask import Flask, render_template, Response, request, redirect, url_for
from flask_socketio import SocketIO

from Scripts.train_model import FallHybridModel, NMMCU

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

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

try:
    model = load_model()
except Exception as e:
    print(f"[ERROR] Could not load model: {e}")
    model = None

scaler = load_scaler()

mp_pose = mp.solutions.pose
mp_draw = mp.solutions.drawing_utils
pose    = mp_pose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5)

# Shared state — one camera thread writes, two stream routes read
latest_display_frame  = None
latest_skeleton_frame = None
frame_lock = threading.Lock()

def camera_thread():
    global latest_display_frame, latest_skeleton_frame

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("[ERROR] Cannot open webcam")
        blank = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.putText(blank, "Camera not found!", (100, 240),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 255), 2)
        with frame_lock:
            latest_display_frame  = blank.copy()
            latest_skeleton_frame = blank.copy()
        return

    frame_buffer = collections.deque(maxlen=WINDOW_SIZE)
    fall_counter = 0
    last_pred    = 0.0
    print("[INFO] Camera thread started.")

    while True:
        success, frame = cap.read()
        if not success:
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
                            socketio.emit('alert', {
                                'msg': 'FALL DETECTED!',
                                'confidence': round(last_pred * 100, 1)
                            })
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

    cap.release()
    print("[INFO] Camera released.")


# Start background camera thread
cam_thread = threading.Thread(target=camera_thread, daemon=True)
cam_thread.start()


def stream_frames(get_frame_fn):
    while True:
        with frame_lock:
            frame = get_frame_fn()
        if frame is None:
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

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    """Handles the appointment form and contact page"""
    if request.method == 'POST':
        # You can grab form data here: request.form.get('name')
        return render_template('contact.html', success=True)
    return render_template('contact.html')

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

@socketio.on('connect')
def on_connect():
    print("[INFO] Browser client connected")

@socketio.on('disconnect')
def on_disconnect():
    print("[INFO] Browser client disconnected")

if __name__ == '__main__':
    print("\n" + "=" * 50)
    print("Fall Detection System Starting...")
    print("Open your browser at: http://127.0.0.1:5000")
    print("=" * 50 + "\n")
socketio.run(app, debug=True, use_reloader=False, host='0.0.0.0', port=5000)