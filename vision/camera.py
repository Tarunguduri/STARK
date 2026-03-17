import cv2
import logging
import threading
import time


logger = logging.getLogger(__name__)


class CameraComponent:
    """Handles threaded camera frame reading from OpenCV."""
    
    def __init__(self, camera_index=0):
        self.camera_index = camera_index
        # Try different backends for Windows
        for backend in [cv2.CAP_DSHOW, cv2.CAP_MSMF, None]:
            if backend is not None:
                self.cap = cv2.VideoCapture(self.camera_index, backend)
            else:
                self.cap = cv2.VideoCapture(self.camera_index)
            
            if self.cap.isOpened():
                logger.info("Camera opened with backend: %s", backend)
                break
        else:
            logger.warning("Camera failed to open for index %s", self.camera_index)
        
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.ret = False
        self.frame = None
        self.running = False
        self.lock = threading.Lock()
        
    def start(self):
        """Start the background camera thread."""
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._update, daemon=True)
            self.thread.start()
            
    def _update(self):
        """Background thread loop reading frames."""
        while self.running:
            ret, frame = self.cap.read()
            if not self.running: break
            if not ret:
                # print("Camera read failed")
                pass
            with self.lock:
                self.ret = ret
                if ret:
                    self.frame = cv2.flip(frame, 1) # Mirror image
            time.sleep(0.01)
            
    def get_frame(self):
        """Retrieve the latest frame."""
        with self.lock:
            if self.ret and self.frame is not None:
                return self.frame.copy()
            return None
            
    def stop(self):
        """Stop the camera feed."""
        self.running = False
        if hasattr(self, 'thread'):
            self.thread.join()
        if self.cap.isOpened():
            self.cap.release()
