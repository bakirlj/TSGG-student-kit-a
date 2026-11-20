#!/usr/bin/env python3
"""Starter: reads {"input": ..., "policy": ...} on stdin and writes one JSON answer on stdout.
Replace the body with your own program, in any language."""
import json
import sys

import cv2 


request = json.load(sys.stdin)
data, policy = request["input"], request["policy"]

img = cv2.imread(data["frame"])

assert img is not None, "Couldn't find any image, check the file name and folder"

gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())

# --- dark / bright: average brightness, 0 = black, 255 = white ---
mean_brightness = float(gray.mean())

# Order matters: a black picture has no edges, so it would also look "blurry";
# a white picture is one huge white patch, so it would also look like "glare".
# The whole-picture faults come first.
if mean_brightness <= policy["dark_max_mean"]:
    code = "dark"
elif mean_brightness >= policy["bright_min_mean"]:
    code = "bright"
elif sharpness < policy["blur_min_sharpness"]:
    code = "blurry"
else:
    code = None

answer = {"code": code, "args": {"sharpness": round(sharpness, 1),
                                 "mean_brightness": round(mean_brightness, 1)}}
json.dump(answer, sys.stdout)


