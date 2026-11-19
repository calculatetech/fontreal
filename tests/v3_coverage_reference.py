#!/usr/bin/env python3
"""Regenerate the approved V3 tone and projection reference bytes with NumPy.

Run this with NumPy installed. Compare stdout with v3-coverage-test --dump.
The build and ordinary CTest run use frozen hashes and need no NumPy.

The scalar tone algorithms come from the approved core-bias, tapered lift, and
brightness studies. The projection comes from the accepted RGB stripe study
(source SHA-256 c2b5420658e2eb5fabb4bd3fe8df99b5b08a41383b9f2b16fa4ff53f3cbb2fa1).
The approval covered dark and light text on white and black, respectively.
These fixtures use synthetic sample triples and also test an independent
grayscale target, as supplied by the accepted thin-stroke treatment.
"""

import sys

import numpy as np

LEVELS = np.arange(256)
ENCODED = LEVELS / 255
LINEAR = np.where(ENCODED <= .04045, ENCODED / 12.92, ((ENCODED + .055) / 1.055) ** 2.4)
LUMA = np.array([.2126, .7152, .0722])
SAMPLES = (0, 1, 17, 52, 86, 125, 171, 199, 216, 251, 254, 255)


def srgb(values):
    return np.where(values <= .0031308, 12.92 * values, 1.055 * values ** (1 / 2.4) - .055)


def coverage(point_size, light):
    pixels = point_size * 96 / 72
    if light:
        full = np.interp(LEVELS, [0, 43, 85, 128, 170, 213, 255], [0, 95, 139, 174, 204, 231, 255])
        size = np.clip((pixels - 40 / 3) / 8, 0, 1)
        edge = .60 * size * np.clip((160 - LEVELS) / 96, 0, 1)
        transfer = LEVELS + (full - LEVELS) * (1 - edge)
    else:
        linear_ink = 255 * (1 - srgb(1 - ENCODED))
        transfer = linear_ink + (LEVELS - linear_ink) * (.20 + .60 * ENCODED)
    curve = np.rint(transfer).astype(np.uint8)
    lift = np.interp(pixels, [32 / 3, 40 / 3, 56 / 3, 64 / 3], [.30, .125, .125, .40])
    position = np.clip((LEVELS - int(curve[64])) / (int(curve[160]) - int(curve[64])), 0, 1)
    gate = position * position * (3 - 2 * position)
    contrast = np.rint(LEVELS + lift * gate * (255 - LEVELS)).astype(np.uint8)
    return contrast[curve]


def project(neutral, samples, light):
    gray = LINEAR[(neutral if light else 255 - neutral)][:, None]
    predicted = LINEAR[samples if light else 255 - samples]
    delta = (predicted - (predicted @ LUMA)[:, None]) * .90
    limit = np.ones_like(delta)
    np.divide(1 - gray, delta, out=limit, where=delta > 0)
    np.divide(-gray, delta, out=limit, where=delta < 0)
    rgb = gray + delta * np.minimum(1, limit.min(axis=1, keepdims=True))
    assert abs(rgb @ LUMA - gray[:, 0]).max() < 1e-7
    encoded = np.rint(255 * srgb(np.clip(rgb, 0, 1))).astype(np.uint8)
    assert abs(LINEAR[encoded] @ LUMA - gray[:, 0]).max() < .0045
    return encoded if light else 255 - encoded


def main():
    samples = np.array(np.meshgrid(SAMPLES, SAMPLES, SAMPLES, indexing="ij")).reshape(3, -1).T
    for points in (8, 10, 11, 12, 14, 16):
        for light in (False, True):
            curve = coverage(points, light)
            raw = samples[:, 1]
            for values in (curve, project(curve[raw], curve[samples], light),
                           project(curve[raw], curve[samples[:, ::-1]], light),
                           project(curve[255 - raw], curve[samples], light)):
                sys.stdout.buffer.write(values.tobytes())


if __name__ == "__main__":
    main()
