# from insightface.app import FaceAnalysis    
# from app import FaceAnalysis    
from pathlib import Path
from model_zoo import get_model

# Define model paths.
INSIGHTFACE_ROOT = Path('~/.insightface').expanduser()
INSIGHT_MODELS = INSIGHTFACE_ROOT / "models"
model_zoo = ['buffalo_l', 'buffalo_m', 'buffalo_s']
model_pack_name = model_zoo[0]
IMAGE_DIR = Path('images')
image_file = IMAGE_DIR / "4people.jpg"
# Paths for TRT and ONNX files.
trt_file = INSIGHT_MODELS / model_pack_name / "det_10g.trt"
onnx_file = INSIGHT_MODELS / model_pack_name / "det_10g.onnx"

def draw_detections(img, dets, kps=None):
    """
    Draw bounding boxes and keypoints on the image.
    
    Args:
        img (np.ndarray): Input image.
        dets (np.ndarray): Detection boxes of shape (N, 5) where each row is [x1, y1, x2, y2, score].
        kps (np.ndarray or None): Keypoints of shape (N, num_keypoints, 2) if available.
    
    Returns:
        np.ndarray: Image with drawn detections.
    """
    # Make a copy of the image to draw on.
    img_drawn = img.copy()
    
    for i, det in enumerate(dets):
        x1, y1, x2, y2, score = det
        # Draw the bounding box.
        cv2.rectangle(img_drawn, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
        # Optionally, draw the detection score.
        cv2.putText(img_drawn, f"{score:.2f}", (int(x1), int(y1)-5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        # If keypoints are provided, draw each one.
        if kps is not None:
            for kp in kps[i]:
                cv2.circle(img_drawn, (int(kp[0]), int(kp[1])), 2, (0, 0, 255), -1)
    return img_drawn

# Load the detection model using get_model.
analy_app = get_model(str(model_pack_name), trt_file=str(trt_file))
if analy_app is None:
    raise RuntimeError("Failed to load detection model.")

# Prepare the model.
analy_app.prepare(ctx_id=0, det_size=(640, 640))

def detect_faces(img):
    faces = analy_app.get(img, max_num=0)
    return faces

if __name__ == '__main__':
    import cv2
    img = cv2.imread(image_file)  # Replace with a valid image file.
    dets, kps = analy_app.detect(img)
    print("Detection results:", dets)
    print("Detection kps:", kps)
    img_with_detections = draw_detections(img, dets, kps)
    # Display the image.
    cv2.imshow("Detections", img_with_detections)
    cv2.waitKey(0)
    # cv2.destroyAllWindows()