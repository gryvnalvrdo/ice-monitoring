import os
import shutil
from ultralytics import YOLO
import torch

def train():
    print("=" * 60)
    print("      TRAINING MODEL YOLOv8 UNTUK DETEKSI ES KRISTAL")
    print("=" * 60)
    device = 0 if torch.cuda.is_available() else "cpu"
    print(f"Menggunakan Device: {device} ({torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU'})")

    yaml_path = os.path.abspath("dataset/yolo_ice/dataset.yaml")
    if not os.path.exists(yaml_path):
        print(f"File YAML dataset tidak ditemukan: {yaml_path}")
        return

    # Inisialisasi dari yolov8n base
    model = YOLO("yolov8n.pt")

    # Latih model selama 15 epoch
    results = model.train(
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

    # Copy best weights ke folder weights/
    os.makedirs("weights", exist_ok=True)
    best_pt = os.path.join("runs", "train", "ice_detector", "weights", "best.pt")
    target_pt = os.path.join("weights", "yolo_ice_best.pt")

    if os.path.exists(best_pt):
        shutil.copy2(best_pt, target_pt)
        print(f"\nTraining Sukses! Model terbaik disimpan ke: {target_pt}")
    else:
        last_pt = os.path.join("runs", "train", "ice_detector", "weights", "last.pt")
        if os.path.exists(last_pt):
            shutil.copy2(last_pt, target_pt)
            print(f"\nTraining Selesai! Model disimpan ke: {target_pt}")

if __name__ == "__main__":
    train()

