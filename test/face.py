import cv2
import numpy as np
import pandas as pd

from huggingface_hub import hf_hub_download
from ultralytics import YOLO
from insightface.app import FaceAnalysis


model_path = hf_hub_download(repo_id="AdamCodd/YOLOv11n-face-detection", filename="model.pt") # download
yolo = YOLO(model_path) #. load `YOLO v11` model (_as face detector_)

recognizer = FaceAnalysis(name='buffalo_l') #. load `buffalo_l` model (_as face recognizer_)
recognizer.prepare(ctx_id=0, det_size=(640, 640)) # config

def recognize(img_path = "screen.png"): #. $\lambda.$ recognize
    img = cv2.imread(img_path) #.1 load input image 🖼️
    results = yolo.predict(img_path, save=False) #.1 detect 🔎 bound boxes ☐ of all faces 👨🏻 in _the image_ 🖼️ (with `YOLO` model)
    r = results[0]

    for box in r.boxes: #. iterate ♻ _bound boxes_ ☐ of faces 👨🏻
        x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
        conf = box.conf[0].item()
        face_crop = img[y1:y2, x1:x2] #.1 crop image 🖼️ on bounding box ☐

        # InsightFace can process this crop directly (bbox alignment mode) It will resize to 112x112 internally
        faces = recognizer.get(face_crop) #. recognize faces 👨🏻 in the _crop_ ☐🖼️

        if len(faces) == 0:
            print(f"YOLO found a face (conf={conf:.2f}) but InsightFace couldn't process the crop")
        else:
            face = faces[0] #. $F_0$ $\gets$ first recognized face
            embedding = face.normed_embedding  # 512-dim L2-normalized vector #.1 `embedding` $\gets$ embedding of the $F_0$
