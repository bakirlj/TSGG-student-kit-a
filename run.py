#!/usr/bin/env python3
"""Camera checker: reads {"input": ..., "policy": ...} on stdin and writes one JSON answer on stdout.
Each check_* function only measures and returns numbers; the decision is made once, at the bottom."""
import json
import sys

import cv2
import numpy as np


def make_roi(h, w, policy):
    """Region of interest: the oval around the scoring area, as fractions of the picture (policy "roi").
    Returns a True/False grid of size h x w: True inside the oval. Shared by every check,
    so they all look at the same part of the board. Without "roi" in the policy, the whole picture is used."""
    roi_cfg = policy.get("roi")
    if not roi_cfg:
        return np.ones((h, w), bool)
    roi = np.zeros((h, w), np.uint8)
    center = (round(roi_cfg["cx"] * w), round(roi_cfg["cy"] * h))
    axes = (round(roi_cfg["rx"] * w), round(roi_cfg["ry"] * h))
    cv2.ellipse(roi, center, axes, 0, 0, 360, 1, -1)
    return roi.astype(bool)


def check_blur(gray, policy):

    # Resize picture. Make new widt and height. 640 x 360
    h, w = gray.shape # Gives us the current height and width
    new_w = policy.get("blur_resize_width", 640)
    new_h = round(h * new_w / w)
    small = cv2.resize(gray, (new_w, new_h), interpolation=cv2.INTER_AREA)
    # new w and h because resize takes width first, while shpae gives height first

    # Oval mask around the scoring area (same oval as glare), made at the small size
    inside = make_roi(new_h, new_w, policy) #True inside oval, false otherwise

    # the brightness that 1% of the pixels are darker than, and
    # the brightness that 99% are darker than
    lo, hi = np.percentile(small[inside], [1, 99])
    stretched = (small.astype(np.float64) - lo) * (255.0 / max(hi - lo, 1))
    stretched = np.clip(stretched, 0, 255)

    lap = cv2.Laplacian(stretched, cv2.CV_64F)
    sharpness = float(lap[inside].var())

    # We compute the Laplacian on the whole picture then cut out the oval
    # Reason being if we cut and then measure, the cut would be super
    # sharp between the edge and the cut. So it would give false information
    return {"sharpness": round(sharpness, 1)}


def check_glare(gray, policy):
    h, w = gray.shape
    # Only pixels inside the oval are measured
    roi = make_roi(h, w, policy)
    roi_size = int(roi.sum())

    white = (gray >= policy["glare_white_level"]) & roi  # white pixels inside the oval only
    bright_share = float(white.sum() / roi_size)  # share of the oval, from 0 to 1

    mask = white.astype(np.uint8) # 0/1 numbers for white pixels for OpenCV
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    if n > 1:
        biggest = int(stats[1:, cv2.CC_STAT_AREA].max())
    else:
        biggest = 0
    largest_blob_share = biggest / roi_size

    return {"bright_share": round(bright_share, 4),
            "largest_blob_share": round(largest_blob_share, 4)}


request = json.load(sys.stdin)
data, policy = request["input"], request["policy"]

# data["frame"] is a path such as "frames/blurry-1.png", relative to the root of your repo.
img = cv2.imread(data["frame"])
assert img is not None, "Couldn't find any image, check the file name and folder"

gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
blur = check_blur(gray, policy)
glare = check_glare(gray, policy)

# Decide: glare first (a white patch can also make the picture look soft), then blur.
# Only the largest white patch decides glare: on real cameras the board's white segments are
# saturated too, so the total white share (bright_share) is high on normal pictures. It stays in args.
if glare["largest_blob_share"] >= policy["glare_min_blob_share"]:
    code = "glare"
elif blur["sharpness"] < policy["blur_min_sharpness"]:
    code = "blurry"
else:
    code = None

# Each check's numbers stay under its own name, so two checks can never overwrite each other's keys
answer = {"code": code, "args": {"blur": blur, "glare": glare}}

json.dump(answer, sys.stdout)
