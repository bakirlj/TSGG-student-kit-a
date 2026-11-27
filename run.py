#!/usr/bin/env python3
"""Camera checker: reads {"input": ..., "policy": ...} on stdin and writes one JSON answer on stdout.
Each check_* function only measures and returns numbers; the decision is made once, at the bottom."""
import json
import sys

import cv2
import numpy as np


def check_blur(gray, policy):

    # Resize picture. Make new widt and height. 640 x 360
    h, w = gray.shape # Gives us the current height and width
    new_w = policy.get("blur_resize_width", 640)
    new_h = round(h * new_w / w)
    small = cv2.resize(gray, (new_w, new_h), interpolation=cv2.INTER_AREA)
    # new w and h because resize takes width first, while shpae gives height first

    # Oval mask around the centre, where the bullseye is supposed to be
    mask = np.zeros((new_h, new_w), np.uint8) # makes all black picture same size as small
    center = (new_w // 2, new_h // 2)
    axes = (int(new_w * policy.get("blur_roi_width", 0.7) / 2),
            int(new_h * policy.get("blur_roi_height", 0.8) / 2))
    # drawing the mask
    cv2.ellipse(mask, center, axes, 0, 0, 360, 255, -1)
    inside = mask > 0 #True inside oval, false otherwise

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


def check_exposure(gray, policy):
    # Average brightness of the whole picture: 0 = black, 255 = white
    return {"mean_brightness": round(float(gray.mean()), 1)}


request = json.load(sys.stdin)
data, policy = request["input"], request["policy"]

# data["frame"] is a path such as "frames/blurry-1.png", relative to the root of your repo.
img = cv2.imread(data["frame"])
assert img is not None, "Couldn't find any image, check the file name and folder"

gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
blur = check_blur(gray, policy)
glare = check_glare(gray, policy)
exposure = check_exposure(gray, policy)

# Decide. Whole-picture faults first: a black picture has no edges, so it would also look "blurry";
# a white picture is one huge white patch, so it would also look like "glare".
# Then glare (a white patch can also make the picture look soft), then blur.
# Only the largest white patch decides glare: on real cameras the board's white segments are
# saturated too, so the total white share (bright_share) is high on normal pictures. It stays in args.
if exposure["mean_brightness"] <= policy["dark_max_mean"]:
    code = "dark"
elif exposure["mean_brightness"] >= policy["bright_min_mean"]:
    code = "bright"
elif glare["largest_blob_share"] >= policy["glare_min_blob_share"]:
    code = "glare"
elif blur["sharpness"] < policy["blur_min_sharpness"]:
    code = "blurry"
else:
    code = None

answer = {"code": code, "args": {**blur, **glare, **exposure}}

json.dump(answer, sys.stdout)
