# -*- coding: utf-8 -*-

from __future__ import division
import datetime
import numpy as np
# bool = np.bool
np.bool = bool
# import onnx
import onnxruntime
import os
import os.path as osp
import cv2
import sys
import tensorrt as trt
import pycuda.driver as cuda
import pycuda.autoinit  # Initializes CUDA driver
TRT_LOGGER = trt.Logger(trt.Logger.INFO)

def softmax(z):
    assert len(z.shape) == 2
    s = np.max(z, axis=1, keepdims=True)
    e_x = np.exp(z - s)
    return e_x / np.sum(e_x, axis=1, keepdims=True)

def distance2bbox(points, distance, max_shape=None):
    x1 = points[:, 0] - distance[:, 0]
    y1 = points[:, 1] - distance[:, 1]
    x2 = points[:, 0] + distance[:, 2]
    y2 = points[:, 1] + distance[:, 3]
    if max_shape is not None:
        # Using np.clip instead of .clamp for numpy arrays
        x1 = np.clip(x1, 0, max_shape[1])
        y1 = np.clip(y1, 0, max_shape[0])
        x2 = np.clip(x2, 0, max_shape[1])
        y2 = np.clip(y2, 0, max_shape[0])
    return np.stack([x1, y1, x2, y2], axis=-1)

def distance2kps(points, distance, max_shape=None):
    preds = []
    for i in range(0, distance.shape[1], 2):
        px = points[:, i % 2] + distance[:, i]
        py = points[:, i % 2 + 1] + distance[:, i + 1]
        if max_shape is not None:
            px = np.clip(px, 0, max_shape[1])
            py = np.clip(py, 0, max_shape[0])
        preds.append(px)
        preds.append(py)
    return np.stack(preds, axis=-1)

