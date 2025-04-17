# final-compre/app/processors/VideoCapture.py
import subprocess
import cv2
import numpy as np
from threading import Thread, Lock

class VideoStream(object):
    def __init__(self, src=0, width=960, height=540):
        """
        Initializes the VideoStream instance with FFmpeg or OpenCV as the backend.

        Args:
            src (str or int): Video source (e.g., RTSP link or webcam index).
            width (int): Width of the output frames.
            height (int): Height of the output frames.
            backend (str): Backend for video capture ("ffmpeg" or "opencv").
        """
        self.src = src
        self.width = width
        self.height = height
        self.frame_size = width * height * 3
        self.started = False
        self.read_lock = Lock()
        self.frame = None
        self.pipe = None
        self.cap = None

    def start(self):
        """
        Starts the video capture based on the selected backend.
        """
        if self.started:
            print("Stream already started!")
            return None
        self.started = True
        if self.src == "0":
            self.backend = "opencv"
            print("opening opencv")
            self._start_opencv()
        else:
            self.backend = "ffmpeg"
            self._start_ffmpeg()
        
        # else:
            # raise ValueError("Invalid backend. Choose 'ffmpeg' or 'opencv'.")

        self.thread = Thread(target=self._update, args=())
        self.thread.daemon = True
        self.thread.start()
        return self

    def _start_ffmpeg(self):
        """
        Launches the FFmpeg process to decode the video source.
        """
        command = [
            "ffmpeg",
            # "-hwaccel", "cuda",                # Enable CUDA hardware acceleration
            "-i", self.src,                      # Input video source
            "-vf", f"scale={self.width}:{self.height}",  # Resize video
            "-f", "rawvideo",                    # Output raw video format
            "-pix_fmt", "bgr24",                 # OpenCV-compatible pixel format
            "-an",                               # Disable audio
            "-sn",                               # Disable subtitles
            "-tune", "zerolatency",              # Optimize for low latency
            "-"                                  # Output to stdout
        ]
        print(f"FFmpeg started for {self.src}")
        self.pipe = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=10**8
        )

    def _start_opencv(self):
        """
        Initializes OpenCV VideoCapture.
        """
        self.cap = cv2.VideoCapture(int(self.src))
        print()
        if not self.cap.isOpened():
            raise RuntimeError(f"Failed to open video source {self.src} with OpenCV.")
        print(f"OpenCV started for device camera {self.src}")
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)

    def _update(self):
        """
        Continuously reads frames from the selected backend.
        """
        while self.started:
            if self.backend == "ffmpeg":
                raw_frame = self.pipe.stdout.read(self.frame_size)
                if len(raw_frame) != self.frame_size:
                    print("Failed to grab frame or end of stream")
                    self.started = False
                    break
                frame = np.frombuffer(raw_frame, np.uint8).reshape((self.height, self.width, 3))
            elif self.backend == "opencv":
                ret, frame = self.cap.read()
                if not ret:
                    print("Failed to grab frame from OpenCV.")
                    self.started = False
                    break
            else:
                frame = None
            
            with self.read_lock:
                self.frame = frame

    def read(self):
        """
        Returns the latest frame from the buffer.

        Returns:
            np.ndarray or None: The latest frame, or None if no frame is available.
        """
        with self.read_lock:
            if self.frame is not None:
                return self.frame.copy()
            else:
                return None

    def stop(self):
        """
        Stops the frame-reading thread and cleans up resources.
        """
        if not self.started:
            return
        self.started = False
        if self.thread.is_alive():
            self.thread.join()
        
        if self.backend == "ffmpeg" and self.pipe:
            try:
                self.pipe.terminate()
                self.pipe.wait(timeout=0.1)
            except subprocess.TimeoutExpired:
                print("FFmpeg did not terminate, killing the process.")
                self.pipe.kill()
            finally:
                self.pipe = None
                print("FFmpeg process closed.")
        elif self.backend == "opencv" and self.cap:
            self.cap.release()
            print("OpenCV capture closed.")

    def __del__(self):
        """
        Ensures resources are cleaned up when the instance is deleted.
        """
        self.stop()