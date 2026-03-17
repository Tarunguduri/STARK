import cv2
import logging
import traceback

from core.reasoning import normalize_gesture_name, workflow_key_for_gesture


logger = logging.getLogger(__name__)

class GestureDetector:
    """Uses MediaPipe to detect hand landmarks and classify gestures using finger-state patterns."""
    
    def __init__(self):
        self.mp_hands = None
        self.mp_draw = None
        self.hands = None
        self._last_logged_gesture = None
        try:
            from mediapipe.python.solutions import drawing_utils
            from mediapipe.python.solutions import hands as hands_solution

            self.mp_hands = hands_solution
            self.hands = self.mp_hands.Hands(
                static_image_mode=False,
                max_num_hands=1,
                min_detection_confidence=0.7,
                min_tracking_confidence=0.5
            )
            self.mp_draw = drawing_utils
            logger.info("MediaPipe initialized successfully via solutions API.")
        except Exception as e:
            logger.warning("MediaPipe solutions API not available. Gesture detection disabled: %s", e)
            logger.debug(traceback.format_exc())
        
    def process_frame(self, frame):
        """Processes an image frame and returns landmarks and the image annotated."""
        if self.hands is None:
            return None, frame
            
        img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.hands.process(img_rgb)
        
        annotated_image = frame.copy()
        landmarks = None
        
        if results.multi_hand_landmarks:
            for hand_landmarks in results.multi_hand_landmarks:
                self.mp_draw.draw_landmarks(
                    annotated_image, 
                    hand_landmarks, 
                    self.mp_hands.HAND_CONNECTIONS
                )
                landmarks = hand_landmarks.landmark
                break  # Only process the first hand
                
        return landmarks, annotated_image
        
    def detect_gesture(self, frame):
        """Helper for STARK GUI - returns (gesture_name, annotated_frame)"""
        landmarks, annotated_image = self.process_frame(frame)
        gesture = self.classify_gesture(landmarks)
        return gesture, annotated_image

    @staticmethod
    def canonical_name(gesture_name: str) -> str:
        return normalize_gesture_name(gesture_name)

    @staticmethod
    def workflow_key(gesture_name: str) -> str:
        return workflow_key_for_gesture(gesture_name)
        
    def classify_gesture(self, landmarks) -> str:
        """
        Classifies gesture using finger-state pattern detection.

        Finger index: [thumb, index, middle, ring, pinky]

        Pattern table:
          1 1 1 1 1  -> Open Palm    (Coding Workspace)
          0 1 1 0 0  -> Peace Sign   (Research Mode)
          1 1 0 0 1  -> Rock Sign    (Entertainment Mode)
          0 0 0 0 0  -> Fist         (Focus Mode)
          0 1 0 0 0  -> Pointing     (Open Browser)
          1 0 0 0 0  -> Single Finger (Assistant Listening)
          0 0 1 1 1  -> OK Sign       (Confirm/Three Fingers)
        """
        if not landmarks:
            return "None"

        # Thumb: use x-axis (right hand in mirrored webcam view)
        thumb_up = landmarks[4].x < landmarks[3].x

        # Fingers 1-4: tip y < pip y means extended (y increases downward)
        tip_ids = [8, 12, 16, 20]
        pip_ids = [6, 10, 14, 18]
        f = [thumb_up] + [
            landmarks[tip_ids[i]].y < landmarks[pip_ids[i]].y
            for i in range(4)
        ]
        # f = [thumb, index, middle, ring, pinky]

        # Exact pattern matching
        res = "Unknown"
        if f[0] and f[1] and f[2] and f[3] and f[4]:                              res = "Open Palm"
        elif not f[0] and not f[1] and not f[2] and not f[3] and not f[4]:         res = "Fist"
        elif not f[0] and f[1] and f[2] and not f[3] and not f[4]:                 res = "Peace Sign"
        elif f[0] and f[1] and not f[2] and not f[3] and f[4]:                     res = "Rock Sign"
        elif not f[0] and f[1] and not f[2] and not f[3] and not f[4]:             res = "Pointing"
        elif f[0] and not f[1] and not f[2] and not f[3] and not f[4]:             res = "Single Finger"
        elif not f[0] and not f[1] and f[2] and f[3] and f[4]:                     res = "OK Sign"
        
        if res != "Unknown" and res != self._last_logged_gesture:
            logger.info("[System] Gesture detected: %s", res)
            self._last_logged_gesture = res
        elif res in ("Unknown", "None"):
            self._last_logged_gesture = None
        return res
