import os
import cv2
import glob
import shutil
import random
from ultralytics import YOLO
import config
from detector import PackageDetector

def generate_yolo_dataset(extracted_dir="dataset/extracted_frames/images",
                          output_yolo_dir="dataset/yolo_ice"):
    print("=" * 65)
    print("   MEMBANGUN DATASET YOLO DARI FRAME VIDEO EKSISTING")
    print("=" * 65)

    images = sorted(glob.glob(os.path.join(extracted_dir, "*.jpg")))
    if not images:
        print(f"Tidak ada gambar di {extracted_dir}")
        return

    train_img_dir = os.path.join(output_yolo_dir, "images", "train")
    val_img_dir = os.path.join(output_yolo_dir, "images", "val")
    train_lbl_dir = os.path.join(output_yolo_dir, "labels", "train")
    val_lbl_dir = os.path.join(output_yolo_dir, "labels", "val")

    for d in [train_img_dir, val_img_dir, train_lbl_dir, val_lbl_dir]:
        os.makedirs(d, exist_ok=True)

    base_yolo = YOLO("yolov8n.pt")
    detector = PackageDetector()

    random.seed(42)
    random.shuffle(images)

    total_images = len(images)
    train_split = int(total_images * 0.8)

    labels_created = 0

    print(f"Total gambar: {total_images} (Train: {train_split}, Val: {total_images - train_split})")
    print("Membuat anotasi label otomatis...")

    for idx, img_path in enumerate(images):
        frame = cv2.imread(img_path)
        if frame is None:
            continue
        fh, fw = frame.shape[:2]

        person_boxes = []
        yolo_res = base_yolo.predict(frame, classes=[0], conf=0.35, verbose=False)
        for r in yolo_res:
            for b in r.boxes:
                xyxy = b.xyxy[0].cpu().numpy()
                x1, y1, x2, y2 = xyxy
                xc = ((x1 + x2) / 2) / fw
                yc = ((y1 + y2) / 2) / fh
                w = (x2 - x1) / fw
                h = (y2 - y1) / fh
                person_boxes.append((2, xc, yc, w, h))

        ice_boxes = []
        proc_frame, events = detector.process_frame(frame)
        for obj in detector.tracker.objects.values():
            bx, by, bw, bh = obj['curr_bbox']

            abs_x = bx + config.ROI[0]
            abs_y = by + config.ROI[1]

            is_large = (bh >= 115 or obj.get('max_area', 0) >= config.SIZE_THRESHOLD_AREA)
            cls_id = 0 if is_large else 1

            xc = (abs_x + bw / 2) / fw
            yc = (abs_y + bh / 2) / fh
            nw = bw / fw
            nh = bh / fh
            ice_boxes.append((cls_id, xc, yc, nw, nh))

        all_boxes = person_boxes + ice_boxes

        is_train = (idx < train_split)
        target_img_dir = train_img_dir if is_train else val_img_dir
        target_lbl_dir = train_lbl_dir if is_train else val_lbl_dir

        base_name = os.path.basename(img_path)
        dest_img_path = os.path.join(target_img_dir, base_name)
        shutil.copy2(img_path, dest_img_path)

        lbl_name = os.path.splitext(base_name)[0] + ".txt"
        dest_lbl_path = os.path.join(target_lbl_dir, lbl_name)

        with open(dest_lbl_path, "w") as lf:
            for b in all_boxes:
                lf.write(f"{b[0]} {b[1]:.6f} {b[2]:.6f} {b[3]:.6f} {b[4]:.6f}\n")

        if len(all_boxes) > 0:
            labels_created += 1

        if (idx + 1) % 50 == 0:
            print(f"  Diproses {idx + 1}/{total_images} gambar...")

    abs_path = os.path.abspath(output_yolo_dir).replace("\\", "/")
    yaml_content = f"""path: {abs_path}
train: images/train
val: images/val

names:
  0: es_besar
  1: es_kecil
  2: pekerja
"""
    yaml_path = os.path.join(output_yolo_dir, "dataset.yaml")
    with open(yaml_path, "w") as yf:
        yf.write(yaml_content)

    print("=" * 65)
    print(f"Dataset YOLO siap dibuat!")
    print(f"File YAML : {yaml_path}")
    print(f"Total file: {total_images} gambar, {labels_created} gambar ber-label")
    print("=" * 65)
    return yaml_path

if __name__ == "__main__":
    generate_yolo_dataset()
