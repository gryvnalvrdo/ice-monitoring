"""
Export Demo Video Deteksi Es Kristal (Pure YOLO Deep Learning)
"""
import sys
from export_yolo_demo import export_yolo_demo

if __name__ == "__main__":
    out_name = sys.argv[1] if len(sys.argv) > 1 else "demo_yolo_pure.mp4"
    duration = int(sys.argv[2]) if len(sys.argv) > 2 else 60
    export_yolo_demo(output_video=out_name, duration_sec=duration)
