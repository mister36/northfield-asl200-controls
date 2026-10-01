"""Trajectory plots for one SIL trace (commanded vs actual, limits, faults)."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

BG = "#11151c"
FG = "#d8dee9"
GRID = "#2a3140"
STATE_COLORS = ["#3b4252", "#5e81ac", "#b48ead", "#a3be8c", "#ebcb8b", "#88c0d0", "#d08770", "#81a1c1", "#bf616a"]


def plot_trace(trace: dict, path: Path) -> Path:
    sig = trace["signals"]
    meta = trace["meta"]
    p = meta["params"]
    lim = p["controls"]["limits"]
    hw = p["hardware"]["arm"]
    t = sig["t"]
    fs = p["controls"]["motion"]["lift_cmd_full_scale_dps"]

    plt.rcParams.update({"font.family": "monospace", "font.size": 9})
    fig, axes = plt.subplots(4, 1, figsize=(11, 8.5), sharex=True,
                             gridspec_kw={"height_ratios": [3, 1.6, 1.2, 0.5]}, facecolor=BG)
    for ax in axes:
        ax.set_facecolor(BG)
        ax.tick_params(colors=FG)
        for s in ax.spines.values():
            s.set_color(GRID)
        ax.grid(color=GRID, lw=0.5)
        ax.yaxis.label.set_color(FG)

    ax = axes[0]
    ax.axhspan(lim["lift_soft_max_deg"], hw["lift_hard_max_deg"], color="#ebcb8b", alpha=0.12)
    ax.axhspan(hw["lift_hard_max_deg"], hw["lift_hard_max_deg"] + 8, color="#bf616a", alpha=0.18)
    ax.axhline(lim["lift_soft_max_deg"], color="#ebcb8b", lw=1, ls="--", label=f"soft limit {lim['lift_soft_max_deg']:.0f} deg")
    ax.axhline(hw["lift_hard_max_deg"], color="#bf616a", lw=1, ls=":", label=f"hard stop {hw['lift_hard_max_deg']:.0f} deg")
    cmd_int = [0.0]
    for i in range(1, len(t)):
        cmd_int.append(cmd_int[-1] + sig["lift_cmd_pct"][i - 1] / 100.0 * fs * (t[i] - t[i - 1]))
    ax.plot(t, sig["lift_deg"], color="#88c0d0", lw=1.8, label="lift actual (deg)")
    ax.plot(t, sig["ctrl_lift_deg"], color="#81a1c1", lw=0.8, ls="--", alpha=0.8, label="lift measured by ECU (deg)")
    ax.set_ylabel("lift [deg]")
    peak = max(sig["lift_deg"])
    if peak > lim["lift_soft_max_deg"] + 0.5:
        i = sig["lift_deg"].index(peak)
        ax.plot([t[i]], [peak], "v", color="#bf616a", ms=10)
        ax.annotate(f"OVERSHOOT {peak:.1f} deg", (t[i], peak), xytext=(8, 8), textcoords="offset points", color="#bf616a",
                    fontweight="bold")
    for d in trace["dtcs"]:
        for a in axes[:3]:
            a.axvline(d["t"], color="#bf616a", lw=1.2)
        axes[0].annotate(f"DTC SPN {d['spn']} FMI {d['fmi']}", (d["t"], axes[0].get_ylim()[1]), xytext=(4, -14),
                         textcoords="offset points", color="#bf616a", fontweight="bold")
    ax.legend(loc="upper right", facecolor=BG, edgecolor=GRID, labelcolor=FG, fontsize=8)
    verdict = "PASS" if trace.get("passed") else "FAIL"
    ax.set_title(f"{meta['variant']} / {meta['scenario']}  -  {verdict}   ({meta['description']})",
                 color="#a3be8c" if verdict == "PASS" else "#bf616a", loc="left", fontsize=10)

    ax = axes[1]
    ax.plot(t, sig["lift_cmd_pct"], color="#ebcb8b", lw=1.2, label="lift cmd (%)")
    ax.plot(t, [v / fs * 100.0 for v in sig["lift_dps"]], color="#88c0d0", lw=1.0, label="lift velocity actual (% FS)")
    ax.plot(t, sig["reach_cmd_pct"], color="#b48ead", lw=1.0, alpha=0.8, label="reach cmd (%)")
    ax.set_ylabel("cmd [%]")
    ax.legend(loc="upper right", facecolor=BG, edgecolor=GRID, labelcolor=FG, fontsize=8)

    ax = axes[2]
    ax.plot(t, sig["grip_bar"], color="#a3be8c", lw=1.0, label="gripper (bar)")
    ax.plot(t, sig["effort"], color="#d08770", lw=1.0, label=f"lift actuator ({meta['effort_unit']})")
    ax.plot(t, [v * 10 for v in sig["speed_mph"]], color="#5e81ac", lw=1.0, label="vehicle speed (x10 mph)")
    ax.legend(loc="upper right", facecolor=BG, edgecolor=GRID, labelcolor=FG, fontsize=8)

    ax = axes[3]
    names = meta["state_names"]
    start = 0
    for i in range(1, len(t) + 1):
        if i == len(t) or sig["state"][i] != sig["state"][start]:
            s = sig["state"][start]
            ax.axvspan(t[start], t[i - 1] + 0.01, color=STATE_COLORS[s])
            if t[i - 1] - t[start] > 0.6:
                ax.text((t[start] + t[i - 1]) / 2, 0.5, names[s], ha="center", va="center", color="white", fontsize=7)
            start = i
    ax.set_yticks([])
    ax.set_xlabel("time [s]", color=FG)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=110, facecolor=BG)
    plt.close(fig)
    return path
