import cv2
import numpy as np

class FaceDetectorYunet():
    def __init__(self, model_path='./face_detection_yunet_2023mar.onnx', img_size=(300, 300), threshold=0.5):
        self.model_path = model_path
        self.img_size = img_size
        self.fd = cv2.FaceDetectorYN_create(str(model_path), "", img_size, score_threshold=threshold)

    def scale_coords(self, image, prediction):
        ih, iw = image.shape[:2]
        rw, rh = self.img_size
        a = np.array([
            (prediction['x1'], prediction['y1']),
            (prediction['x1'] + prediction['x2'], prediction['y1'] + prediction['y2'])
        ])
        b = np.array([iw / rw, ih / rh])
        c = a * b
        prediction['img_width'] = iw
        prediction['img_height'] = ih
        prediction['x1'] = int(c[0, 0].round())
        prediction['x2'] = int(c[1, 0].round())
        prediction['y1'] = int(c[0, 1].round())
        prediction['y2'] = int(c[1, 1].round())
        prediction['face_width'] = (c[1, 0] - c[0, 0])
        prediction['face_height'] = (c[1, 1] - c[0, 1])
        prediction['area'] = prediction['face_width'] * prediction['face_height']
        prediction['pct_of_frame'] = prediction['area'] / (prediction['img_width'] * prediction['img_height'])
        return prediction

    def parse_predictions(self, image, faces):
        data = []
        for num, face in enumerate(list(faces)):
            x1, y1, x2, y2 = list(map(int, face[:4]))
            landmarks = list(map(int, face[4:len(face) - 1]))
            landmarks = np.array_split(landmarks, len(landmarks) / 2)
            positions = ['left_eye', 'right_eye', 'nose', 'right_mouth', 'left_mouth']
            landmarks = {positions[num]: x.tolist() for num, x in enumerate(landmarks)}
            confidence = face[-1]
            datum = {
                'x1': x1,
                'y1': y1,
                'x2': x2,
                'y2': y2,
                'face_num': num,
                'landmarks': landmarks,
                'confidence': confidence,
                'model': 'yunet'
            }
            d = self.scale_coords(image, datum)
            data.append(d)
        return data

    def detect(self, image):
        if isinstance(image, str):
            image = cv2.imread(str(image))
        img = cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)
        img = cv2.resize(img, self.img_size)
        self.fd.setInputSize(self.img_size)
        _, faces = self.fd.detect(img)
        if faces is None:
            return None
        else:
            predictions = self.parse_predictions(image, faces)
            return predictions
    
def convert_yunet_to_compreface(yunet_results):
    compreface_results = []

    for face in yunet_results:
        compreface_result = {
            "age": {
                "probability": None,  # Age is not available in yunet; can be set to None or a default
                "high": None,        # High age prediction
                "low": None          # Low age prediction
            },
            "gender": {
                "probability": None,  # Gender is not available in yunet
                "value": None         # Gender value
            },
            "mask": {
                "probability": None,  # Mask prediction is not available in yunet
                "value": None         # Mask value
            },
            "embedding": [],          # Yunet does not provide embeddings
            "box": {
                "probability": face.get("confidence", 0),  # Confidence becomes the probability
                "x_max": face["x2"],                      # Map bounding box coordinates
                "y_max": face["y2"],
                "x_min": face["x1"],
                "y_min": face["y1"]
            },
            "landmarks": [
                face["landmarks"].get("left_eye"),
                face["landmarks"].get("right_eye"),
                face["landmarks"].get("nose"),
                face["landmarks"].get("right_mouth"),
                face["landmarks"].get("left_mouth")
            ],
            "subjects": [],            # Yunet does not provide subject similarity data
            "execution_time": {
                "age": None,          # Yunet does not provide execution time details
                "gender": None,
                "detector": None,
                "calculator": None,
                "mask": None
            }
        }

        compreface_results.append(compreface_result)

    return compreface_results