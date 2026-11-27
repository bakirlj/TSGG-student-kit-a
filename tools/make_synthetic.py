"""Make synthetic faulty pictures from real good ones (ok-*.png), so the checker has blur and glare examples.

Real blurry and glare pictures were hard to find in the field, so we add the fault ourselves with OpenCV.
Every output is listed in frames/synthetic.json with its source and exact parameters, so anyone can
see which pictures are synthetic and regenerate them. No randomness: same input -> same output.

Usage: python tools/make_synthetic.py           # every recipe
       python tools/make_synthetic.py glare     # only the glare pictures (others are left untouched)
"""
import json
import os
import sys

import cv2
import numpy as np

FRAMES = "frames"

# (fault, source picture, parameters). Add rows to make more pictures; numbering follows the order.
RECIPES = [
    # Out of focus: gaussian blur, sigma in pixels of the full 3840x2160 picture.
    ("blurry", "ok-1", {"method": "gaussian", "sigma": 6}),
    ("blurry", "ok-2", {"method": "gaussian", "sigma": 12}),
    # Camera shake: straight-line motion blur, length in pixels, angle in degrees.
    ("blurry", "ok-1", {"method": "motion", "length": 61, "angle": 0}),
    ("blurry", "ok-2", {"method": "motion", "length": 91, "angle": 35}),
    # Glare: bright hotspot; center and radius as fractions of the picture size, strength 1 = +255 at the core.
    ("glare", "ok-1", {"center": [0.50, 0.45], "radius": 0.12, "strength": 1.6}),
    ("glare", "ok-2", {"center": [0.30, 0.35], "radius": 0.08, "strength": 2.0}),
    ("glare", "ok-1", {"center": [0.70, 0.60], "radius": 0.18, "strength": 1.2}),
    ("glare", "ok-2", {"center": [0.55, 0.30], "radius": 0.10, "strength": 1.4, "streak": True}),
    # Harder glare: one patch of 2.5-4 % of the picture, so the total white stays under 5 %
    # (glare_max_bright_share) and only the largest-patch rule (glare_min_blob_share) catches it.
    ("glare", "ok-1", {"center": [0.50, 0.50], "radius": 0.06, "strength": 1.6}),   # medium spot, centre
    ("glare", "ok-2", {"center": [0.60, 0.45], "radius": 0.10, "strength": 0.9}),   # weak, soft spot
    ("glare", "ok-1", {"center": [0.35, 0.60], "radius": 0.05, "strength": 2.5}),   # small, very strong
    ("glare", "ok-2", {"center": [0.45, 0.50], "radius": 0.05, "strength": 1.5}),   # just above the limit
    ("glare", "ok-1", {"center": [0.80, 0.25], "radius": 0.055, "strength": 1.4}),  # near limit, corner
    # Exposure: every pixel becomes alpha * pixel + beta (clipped to 0-255).
    # Dark: lamp off / camera underexposed. Bright: camera overexposed / strong light on the whole board.
    ("dark", "ok-1", {"alpha": 0.15, "beta": 0}),     # nearly black
    ("dark", "ok-2", {"alpha": 0.30, "beta": 0}),     # very dim, closer to the limit
    ("bright", "ok-2", {"alpha": 4.5, "beta": 110}),  # nearly white
    ("bright", "ok-1", {"alpha": 3.8, "beta": 80}),   # washed out, closer to the limit
]


def blur(img, p):
    if p["method"] == "gaussian":
        return cv2.GaussianBlur(img, (0, 0), p["sigma"])
    n = p["length"]
    kernel = np.zeros((n, n), np.float32)
    kernel[n // 2, :] = 1.0
    rot = cv2.getRotationMatrix2D(((n - 1) / 2, (n - 1) / 2), p["angle"], 1.0)
    kernel = cv2.warpAffine(kernel, rot, (n, n))
    return cv2.filter2D(img, -1, kernel / kernel.sum())


def glare(img, p):
    h, w = img.shape[:2]
    cx, cy, r = p["center"][0] * w, p["center"][1] * h, p["radius"] * w
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    light = np.exp(-((x - cx) ** 2 + (y - cy) ** 2) / (2 * r * r))
    if p.get("streak"):  # thin horizontal flare through the hotspot
        streak = np.exp(-((y - cy) ** 2) / (2 * (0.06 * r) ** 2) - ((x - cx) ** 2) / (2 * (4 * r) ** 2))
        light = np.maximum(light, 0.8 * streak)
    out = img.astype(np.float32) + p["strength"] * 255.0 * light[..., None]
    return np.clip(out, 0, 255).astype(np.uint8)


def exposure(img, p):
    return cv2.convertScaleAbs(img, alpha=p["alpha"], beta=p["beta"])


MAKERS = {"blurry": blur, "glare": glare, "dark": exposure, "bright": exposure}


def main():
    only = set(sys.argv[1:])  # e.g. {"glare"}; empty means every fault
    counters, manifest = {}, []
    for fault, source, params in RECIPES:
        counters[fault] = counters.get(fault, 0) + 1
        name = f"{fault}-{counters[fault]}"
        manifest.append({"frame": f"{FRAMES}/{name}.png", "source": f"{FRAMES}/{source}.png",
                         "fault": fault, "params": params})
        if only and fault not in only:
            continue
        img = cv2.imread(os.path.join(FRAMES, source + ".png"), cv2.IMREAD_COLOR)
        if img is None:
            raise SystemExit(f"cannot read {FRAMES}/{source}.png")
        out = MAKERS[fault](img, params)
        cv2.imwrite(os.path.join(FRAMES, name + ".png"), out, [cv2.IMWRITE_PNG_COMPRESSION, 9])
        print(f"{name} <- {source} {params}")
    with open(os.path.join(FRAMES, "synthetic.json"), "w") as f:
        json.dump({"note": "Made by tools/make_synthetic.py from real good pictures; not from the field.",
                   "pictures": manifest}, f, indent=2)
        f.write("\n")


if __name__ == "__main__":
    main()
