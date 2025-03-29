# -*- coding: utf-8 -*-
# @Time : 20-6-9 下午3:06
# @Author : zhuying
# @Company : Minivision
# @File : test.py
# @Software : PyCharm

import os
import cv2
import numpy as np
import warnings
import time

from custom_service.silent_antispoof.anti_spoof_predict import AntiSpoofPredict
from custom_service.silent_antispoof.generate_patches import CropImage
from custom_service.silent_antispoof.utility import parse_model_name
warnings.filterwarnings('ignore')


def test(frame, image_bbox, model_dir, device_id):
    model_test = AntiSpoofPredict(device_id) # gpuid : 0 , 1.
    image_cropper = CropImage()
    # image_bbox = model_test.get_bbox(frame)
    prediction = np.zeros((1, 3))
    test_speed = 0
    # sum the prediction from single model's result
    for model_name in os.listdir(model_dir):
        h_input, w_input, model_type, scale = parse_model_name(model_name)
        param = {
            "org_img": frame,
            "bbox": image_bbox,
            "scale": scale,
            "out_w": w_input,
            "out_h": h_input,
            "crop": True,
        }
        if scale is None:
            param["crop"] = False
        img = image_cropper.crop(**param)
        start = time.time()
        prediction += model_test.predict(img, os.path.join(model_dir, model_name))
        test_speed += time.time()-start

    # draw result of prediction
    label = np.argmax(prediction)
    value = prediction[0][label]/2
    if label == 1:
        result_text = "RealFace Score: {:.2f}".format(value)
        speed = "Prediction cost {:.2f} s".format(test_speed)
        is_spoof = False
        score = value
        duration = test_speed
        return (is_spoof, score, duration)

    else:
        result_text = "FakeFace Score: {:.2f}".format(value)
        speed = "Prediction cost {:.2f} s".format(test_speed)
        is_spoof = True
        score = value
        duration = test_speed
        return (is_spoof, score, duration)

    # cv2.rectangle(
    #     frame,
    #     (image_bbox[0], image_bbox[1]),
    #     (image_bbox[0] + image_bbox[2], image_bbox[1] + image_bbox[3]),
    #     color, 2)
    # cv2.putText(
    #     frame,
    #     result_text,
    #     (image_bbox[0], image_bbox[1] - 5),
    #     cv2.FONT_HERSHEY_COMPLEX, 0.5*frame.shape[0]/1024, color)

