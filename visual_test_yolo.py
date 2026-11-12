import cv2
import os
import glob
from ultralytics import YOLO

def test_visual():
    print("=" * 65)
    print("      PENGUJIAN VISUAL MODEL YOLO HASIL TRAINING")
    print("=" * 65)

    weights_path = "weights/yolo_ice_best.pt"
    if not os.path.exists(weights_path):
        print(f"File model tidak ditemukan: {weights_path}")
        return

    model = YOLO(weights_path)
    output_dir = "scratch/yolo_visual_eval"
    os.makedirs(output_dir, exist_ok=True)

    # Ambil sampel dari validation set
    val_images = sorted(glob.glob("dataset/yolo_ice/images/val/*.jpg"))
    if not val_images:
        val_images = sorted(glob.glob("dataset/extracted_frames/images/*.jpg"))

    test_samples = val_images[:10]  # Ambil 10 sampel beragam
    print(f"Menguji model pada {len(test_samples)} sampel gambar...")

    detection_summary = {"es_besar": 0, "es_kecil": 0, "pekerja": 0}

    for idx, img_path in enumerate(test_samples):
        frame = cv2.imread(img_path)
        if frame is None: continue

        results = model.predict(frame, conf=0.25, verbose=False)
        annotated_frame = results[0].plot()

        base_name = os.path.basename(img_path)
        save_path = os.path.join(output_dir, f"eval_{base_name}")
        cv2.imwrite(save_path, annotated_frame)

        boxes = results[0].boxes
        dets_in_img = []
        for b in boxes:
            c = int(b.cls[0].item())
            name = model.names.get(c, str(c))
            conf = float(b.conf[0].item())
            detection_summary[name] = detection_summary.get(name, 0) + 1
            dets_in_img.append(f"{name} ({conf:.2f})")

        print(f"  [{idx+1}/{len(test_samples)}] {base_name}: {len(boxes)} objek terdeteksi -> {', '.join(dets_in_img) if dets_in_img else 'Tidak ada'}")

    print("\n" + "=" * 65)
    print("RINGKASAN HASIL EVALUASI:")
    print(f"  Total Es Besar Terdeteksi : {detection_summary.get('es_besar', 0)}")
    print(f"  Total Es Kecil Terdeteksi : {detection_summary.get('es_kecil', 0)}")
    print(f"  Total Pekerja Terdeteksi  : {detection_summary.get('pekerja', 0)}")
    print(f"\nGambar hasil deteksi tersimpan di folder: {output_dir}")
    print("=" * 65)

if __name__ == "__main__":
    test_visual()

