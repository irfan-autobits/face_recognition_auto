# final-compre/app/processors/frame_draw.py
import cv2
import numpy as np
from config.Paths import FACE_REC_TH
np.int = int

def format_subject(subject):
    # Split the subject by whitespace
    parts = subject.split()
    # Check that we have at least two parts
    if len(parts) >= 2:
        first_part = parts[0]
        # Get the first letter of the second part
        second_initial = parts[1][0]
        return f"{first_part}_{second_initial}"
    # If there's only one part, return it unchanged (or handle as needed)
    return subject
    
def Drawing_on_frame(frame, box, landmarks, landmark_3d_68, subject, color, probability, spoof_res, distance, draw_lan=False):
    """
    Function to process the frame before sending it to the client.
    You can add your own frame processing logic here (e.g., recognition, drawing).
    """
    if spoof_res["is_spoof"]:
        # print("❌ Spoof Detected! Face Rejected.")
        color = (0, 0, 255)
        cv2.rectangle(frame, (box['x_min'], box['y_min']), 
                            (box['x_max'], box['y_max']), color, 1)    
        spoof_text = f"spoof: {spoof_res['spoof_score']:.2f}"    
        cv2.putText(frame, spoof_text, (box['x_min']+5, box['y_min'] - 15),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
    else:
        # print("✅ Real face! Face Accepted.")
        # frame = np.zeros_like(frame)  # Black background
        # frame[:] = (255, 255, 255)  # Uncomment for White background
        cv2.rectangle(frame, (box['x_min'], box['y_min']), 
                            (box['x_max'], box['y_max']), color, 1)
        spoof_text = f"Real: {spoof_res['spoof_score']:.2f}"    
        # cv2.putText(frame, spoof_text, (box['x_min']+5, box['y_min'] - 15),
        #                 cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
        # cv2.putText(frame, str(int(probability * 100)), (box['x_min']+5, box['y_min'] - 15),
        #                 cv2.FONT_HERSHEY_SIMPLEX, 0.3, color, 1)
        frmt_sim = f"{distance:.3f}"
        subject = format_subject(subject)
        sub_sim = f"{frmt_sim}_{subject}"  
        cv2.putText(frame, sub_sim, (box['x_min']+5, box['y_min'] - 15),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
        if draw_lan:
            # Draw landmarks
            colors = [(0, 255, 0), (0, 0, 255), (0, 0, 255), (0, 255, 0), (0, 0, 255)]
            # colors = [(0, 0, 255), (0, 255, 255), (255, 0, 255), (0, 255, 0), (255, 0, 0)]
            for ((x,y), color) in zip(landmarks, colors):
                # print(f"land is {(int(x), int(y))}, type {type((int(x), int(y)))}")
                cv2.circle(frame, (int(x), int(y)), 2, color, -1)
            # print(f"landmarl {landmark_3d_68}")
            lmk = np.round(landmark_3d_68).astype(np.int)
            for l in range(lmk.shape[0]):
                color = (255, 0, 0)
                cv2.circle(frame, (lmk[l][0], lmk[l][1]), 1, color,
                            2)
    return frame

