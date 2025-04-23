# config/state.py
import threading

frame_lock = threading.Lock()
vs_lock    = threading.Lock()
model_lock = threading.Lock()
feed_lock  = threading.Lock()
