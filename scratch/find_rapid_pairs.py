import sys
sys.path.append(r"c:\Users\alver\OneDrive\Documents\Projects\camera")
import cv2, config

# Let's inspect all 62 counts from gt_audit/events.txt
# and check which ones are genuine bags and what their timestamps are!
with open("scratch/gt_audit/events.txt") as f:
    lines = [l.strip() for l in f if l.strip()]

events = []
for l in lines:
    parts = l.split("|")
    c_num = int(parts[0].replace("Count", "").strip())
    f_num = int(parts[1].split("(")[0].replace("Frame", "").strip())
    size = parts[2].strip()
    area = float(parts[3].replace("Area:", "").replace("px", "").strip())
    events.append((c_num, f_num, size, area))

print(f"Total events recorded: {len(events)}")
for i in range(len(events) - 1):
    c1, f1, s1, a1 = events[i]
    c2, f2, s2, a2 = events[i+1]
    df = f2 - f1
    dt_sec = df / 10.0
    if dt_sec < 4.0:
        print(f"Rapid count pair: Count {c1} (F:{f1}) -> Count {c2} (F:{f2}) | diff={df} frames ({dt_sec:.1f}s) | areas: {a1:.0f}, {a2:.0f}")

