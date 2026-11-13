import os
import sys
import shutil
import torch
from ultralytics import YOLO

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT_DIR)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

def train():
    device = 0 if torch.cuda.is_available() else "cpu"
    yaml_path = os.path.abspath("dataset/yolo_ice/dataset.yaml")
    if not os.path.exists(yaml_path):
        print(f"File YAML dataset tidak ditemukan: {yaml_path}")
        return

    base_weights = "weights/yolov8n.pt" if os.path.exists("weights/yolov8n.pt") else "yolov8n.pt"
    model = YOLO(base_weights)
    model.train(
        data=yaml_path,
        epochs=15,
        imgsz=640,
        batch=16,
        device=device,
        project="runs/train",
        name="ice_detector",
        exist_ok=True,
        verbose=True
    )

    os.makedirs("weights", exist_ok=True)
    candidates = [
        os.path.join("runs", "detect", "runs", "train", "ice_detector", "weights", "best.pt"),
        os.path.join("runs", "train", "ice_detector", "weights", "best.pt"),
        os.path.join("runs", "detect", "runs", "train", "ice_detector", "weights", "last.pt"),
        os.path.join("runs", "train", "ice_detector", "weights", "last.pt"),
    ]
    target_pt = os.path.join("weights", "yolo_ice_best.pt")
    for pt in candidates:
        if os.path.exists(pt):
            shutil.copy2(pt, target_pt)
            print(f"Training selesai. Model disimpan ke: {target_pt}")
            break

if __name__ == "__main__":
    train()
