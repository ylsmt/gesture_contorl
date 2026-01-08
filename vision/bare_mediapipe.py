import cv2
import numpy as np
import mediapipe as mp

class BareHandTracker:
    def __init__(self, min_det=0.6, min_track=0.6, max_hands=1):
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=max_hands,
            min_detection_confidence=min_det,
            min_tracking_confidence=min_track
        )

    def process(self, frame_bgr):
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        res = self.hands.process(rgb)

        h, w = frame_bgr.shape[:2]
        if not res.multi_hand_landmarks:
            return None
        lm = res.multi_hand_landmarks[0]
        pts = np.array([[p.x * w, p.y * h] for p in lm.landmark], dtype=np.float32)
        return pts