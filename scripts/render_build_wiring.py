"""Create original, deterministic electrical reference sheets; no image edits.

Run from the repository root with Python and matplotlib. The drawings use
generic terminal labels, not physical PCB pad positions or verified mechanics.
"""
from pathlib import Path
import json
import os

os.environ.setdefault("MPLCONFIGDIR", "/tmp/microduck-matplotlib")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Circle

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/build-guide"
CFG = json.loads((ROOT / "hardware/robot.json").read_text())
NAVY = "#162D42"
TEAL = "#087F8C"
BLUE = "#2372B8"
PURPLE = "#8A52A0"
ORANGE = "#D16B13"
RED = "#BA3335"
GRAY = "#4E5C66"
LIGHT = "#F2F5F7"


def text(ax, x, y, value, size=11, color=NAVY, weight="normal", ha="left", va="center"):
    return ax.text(x, y, value, fontsize=size, color=color, weight=weight,
                   ha=ha, va=va, linespacing=1.35, family="DejaVu Sans")


def box(ax, x, y, w, h, fill=LIGHT, edge="#C7D2D9", lw=1):
    patch = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.025,rounding_size=0.09",
                          linewidth=lw, edgecolor=edge, facecolor=fill)
    ax.add_patch(patch)
    return patch


def wire(ax, points, color=GRAY, lw=2, arrow=False):
    xs, ys = zip(*points)
    ax.plot(xs, ys, color=color, linewidth=lw, solid_capstyle="round")
    if arrow:
        ax.add_patch(FancyArrowPatch(points[-2], points[-1], arrowstyle="-|>",
                                    mutation_scale=14, linewidth=lw, color=color))


def dot(ax, x, y, color=GRAY):
    ax.add_patch(Circle((x, y), 0.045, color=color, zorder=6))


def vertical_resistor(ax, x, low, high, color):
    ys = [low + (high - low) * i / 6 for i in range(7)]
    xs = [x, x - .07, x + .07, x - .07, x + .07, x - .07, x]
    # White backing removes the underlying branch segment: this is a resistor,
    # never a direct short from a GPIO to the power rail.
    ax.plot([x, x], [low, high], color="white", linewidth=4, zorder=7)
    ax.plot(xs, ys, color=color, linewidth=1.4, zorder=8)


def base(number, title, subtitle):
    fig, ax = plt.subplots(figsize=(16.54, 11.69))
    fig.subplots_adjust(0, 0, 1, 1)
    ax.set(xlim=(0, 16.54), ylim=(0, 11.69))
    ax.set_axis_off()
    fig.patch.set_facecolor("white")
    text(ax, .55, 11.16, f"{number}  /  {title}", 24, weight="bold")
    text(ax, .58, 10.65, subtitle, 12, color=GRAY)
    ax.plot([.55, 15.98], [10.35, 10.35], color=TEAL, linewidth=2)
    text(ax, .58, .27, "DIY MICRODUCK / 8-SERVO BENCH PROTOTYPE", 10, weight="bold")
    text(ax, 15.98, .27, "SCHEMATIC TERMINALS • NOT PHYSICAL PAD LOCATIONS • NOT TO SCALE", 9, color=GRAY, ha="right")
    return fig, ax


def save(fig, name):
    OUT.mkdir(parents=True, exist_ok=True)
    for suffix in ("svg", "pdf", "png"):
        fig.savefig(OUT / f"{name}.{suffix}", dpi=300, facecolor="white")
    plt.close(fig)


