"""Run the checker (run.py) on chosen pictures with policy.json and print each answer.

Usage, from the repo root:
    python tools/check_frames.py glare        # every frames/glare-*.png
    python tools/check_frames.py ok blurry    # several groups
    python tools/check_frames.py              # every picture in frames/

No pass/fail here (that is bb conform's job): it shows the numbers, for tuning thresholds.
"""
import glob
import json
import os
import subprocess
import sys

with open("policy.json", encoding="utf-8") as f:
    policy = json.load(f)

prefixes = sys.argv[1:] or [""]
frames = sorted({p.replace("\\", "/") for pre in prefixes for p in glob.glob(f"frames/{pre}*.png")})
if not frames:
    sys.exit(f"no pictures in frames/ starting with {prefixes}")

for frame in frames:
    request = json.dumps({"input": {"frame": frame}, "policy": policy})
    result = subprocess.run([sys.executable, "run.py"], input=request, capture_output=True, text=True)
    if result.returncode != 0:
        last = (result.stderr.strip().splitlines() or ["(no error text)"])[-1]
        print(f"{os.path.basename(frame):22} CRASH: {last}")
    else:
        print(f"{os.path.basename(frame):22} {result.stdout.strip()}")
