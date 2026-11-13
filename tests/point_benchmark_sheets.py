#!/usr/bin/env python3
"""Assemble the fixed 8–16pt experiment with an untouched Qt control."""
import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("old", type=Path, help="75%% candidate output directory")
    parser.add_argument("nearest", type=Path, help="50%% candidate output directory")
    parser.add_argument("stock", type=Path, help="stock Qt output directory")
    parser.add_argument("output", type=Path)
    parser.add_argument("--label-font", type=Path, required=True)
    args = parser.parse_args()
    folders = [args.old, args.nearest, args.stock]
    datasets = [json.loads((p / "rows.json").read_text()) for p in folders]
    maps = [{r["id"]: r for r in rows} for rows in datasets]
    assert all(len(rows) == len(mapping) == 220 for rows, mapping in zip(datasets, maps))
    assert maps[0].keys() == maps[1].keys() == maps[2].keys()
    names = ["Noto Sans Regular", "Noto Serif Regular", "Lato Light", "Hack Regular"]
    names += [f"{family} {style}" for family in ("Noto Sans", "Noto Serif", "Hack")
              for style in ("Italic", "BoldItalic")]
    points = [8, 9, 10, 11, 11.25, 12, 13, 14, 15, 16]
    for key in maps[0]:
        peers = [m[key] for m in maps]
        for field in ("label", "font_sha256", "point_size", "base_px", "runs", "height", "logical_dpi", "scale"):
            assert all(r[field] == peers[0][field] for r in peers), (key, field)
        assert peers[0]["logical_dpi"] == 96 and peers[0]["scale"] == 1
    label = ImageFont.truetype(str(args.label_font), 12)
    head = ImageFont.truetype(str(args.label_font), 17)
    args.output.mkdir(parents=True, exist_ok=True)
    images, conditions, strips = [], [], []
    for name in names:
        group = sorted((r for r in datasets[1] if r["label"] == name), key=lambda r: r["point_size"])
        assert [r["point_size"] for r in group] == points
        for row in group:
            conditions.append({k: row[k] for k in ("id", "label", "point_size", "base_px", "logical_dpi", "scale", "cutoff", "font_sha256")}
                              | {"font_file": Path(row["font_path"]).name,
                                 "layout_sha256": hashlib.sha256(json.dumps(row["runs"], sort_keys=True, separators=(",", ":")).encode()).hexdigest()})
        for palette, bg, fg in (("light", 255, 0), ("dark", 0, 255)):
            height = 112 + sum(r["height"] + 27 for r in group)
            sheet = Image.new("RGB", (1560, height), (bg,) * 3)
            draw = ImageDraw.Draw(sheet)
            draw.text((12, 10), name.replace("BoldItalic", "Bold Italic") + " | horizontal-stroke fitting | actual 8-16pt", font=head, fill=(fg,) * 3)
            draw.text((12, 37), f'96 DPI / 100% scale. Candidates: floor 242, cutoff {group[0]["cutoff"]}, linear blend. Stock Qt control is untouched.', font=label, fill=(fg,) * 3)
            for col, title in enumerate(("75% stroke fitting + 242", "50% stroke fitting + 242", "Stock Qt (Fontreal disabled)")):
                draw.text((col * 520 + 12, 65), title, font=head, fill=(fg,) * 3)
            y, crops = 100, []
            for row in group:
                draw.text((12, y), f'{row["point_size"]:g}pt | Qt raster {row["base_px"]:g}px', font=label, fill=(fg,) * 3)
                y += 20
                for col, folder in enumerate(folders):
                    source = folder / f'{row["id"]}-{palette}.png'
                    im = Image.open(source).convert("RGB")
                    assert im.size == (620, row["height"])
                    box = ImageChops.difference(im, Image.new("RGB", im.size, (bg,) * 3)).getbbox()
                    assert box and box[2] < 500
                    cropped = im.crop((0, 0, 500, im.height))
                    x = col * 520 + 12
                    sheet.paste(cropped, (x, y))
                    crops.append((x, y, cropped))
                    strips.append(dict(id=row["id"], palette=palette, column=col, sha256=sha(source)))
                y += row["height"] + 7
            assert y <= height < 1000
            file = "stockqt-smallpt-" + name.lower().replace(" ", "-") + f"-{palette}.png"
            target = args.output / file
            sheet.save(target)
            with Image.open(target) as saved:
                for x, y, im in crops:
                    assert saved.crop((x, y, x + im.width, y + im.height)).tobytes() == im.tobytes()
            images.append(dict(file=file, font=name, palette=palette, sha256=sha(target)))
    assert len(conditions) == 100 and len(images) == 20 and len(strips) == 600
    record = dict(kind="75% versus 50% fitting with untouched stock Qt control", logical_dpi=96, display_scale=1,
                  columns=["75% auto-mono +242", "50% auto-mono +242", "Stock Qt; Fontreal disabled; no floor or manual blend"],
                  candidate_floor=242, candidate_cutoffs={"light": 128, "regular_and_heavier": 160},
                  compared_conditions=220, displayed_conditions=100, conditions=conditions, images=images, source_strips=strips,
                  renderer_source_sha256=sha(Path(__file__).with_name("point_benchmark_chart.cpp")),
                  assembler_sha256=sha(Path(__file__)), label_font_sha256=sha(args.label_font),
                  limits=["Stock Qt uses the capture desktop font configuration, not a universal KDE default",
                          "Static Latin fonts, 96 DPI, 100% scale only", "Neither candidate meets the full visual target"])
    (args.output / "stockqt-smallpt-captures.json").write_text(json.dumps(record, indent=2) + "\n")
    print("PASS 220 matched layouts, 100 displayed conditions, 600 exact source crops, 20 sheets")


if __name__ == "__main__":
    main()
