import os
import sys
import json
import time
import cv2

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT_DIR)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import config
from cloud_sync import cloud_sync

def setup_wizard():
    city_input = input("Masukkan Nama Kota Cabang [Default: Makassar]: ").strip() or "Makassar"
    suggested_code = city_input[:3].upper() + "-01"
    code_input = input(f"Masukkan Kode Unik Cabang [Default: {suggested_code}]: ").strip() or suggested_code
    default_vid = "videos/XVR_ch3_main_20261022200001_20261022203800.mp4"
    rtsp_input = input(f"Masukkan URL RTSP / Video [Default: {default_vid}]: ").strip() or default_vid

    profile = {
        "branch_city": city_input,
        "branch_code": code_input,
        "video_source": rtsp_input,
        "configured_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }

    os.makedirs("data", exist_ok=True)
    profile_path = "data/branch_profile.json"
    with open(profile_path, "w") as f:
        json.dump(profile, f, indent=2)

    print(f"Profil cabang disimpan ke {profile_path}")
    cap = cv2.VideoCapture(rtsp_input)
    if cap.isOpened():
        ret, frame = cap.read()
        if ret and frame is not None:
            fh, fw = frame.shape[:2]
            print(f"Kamera terhubung ({fw}x{fh} px)")
        cap.release()

if __name__ == "__main__":
    setup_wizard()