def logic_sheet():
    pi, esp = CFG["controllers"]["pi"], CFG["controllers"]["esp32"]
    fig, ax = base("03", "LOGIC WIRING — EXACT CONNECTIONS",
                   "Classic ESP32-WROOM DevKit only. Leave the servo V+ supply physically disconnected for this sheet.")
    box(ax, .6, 6.05, 15.34, 4.0, fill="white")
    text(ax, .88, 9.72, "A. Pi ↔ ESP32: three signal connections", 15, weight="bold")
    text(ax, 15.6, 9.72, "115200 baud • 8N1 • 3.3 V signals", 11, ha="right", color=TEAL)
    box(ax, .95, 6.5, 3.7, 2.7, fill="#EAF3E7", edge="#9FB69A")
    box(ax, 11.2, 6.5, 4.35, 2.7, fill="#EAF1F7", edge="#9BB1C7")
    text(ax, 1.18, 8.9, "Raspberry Pi Zero 2 W", 14, weight="bold")
    text(ax, 11.45, 8.9, "ESP32 UART2", 14, weight="bold")
    rows = [(8.12, f"Pin {pi['uart_tx_header_pin']} / GPIO{pi['uart_tx_bcm']} TX", f"GPIO{esp['uart_rx_gpio']} / RX2", BLUE),
            (7.45, f"Pin {pi['uart_rx_header_pin']} / GPIO{pi['uart_rx_bcm']} RX", f"GPIO{esp['uart_tx_gpio']} / TX2", PURPLE),
            (6.78, "Pin 6 / GND", "GND", GRAY)]
    for index, (y, left, right, color) in enumerate(rows):
        text(ax, 1.18, y, left, 12)
        text(ax, 11.45, y, right, 12)
        if index == 1:
            wire(ax, [(11.2, y), (4.65, y)], color, arrow=True)
        else:
            wire(ax, [(4.65, y), (11.2, y)], color, arrow=index == 0)
        dot(ax, 4.65, y, color)
        dot(ax, 11.2, y, color)
    text(ax, 7.9, 8.34, "Pi TX → ESP RX", 11, color=BLUE, ha="center", weight="bold")
    text(ax, 7.9, 7.67, "Pi RX ← ESP TX", 11, color=PURPLE, ha="center", weight="bold")
    text(ax, 7.9, 7.0, "Shared signal ground", 11, color=GRAY, ha="center")
    text(ax, .95, 6.25, "Power Pi + ESP32 through their approved USB/5 V logic inputs. Disable Pi serial login before using the UART.", 11)

    box(ax, .6, .85, 15.34, 4.95, fill="white")
    text(ax, .88, 5.44, "B. ESP32 I²C: connect each row as one shared electrical net", 15, weight="bold")
    headers = [(1.05, "SIGNAL"), (4.0, "ESP32 / SOURCE"), (8.2, "PCA9685 — 0x40"), (12.0, "MPU6050 — 0x68")]
    for x, label in headers:
        text(ax, x, 4.87, label, 12, weight="bold")
    matrix = [
        (4.27, "SDA / data", f"GPIO{esp['i2c_sda_gpio']}", "SDA", "SDA", TEAL),
        (3.65, "SCL / clock", f"GPIO{esp['i2c_scl_gpio']}", "SCL", "SCL", BLUE),
        (3.03, "LOGIC POWER", "3.3 V logic source*", "VCC = 3.3 V", "3.3 V-compatible input*", ORANGE),
        (2.41, "REFERENCE", "GND", "GND", "GND", GRAY),
    ]
    for y, label, source, pca, imu, color in matrix:
        box(ax, .92, y - .23, 14.7, .47, fill=LIGHT, edge="white")
        ax.plot([1.01, 1.01], [y - .16, y + .16], color=color, linewidth=4)
        for x, value in ((1.16, label), (4.0, source), (8.2, pca), (12.0, imu)):
            text(ax, x, y, value, 11.6, color=color if x == 1.16 else NAVY,
                 weight="bold" if x == 1.16 else "normal")
    text(ax, 1.04, 1.84, "* Verify the actual breakout's supply labels/regulator requirements and the 3.3 V source capacity before wiring.", 10.5)
    text(ax, 1.04, 1.44, "Keep I²C pull-ups at 3.3 V. AD0 low gives MPU6050 address 0x68. PCA9685 VCC is NOT servo V+.", 10.5, weight="bold")
    text(ax, 1.04, 1.08, "No Pi SDA/SCL connection is used here. Match printed signal names on your own boards, not these drawing positions.", 10.5)
    save(fig, "03-logic-wiring")


