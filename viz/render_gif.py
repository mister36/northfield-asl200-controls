#!/usr/bin/env python3
"""Render a SIL trace to an animated GIF (and optionally MP4 via ffmpeg) for
PR comments and slides: rear view of the arm + lift trajectory with limits.

  python3 viz/render_gif.py out/asl200_electric_mack/normal.trace.json -o out/media/electric_normal.gif
  python3 viz/render_gif.py a.trace.json b.trace.json -o side_by_side.gif      # two panes, shared clock
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

BG, PANEL, LINE, FG, DIM = (14, 17, 23), (22, 27, 34), (42, 49, 64), (216, 222, 233), (123, 132, 150)
OK, BAD, WARN, ACC, VIO = (163, 190, 140), (191, 97, 106), (235, 203, 139), (136, 192, 208), (180, 142, 173)
STATE_COLORS = [(59, 66, 82), (94, 129, 172), (180, 142, 173), (163, 190, 140), (235, 203, 139), (136, 192, 208),
                (208, 135, 112), (129, 161, 193), (191, 97, 106)]
PANE_W, PANE_H = 520, 470


def font(size: int, bold: bool = False):
    for name in (["DejaVuSansMono-Bold.ttf"] if bold else []) + ["DejaVuSansMono.ttf"]:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


F11, F12, F14B = font(11), font(12), font(14, True)


class Pane:
    def __init__(self, trace: dict):
        self.tr = trace
        self.s = trace["signals"]
        p = trace["meta"]["params"]
        self.soft = p["controls"]["limits"]["lift_soft_max_deg"]
        self.hard = p["hardware"]["arm"]["lift_hard_max_deg"]
        self.peak = max(self.s["lift_deg"])
        self.n = len(self.s["t"])
        self.dt = trace["meta"].get("dt_s", 0.01)
        self.t_end = self.s["t"][-1]

    def draw(self, img: Image.Image, ox: int, t: float, t_end: float) -> None:
        d = ImageDraw.Draw(img)
        s, i = self.s, min(self.n - 1, int(round(t / self.dt)))
        m = self.tr["meta"]
        d.rectangle([ox, 0, ox + PANE_W - 1, PANE_H - 1], fill=PANEL, outline=LINE)
        verdict = self.tr.get("passed")
        head = f"{m['variant']} / {m['scenario']}"
        d.text((ox + 10, 8), head, fill=FG, font=F12)
        if verdict is not None:
            d.text((ox + PANE_W - 50, 8), "PASS" if verdict else "FAIL", fill=OK if verdict else BAD, font=F14B)
        # ---- scene (rear view)
        sx0, sy0, sw, sh = ox + 10, 28, PANE_W - 20, 250
        d.rectangle([sx0, sy0, sx0 + sw, sy0 + sh], fill=(11, 14, 19))
        sc, px0, gy = sw / 6.4, sx0 + sw * 0.45, sy0 + sh - 16

        def X(x):
            return px0 + x * sc

        def Y(y):
            return gy - y * sc
        d.rectangle([sx0, gy, sx0 + sw, sy0 + sh], fill=(28, 34, 44))
        d.rectangle([X(-2.5), Y(3.4), X(0), Y(0.9)], fill=(34, 43, 56), outline=(59, 70, 88), width=2)
        for wx in (-2.0, -0.4):
            d.ellipse([X(wx - 0.5), Y(1.0), X(wx + 0.5), Y(0.0)], fill=(26, 31, 39))
        d.text((X(-1.7), Y(2.3)), "HOPPER", fill=DIM, font=F11)
        lift, reach = s["lift_deg"][i], s["reach_mm"][i]
        px, py, L = 0.15, 2.6, 1.0 + reach / 1000.0
        r = (L + 0.35) * sc
        box = [X(px) - r, Y(py) - r, X(px) + r, Y(py) + r]

        def pil_ang(deg):  # boom angle phi=-45+lift (math, ccw) -> PIL (cw from +x)
            return -(-45 + deg)
        d.arc(box, pil_ang(self.hard), pil_ang(self.soft), fill=(150, 130, 90), width=6)
        d.arc(box, pil_ang(self.hard + 8), pil_ang(self.hard), fill=BAD, width=6)
        a = math.radians(-45 + lift)
        tx, ty = px + L * math.cos(a), py + L * math.sin(a)
        over = lift > self.soft + 0.05
        d.line([X(px), Y(py), X(px + math.cos(a)), Y(py + math.sin(a))], fill=(76, 86, 106), width=12)
        d.line([X(px + 0.6 * math.cos(a)), Y(py + 0.6 * math.sin(a)), X(tx), Y(ty)], fill=BAD if over else ACC, width=7)
        d.ellipse([X(px) - 5, Y(py) - 5, X(px) + 5, Y(py) + 5], fill=FG)
        grip = s["grip_bar"][i]
        held = grip > 40 and (s["state"][i] != 0 or lift > 3)
        cw, ch = 0.62 * sc, 1.05 * sc
        if held:
            c, sn = math.cos(-math.radians(lift)), math.sin(-math.radians(lift))
            cx, cy = X(tx), Y(ty)
            pts = []
            for qx, qy in ((0, -ch * 0.55), (cw, -ch * 0.55), (cw, ch * 0.45), (0, ch * 0.45)):
                pts.append((cx + qx * c - qy * sn, cy + qx * sn + qy * c))
            d.polygon(pts, fill=(79, 107, 58), outline=OK)
        else:
            cx = X(1.77 + px)
            d.rectangle([cx, gy - ch, cx + cw, gy], fill=(79, 107, 58), outline=OK)
        rr = 0.18 * sc
        d.ellipse([X(tx) - rr, Y(ty) - rr, X(tx) + rr, Y(ty) + rr], outline=OK if grip > 40 else DIM, width=4)
        d.text((sx0 + 8, sy0 + 6), f"lift {lift:6.1f} deg", fill=BAD if over else FG, font=F14B)
        d.text((sx0 + 8, sy0 + 24), f"reach {reach:5.0f} mm", fill=DIM, font=F12)
        st = m["state_names"][s["state"][i]]
        d.text((sx0 + sw - 8 - 9 * len(st), sy0 + 6), st, fill=BAD if st == "FAULT_STOP" else FG, font=F14B)
        if over:
            d.text((sx0 + 8, sy0 + 44), "SOFT LIMIT EXCEEDED", fill=BAD, font=F14B)
        if s["dtc_spn"][i]:
            d.text((sx0 + sw - 160, sy0 + 26), f"DTC SPN {s['dtc_spn'][i]}", fill=BAD, font=F14B)
        # ---- chart
        cx0, cy0, cw_, ch_ = ox + 44, 292, PANE_W - 56, 140
        lo, hi = -10.0, max(self.hard + 8, self.peak + 5)
        d.rectangle([cx0, cy0, cx0 + cw_, cy0 + ch_], outline=LINE)

        def cx(tt):
            return cx0 + tt / t_end * cw_

        def cy(v):
            return cy0 + ch_ - (v - lo) / (hi - lo) * ch_
        d.rectangle([cx0, cy(hi), cx0 + cw_, cy(self.hard)], fill=(60, 34, 40))
        d.rectangle([cx0, cy(self.hard), cx0 + cw_, cy(self.soft)], fill=(56, 52, 40))
        for v in (0, 50, 100, 150):
            d.text((ox + 10, cy(v) - 6), f"{v:>3}", fill=DIM, font=F11)
        step = max(1, self.n // 600)
        pts = [(cx(s["t"][k]), cy(s["lift_deg"][k])) for k in range(0, self.n, step)]
        d.line(pts, fill=ACC, width=2)
        for dt in self.tr.get("dtcs", []):
            d.line([cx(dt["t"]), cy0, cx(dt["t"]), cy0 + ch_], fill=BAD, width=1)
        if self.peak > self.soft + 0.5:
            k = s["lift_deg"].index(self.peak)
            d.text((cx(s["t"][k]) + 6, cy(self.peak) - 2), f"overshoot {self.peak:.1f}", fill=BAD, font=F11)
        d.line([cx(t), cy0, cx(t), cy0 + ch_], fill=FG, width=1)
        d.text((cx0 + 4, cy0 + 2), "lift [deg]", fill=DIM, font=F11)
        # state band
        by = cy0 + ch_ + 8
        k0 = 0
        for k in range(1, self.n + 1):
            if k == self.n or s["state"][k] != s["state"][k0]:
                d.rectangle([cx(s["t"][k0]), by, max(cx(s["t"][k - 1]), cx(s["t"][k0]) + 1), by + 10],
                            fill=STATE_COLORS[s["state"][k0]])
                k0 = k
        d.text((ox + 10, PANE_H - 20), f"t = {t:6.2f} s", fill=FG, font=F12)


def render(traces: list[dict], out: Path, fps: int = 12, speed: float = 1.0, mp4: bool = False) -> Path:
    panes = [Pane(tr) for tr in traces]
    t_end = max(p.t_end for p in panes)
    n_frames = int(t_end / speed * fps) + 1
    frames = []
    for f in range(n_frames):
        t = min(t_end, f * speed / fps)
        img = Image.new("RGB", (PANE_W * len(panes) + 10 * (len(panes) - 1), PANE_H), BG)
        for k, p in enumerate(panes):
            p.draw(img, k * (PANE_W + 10), t, t_end)
        frames.append(img)
    out.parent.mkdir(parents=True, exist_ok=True)
    pal = [fr.convert("P", palette=Image.Palette.ADAPTIVE, colors=64) for fr in frames]
    pal[0].save(out, save_all=True, append_images=pal[1:], duration=int(1000 / fps), loop=0, optimize=True)
    if mp4 and shutil.which("ffmpeg"):
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(out), "-movflags", "faststart", "-pix_fmt", "yuv420p",
                        "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2", str(out.with_suffix(".mp4"))], check=True)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("traces", type=Path, nargs="+")
    ap.add_argument("-o", "--out", type=Path, required=True)
    ap.add_argument("--fps", type=int, default=12)
    ap.add_argument("--speed", type=float, default=1.0, help="playback speed multiplier")
    ap.add_argument("--start", type=float, default=0.0, help="trim: start time [s]")
    ap.add_argument("--end", type=float, default=None, help="trim: end time [s]")
    ap.add_argument("--mp4", action="store_true")
    args = ap.parse_args()
    traces = [json.loads(p.read_text()) for p in args.traces[:2]]
    if args.start or args.end:
        for tr in traces:
            s = tr["signals"]
            k0 = int(args.start / 0.01)
            k1 = int(args.end / 0.01) + 1 if args.end else len(s["t"])
            for key in s:
                s[key] = s[key][k0:k1]
            s["t"] = [round(x - args.start, 3) for x in s["t"]]
            tr["dtcs"] = [{**d, "t": d["t"] - args.start} for d in tr.get("dtcs", []) if args.start <= d["t"] <= (args.end or 1e9)]
    print(render(traces, args.out, fps=args.fps, speed=args.speed, mp4=args.mp4))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