class RetinaFace:
    def __init__(self, model_file=None, session=None, use_onnx=True, trt_file=None):
        self.model_file = model_file
        self.session = session
        self.taskname = 'detection'
        self.use_onnx = use_onnx
        self.trt_file = trt_file
        if self.use_onnx:
            # Initialize using ONNX Runtime
            if self.session is None:
                print("hehe no onnx  here ")
                # assert self.model_file is not None and osp.exists(self.model_file)
                # self.session = onnxruntime.InferenceSession(self.model_file, None)
        else:
            # Use TRT mode: load TRT engine from the provided trt_file.
            assert trt_file is not None and osp.exists(trt_file), "TRT file must be provided"
            self.engine = self.load_trt_engine(trt_file)
            self.context = self.engine.create_execution_context()
            # Allocate buffers once for inference reuse
            self.inputs, self.outputs, self.bindings, self.stream = self.allocate_buffers(self.engine)

        self.center_cache = {}
        self.nms_thresh = 0.4
        self.det_thresh = 0.5
        self._init_vars()

    def _init_vars(self):
        if self.use_onnx:
            input_cfg = self.session.get_inputs()[0]
            input_shape = input_cfg.shape
            self.input_size = tuple(input_shape[2:4][::-1]) if not isinstance(input_shape[2], str) else None
            self.input_name = input_cfg.name
            outputs = self.session.get_outputs()
            self.output_names = [o.name for o in outputs]
            
            # Set feature map configuration based on ONNX outputs.
            num_outputs = len(outputs)
            if num_outputs == 6:
                self.fmc = 3
                self._feat_stride_fpn = [8, 16, 32]
                self._num_anchors = 2
            elif num_outputs == 9:
                self.fmc = 3
                self._feat_stride_fpn = [8, 16, 32]
                self._num_anchors = 2
                self.use_kps = True
            elif num_outputs == 10:
                self.fmc = 5
                self._feat_stride_fpn = [8, 16, 32, 64, 128]
                self._num_anchors = 1
            elif num_outputs == 15:
                self.fmc = 5
                self._feat_stride_fpn = [8, 16, 32, 64, 128]
                self._num_anchors = 1
                self.use_kps = True
        else:
            # For TRT mode, you need to set these manually.
            self.input_size = (640, 640)
            self.input_name = "input.1"  # This is a placeholder; adjust as needed.
            # Manually set the feature map configuration for your TRT model.
            # For example, for det_10g, these might be the values:
            self.fmc = 3
            self._feat_stride_fpn = [8, 16, 32]
            self._num_anchors = 2
            self.use_kps = True
            # If your TRT engine doesn't include output names, set them to None.
            self.output_names = ['448', '471', '494', '451', '474', '497', '454', '477', '500']
        self.input_mean = 127.5
        self.input_std = 128.0
        self._anchor_ratio = 1.0

    def prepare(self, ctx_id, **kwargs):
        if self.use_onnx and ctx_id < 0:
            self.session.set_providers(['CPUExecutionProvider'])
        nms_thresh = kwargs.get('nms_thresh', None)
        if nms_thresh is not None:
            self.nms_thresh = nms_thresh
        det_thresh = kwargs.get('det_thresh', None)
        if det_thresh is not None:
            self.det_thresh = det_thresh
        input_size = kwargs.get('input_size', None)
        if input_size is not None:
            if self.input_size is not None:
                print('Warning: det_size is already set, ignoring new value.')
            else:
                self.input_size = input_size

    def load_trt_engine(self, engine_file_path):
        """Load a serialized TensorRT engine from file."""
        with open(engine_file_path, "rb") as f, trt.Runtime(TRT_LOGGER) as runtime:
            engine = runtime.deserialize_cuda_engine(f.read())
        return engine

    def allocate_buffers(self, engine):
        """
        Allocate host and device buffers for TRT engine bindings.
        Returns lists for inputs, outputs, bindings, and a CUDA stream.
        """
        inputs = []
        outputs = []
        bindings = []
        stream = cuda.Stream()
        for binding in engine:
            binding_shape = engine.get_binding_shape(binding)
            # Multiply by engine.max_batch_size if using explicit batch mode
            size = trt.volume(binding_shape) * engine.max_batch_size
            dtype = trt.nptype(engine.get_binding_dtype(binding))
            # Allocate pagelocked host memory and device memory
            host_mem = cuda.pagelocked_empty(size, dtype)
            device_mem = cuda.mem_alloc(host_mem.nbytes)
            bindings.append(int(device_mem))
            if engine.binding_is_input(binding):
                inputs.append({'name': binding, 'host': host_mem, 'device': device_mem})
            else:
                outputs.append({'name': binding, 'host': host_mem, 'device': device_mem})
        return inputs, outputs, bindings, stream

    def do_inference(self, context, bindings, inputs, outputs, stream, batch_size=1):
        """Execute inference asynchronously and return output host buffers."""
        # Transfer input data to the GPU
        for inp in inputs:
            cuda.memcpy_htod_async(inp['device'], inp['host'], stream)
        # Run inference
        context.execute_async_v2(bindings=bindings, stream_handle=stream.handle)
        # Transfer predictions back from GPU
        for out in outputs:
            cuda.memcpy_dtoh_async(out['host'], out['device'], stream)
        # Wait for all operations to complete
        stream.synchronize()
        # Return outputs as numpy arrays
        return [out['host'] for out in outputs]

    def retinaface_inference_trt(self, blob):
        """
        Run inference using TensorRT.
        Preprocess input blob should be in the correct shape.
        """
        # Copy blob data to input buffer
        np.copyto(self.inputs[0]['host'], blob.ravel())
        # Reuse the persistent context created during initialization.
        trt_outputs = self.do_inference(self.context, self.bindings, self.inputs, self.outputs, self.stream)
        return trt_outputs

    def forward(self, img, threshold):
        scores_list = []
        bboxes_list = []
        kpss_list = []
        blob = cv2.dnn.blobFromImage(
            img, 1.0/self.input_std, self.input_size,
            (self.input_mean, self.input_mean, self.input_mean),
            swapRB=True
        )
        if self.use_onnx:
            net_outs = self.session.run(self.output_names, {self.input_name: blob})
        else:
            net_outs = self.retinaface_inference_trt(blob)
            print("TRT outputs:")
            for o in net_outs:
                print(o.shape)
        
        input_height = blob.shape[2]
        input_width = blob.shape[3]
        
        # Assume three stages corresponding to strides in self._feat_stride_fpn
        # and that TRT outputs are arranged in groups of 3 (scores, bbox, keypoints)
        num_stages = len(self._feat_stride_fpn)
        for stage in range(num_stages):
            stride = self._feat_stride_fpn[stage]
            # Expected feature map dimensions for this stage:
            H = input_height // stride
            W = input_width // stride
            # We have _num_anchors anchors per location
            N = H * W * self._num_anchors

            # For TRT, outputs are flat. They are arranged as:
            # net_outs[stage*3]     : scores, shape (N,)
            # net_outs[stage*3 + 1] : bbox predictions, shape (N*4,)
            # net_outs[stage*3 + 2] : keypoints predictions, shape (N*10,) if used
            scores = net_outs[stage*3].reshape((N, 1))
            bbox_preds = net_outs[stage*3 + 1].reshape((N, 4)) * stride
            if self.use_kps:
                kps_preds = net_outs[stage*3 + 2].reshape((N, 10)) * stride

            # Compute anchor centers (should be same as before)
            key = (H, W, stride)
            if key in self.center_cache:
                anchor_centers = self.center_cache[key]
            else:
                anchor_centers = np.stack(np.mgrid[:H, :W][::-1], axis=-1).astype(np.float32)
                # Multiply by stride and flatten to (H*W, 2)
                anchor_centers = (anchor_centers * stride).reshape((-1, 2))
                # If more than one anchor per location, duplicate accordingly
                if self._num_anchors > 1:
                    anchor_centers = np.stack([anchor_centers] * self._num_anchors, axis=1).reshape((-1, 2))
                self.center_cache[key] = anchor_centers

            # Now decode bounding boxes using the helper function
            bboxes = distance2bbox(anchor_centers, bbox_preds)
            pos_inds = np.where(scores >= threshold)[0]
            pos_scores = scores[pos_inds]
            pos_bboxes = bboxes[pos_inds]
            scores_list.append(pos_scores)
            bboxes_list.append(pos_bboxes)
            if self.use_kps:
                kpss = distance2kps(anchor_centers, kps_preds)
                kpss = kpss.reshape((kpss.shape[0], -1, 2))
                pos_kpss = kpss[pos_inds]
                kpss_list.append(pos_kpss)
        
        return scores_list, bboxes_list, kpss_list



    def detect(self, img, input_size=None, max_num=0, metric='default'):
        """
        Run detection on an image and return detections (bounding boxes with scores) and keypoints.
        The outputs are scaled to the original image coordinates.
        
        Args:
            img (np.ndarray): Original input image.
            input_size (tuple or None): The fixed input size (width, height) used during inference.
                                        If None, self.input_size is used.
            max_num (int): Maximum number of detections to return.
            metric (str): Metric for ranking detections if max_num > 0.
        
        Returns:
            det (np.ndarray): Detections of shape (N, 5) where each row is [x1, y1, x2, y2, score].
            kps (np.ndarray or None): Keypoints of shape (N, num_kps, 2), or None if not used.
        """
        # Use provided input_size or self.input_size (e.g., (640, 640))
        if input_size is None:
            assert self.input_size is not None, "Input size must be provided."
            input_size = self.input_size  # (width, height)
        else:
            self.input_size = input_size

        orig_h, orig_w = img.shape[:2]
        target_w, target_h = input_size  # typically (640, 640)

        # Compute resized dimensions preserving aspect ratio.
        aspect_ratio = orig_w / orig_h
        if (target_w / target_h) > aspect_ratio:
            new_h = target_h
            new_w = int(aspect_ratio * new_h)
        else:
            new_w = target_w
            new_h = int(new_w / aspect_ratio)

        # Compute scale factor to map detections back to original image.
        scale_x = orig_w / new_w
        scale_y = orig_h / new_h

        # Resize the image.
        resized_img = cv2.resize(img, (new_w, new_h))
        # Create a blank canvas of the fixed input size and place the resized image at top-left.
        det_img = np.zeros((target_h, target_w, 3), dtype=np.uint8)
        det_img[:new_h, :new_w, :] = resized_img

        # Run inference on the fixed-size detection image.
        scores_list, bboxes_list, kpss_list = self.forward(det_img, self.det_thresh)

        # The network outputs are in the resized coordinate space.
        # We need to scale bounding boxes and keypoints back to the original image.
        # In this example, since the resized image is at (0,0), we only multiply by scale factors.
        # Combine detections from all stages.
        scores = np.vstack(scores_list)
        scores_ravel = scores.ravel()
        order = scores_ravel.argsort()[::-1]
        bboxes = np.vstack(bboxes_list)
        
        # Scale bounding boxes:
        # Note: bboxes are assumed to be [x1, y1, x2, y2] in the resized image.
        bboxes[:, [0, 2]] *= scale_x
        bboxes[:, [1, 3]] *= scale_y

        if self.use_kps:
            kps = np.vstack(kpss_list)
            # Scale keypoints:
            kps[..., 0] *= scale_x
            kps[..., 1] *= scale_y
        else:
            kps = None

        # Arrange detections in descending score order.
        pre_det = np.hstack((bboxes, scores)).astype(np.float32, copy=False)
        pre_det = pre_det[order, :]
        keep = self.nms(pre_det)
        det = pre_det[keep, :]

        if self.use_kps:
            kps = kps[order, :, :][keep, :, :]

        # If a maximum number of detections is requested, pick the top ones.
        if max_num > 0 and det.shape[0] > max_num:
            area = (det[:, 2] - det[:, 0]) * (det[:, 3] - det[:, 1])
            img_center = (orig_h // 2, orig_w // 2)
            offsets = np.vstack([
                (det[:, 0] + det[:, 2]) / 2 - img_center[1],
                (det[:, 1] + det[:, 3]) / 2 - img_center[0]
            ])
            offset_dist_squared = np.sum(np.power(offsets, 2.0), 0)
            if metric == 'max':
                values = area
            else:
                values = area - offset_dist_squared * 2.0
            bindex = np.argsort(values)[::-1][:max_num]
            det = det[bindex, :]
            if kps is not None:
                kps = kps[bindex, :]

        return det, kps



    def nms(self, dets):
        thresh = self.nms_thresh
        x1 = dets[:, 0]
        y1 = dets[:, 1]
        x2 = dets[:, 2]
        y2 = dets[:, 3]
        scores = dets[:, 4]
        areas = (x2 - x1 + 1) * (y2 - y1 + 1)
        order = scores.argsort()[::-1]
        keep = []
        while order.size > 0:
            i = order[0]
            keep.append(i)
            xx1 = np.maximum(x1[i], x1[order[1:]])
            yy1 = np.maximum(y1[i], y1[order[1:]])
            xx2 = np.minimum(x2[i], x2[order[1:]])
            yy2 = np.minimum(y2[i], y2[order[1:]])
            w = np.maximum(0.0, xx2 - xx1 + 1)
            h = np.maximum(0.0, yy2 - yy1 + 1)
            inter = w * h
            ovr = inter / (areas[i] + areas[order[1:]] - inter)
            inds = np.where(ovr <= thresh)[0]
            order = order[inds + 1]
        return keep

# def get_retinaface(name, download=False, root='~/.insightface/models', **kwargs):
#     if not download:
#         assert os.path.exists(name)
#         return RetinaFace(name, use_onnx=True)
#     else:
#         from .model_store import get_model_file
#         _file = get_model_file("retinaface_%s" % name, root=root)
#         return RetinaFace(_file, use_onnx=True)