def servo_sheet():
    fig, ax = base("04", "SERVO POWER, INHIBITS & CHANNEL MAP",
                   "Planning diagram only. The current firmware has no PWM backend; never energize servos to try the software demo.")
    text(ax, .65, 9.98, "A. Dedicated servo positive supply — separate from the Pi/ESP32 positive rail", 15, weight="bold")
    blocks = [(.65, 2.05, "5 V servo\nsupply", "Source capacity\nto be measured"),
              (3.07, 1.20, "Fuse", "Rated after\nmeasurements"),
              (4.64, 2.1, "Latching\nphysical stop", "DC-current-rated\nindependent cutoff"),
              (7.11, 2.1, "Default-OFF\nhigh-side gate", "GPIO controls EN;\nnot motor current"),
              (9.58, 2.15, "PCA9685\nservo V+", "NOT logic VCC"),
              (12.10, 3.8, "Eight servos\nV+ terminals", "No servo return current\nthrough Pi / breadboard")]
    for x, w, title, sub in blocks:
        box(ax, x, 8.72, w, .98, fill="#FFF0E9", edge="#D9AC9B")
        text(ax, x + w / 2, 9.22, title, 12, weight="bold", ha="center")
        text(ax, x + w / 2, 8.31, sub, 10, color=GRAY, ha="center")
    for i in range(len(blocks) - 1):
        x, w, *_ = blocks[i]
        wire(ax, [(x + w, 9.21), (blocks[i + 1][0], 9.21)], RED, 2.8, arrow=True)
    # A dedicated heavy return path bypasses logic boards; a single ground
    # distribution node joins the signal reference without joining positive rails.
    wire(ax, [(14.5, 8.72), (14.5, 7.57), (1.67, 7.57), (1.67, 8.72)], GRAY, 3)
    text(ax, 1.8, 8.68, "− / GND", 10, va="top", weight="bold", color=GRAY)
    text(ax, 14.35, 8.68, "servo GND terminals", 10, ha="right", va="top", weight="bold", color=GRAY)
    text(ax, 8.22, 7.87, "HEAVY SERVO RETURN → suitable common ground distribution → supply negative", 11, ha="center", weight="bold")
    dot(ax, 8.18, 7.57)
    wire(ax, [(8.18, 7.57), (8.18, 7.12)], GRAY, 1.6)
    text(ax, 8.18, 6.99, "Pi / ESP32 / PCA9685 / IMU signal grounds join here", 10.5, ha="center")

    box(ax, .6, 3.12, 7.12, 3.5, fill="white")
    text(ax, .88, 6.27, "B. Reset-safe inhibits", 14, weight="bold")
    text(ax, .9, 5.66, "ESP GPIO25", 11, weight="bold")
    wire(ax, [(2.52, 5.66), (6.18, 5.66)], PURPLE, arrow=True)
    text(ax, 6.28, 5.66, "PCA OE", 11, weight="bold")
    dot(ax, 4.95, 5.66, PURPLE)
    wire(ax, [(4.95, 5.66), (4.95, 6.02)], PURPLE, 1.5)
    vertical_resistor(ax, 4.95, 5.77, 5.95, PURPLE)
    text(ax, 4.85, 6.1, "3.3 V pull-up", 10, ha="right", color=PURPLE)
    text(ax, 2.95, 5.31, "OE HIGH = outputs DISABLED", 11, color=PURPLE, weight="bold")
    text(ax, .9, 4.58, "ESP GPIO26", 11, weight="bold")
    wire(ax, [(2.52, 4.58), (6.18, 4.58)], TEAL, arrow=True)
    text(ax, 6.28, 4.58, "Gate EN", 11, weight="bold")
    dot(ax, 4.95, 4.58, TEAL)
    wire(ax, [(4.95, 4.58), (4.95, 4.23)], TEAL, 1.5)
    vertical_resistor(ax, 4.95, 4.31, 4.49, TEAL)
    text(ax, 4.85, 4.15, "GND pull-down", 10, ha="right", color=TEAL)
    text(ax, 2.95, 3.81, "EN LOW = servo power OFF", 11, color=TEAL, weight="bold")
    text(ax, .9, 3.39, "External resistors required; values/circuit depend on selected boards.", 10)

    box(ax, 8.12, 3.12, 7.82, 3.5, fill="white")
    text(ax, 8.4, 6.27, "C. PCA9685 signal channel → joint", 14, weight="bold")
    for i, joint in enumerate(CFG["joints"]):
        y = 5.83 - i * .315
        text(ax, 8.48, y, f"CH {joint['channel']}", 11, color=TEAL, weight="bold")
        text(ax, 9.35, y, joint["name"], 11)
        text(ax, 14.98, y, "LEG" if joint["role"] == "leg" else "HEAD", 10, color=GRAY)
    text(ax, 8.4, 3.29, "Left/right means the robot's own left/right, not the viewer's.", 10)

    box(ax, .6, .85, 15.34, 1.9, fill="#FFF7DF", edge="#E3D1A1")
    text(ax, .9, 2.41, "D. Identify the three actual servo connections before plugging in", 14, weight="bold")
    for x, title, color in ((1.0, "SIGNAL → assigned CH", BLUE),
                            (5.98, "V+ → switched servo 5 V", RED),
                            (11.16, "GND → heavy return", GRAY)):
        text(ax, x, 1.91, title, 12, color=color, weight="bold")
    text(ax, .9, 1.48, "Header order and servo lead colors vary: use board labels and the servo datasheet. Do not infer pin order from this sheet.", 10.5)
    text(ax, .9, 1.08, "Before any future output: measured calibration, rated power/stop/gate, supported mechanism and commissioning checks are required.", 10.5)
    save(fig, "04-servo-power-and-channels")


if __name__ == "__main__":
    assert CFG["hardware_output_enabled"] is False
    assert CFG["initial_dof"] == 8
    assert [j["channel"] for j in CFG["joints"]] == list(range(8))
    logic_sheet()
    servo_sheet()
    print(f"Created original electrical reference sheets in {OUT}")
