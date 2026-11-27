#!/usr/bin/env python3
"""Camera checker. Reads {"input": {"frame": path}, "policy": {...}} on stdin, writes one JSON answer on stdout:
{"code": null | "dark" | "bright" | "glare" | "blurry", "args": {the numbers behind the verdict}}.

Checks run in order and the first fault found wins (see rules.md):
  R3 dark    - mean brightness below dark_max_mean
  R4 bright  - mean brightness above bright_min_mean
  R2 glare   - share of near-white pixels above glare_max_bright_share
  R1 blurry  - sharpness (variance of the Laplacian) below blur_min_sharpness
Pictures are scaled to work_width pixels wide first, so the numbers do not depend on camera resolution.
"""
import json
import sys

import cv2
import numpy as np


def measure(gray, policy):
    h, w = gray.shape
    width = policy["work_width"]
    small = cv2.resize(gray, (width, round(h * width / w)), interpolation=cv2.INTER_AREA)
    return {
        "mean_brightness": round(float(small.mean()), 1),
        "bright_share": round(float(np.mean(small >= policy["glare_pixel_level"])), 4),
        "sharpness": round(float(cv2.Laplacian(small, cv2.CV_64F).var()), 1),
    }


def verdict(m, policy):
    if m["mean_brightness"] < policy["dark_max_mean"]:
        return "dark"
    if m["mean_brightness"] > policy["bright_min_mean"]:
        return "bright"
    if m["bright_share"] > policy["glare_max_bright_share"]:
        return "glare"
    if m["sharpness"] < policy["blur_min_sharpness"]:
        return "blurry"
    return None


def check(frame, policy):
    gray = cv2.imread(frame, cv2.IMREAD_GRAYSCALE)
    if gray is None:
        return {"code": "unreadable", "args": {"frame": frame}}
    m = measure(gray, policy)
    return {"code": verdict(m, policy), "args": m}


if __name__ == "__main__":
    request = json.load(sys.stdin)
    json.dump(check(request["input"]["frame"], request["policy"]), sys.stdout)