#!/usr/bin/env python3
"""Starter: reads {"input": ..., "policy": ...} on stdin and writes one JSON answer on stdout.
Replace the body with your own program, in any language."""
import json
import sys

import cv2 
import numpy as np


request = json.load(sys.stdin)
data, policy = request["input"], request["policy"]

img = cv2.imread(data["frame"])

assert img is not None, "Couldn't find any image, check the file name and folder"

gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
h, w = gray.shape

# Region of interest: the oval around the scoring area, as fractions of the picture (policy "roi")
# Only pixels inside it are measured. Without "roi" in the policy, the whole picture is used
roi_cfg = policy.get("roi")
if roi_cfg:
    roi = np.zeros((h, w), np.uint8)
    center = (round(roi_cfg["cx"] * w), round(roi_cfg["cy"] * h))
    axes = (round(roi_cfg["rx"] * w), round(roi_cfg["ry"] * h))
    cv2.ellipse(roi, center, axes, 0, 0, 360, 1, -1)  
    roi = roi.astype(bool)
else:
    roi = np.ones((h, w), bool)
roi_size = int(roi.sum())  

# Laplacian on the whole picture, then keep only the values inside the oval
# (blanking the outside first would turn the oval's border into a fake strong edge)
sharpness = float(cv2.Laplacian(gray, cv2.CV_64F)[roi].var())

white = (gray >= policy["glare_white_level"]) & roi  # white pixels inside the oval only
bright_share = float(white.sum() / roi_size)  # share of the oval, from 0 to 1

mask = white.astype(np.uint8) # 0/1 numbers for white pixels for OpenCV
n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
if n > 1:
    biggest = int(stats[1:, cv2.CC_STAT_AREA].max())
else:
    biggest = 0
largest_blob_share = biggest / roi_size


if largest_blob_share >= policy["glare_min_blob_share"] or bright_share > policy["glare_max_bright_share"]:
    # glare if either one is too high
    code = "glare"
elif sharpness < policy["blur_min_sharpness"]:
    code = "blurry"
else:
    code = None


# data["frame"] is a path such as "frames/blurry-1.png", relative to the root of your repo.
answer = {"code": code, "args": {"sharpness": round(sharpness, 1),
                                 "bright_share": round(bright_share, 4),
                                 "largest_blob_share": round(largest_blob_share,4)}}

json.dump(answer, sys.stdout)


