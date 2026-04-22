import cv2
import mediapipe as mp
import numpy as np

class FallPreprocessor:
    def __init__(self):
        self.mp_pose = mp.solutions.pose.Pose(static_image_mode=False, min_detection_confidence=0.5)
        self.clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))

    def apply_filters(self, frame):
        # 1. Noise Removal (Gaussian Blur) [cite: 37]
        blurred = cv2.GaussianBlur(frame, (5, 5), 0)
        
        # 2. Image Enhancement (CLAHE) [cite: 44]
        lab = cv2.cvtColor(blurred, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        cl = self.clahe.apply(l)
        enhanced = cv2.merge((cl, a, b))
        return cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)

    def get_skeletal_mask(self, frame):
        # 3. Privacy Masking [cite: 58]
        results = self.mp_pose.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        mask = np.zeros(frame.shape, dtype=np.uint8) # Blank canvas [cite: 58]
        
        if results.pose_landmarks:
            # Draw stick figure logic (MediaPipe landmarks) [cite: 60]
            mp.solutions.drawing_utils.draw_landmarks(
                mask, results.pose_landmarks, mp.solutions.pose.POSE_CONNECTIONS)
            
            # Extract 33 coordinates for PCA [cite: 60]
            coords = [[lm.x, lm.y, lm.z] for lm in results.pose_landmarks.landmark]
            return mask, np.array(coords).flatten()
        return mask, None