"""Assemble the final vertical social video: branded intro/outro + real app footage
(Ken Burns pans over the actual live dashboard) with crossfades, 30fps.
"""
import subprocess
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent
OUT = ROOT / "output"
REAL = OUT / "real"
WORK = OUT / "work"
WORK.mkdir(exist_ok=True)

W, H = 1080, 1920
FPS = 30


def run(cmd):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


SRC_FPS = 25  # Playwright's bundled ffmpeg records webm at a fixed 25fps.


def kenburns_clip(src, start, dur, rect0, rect1, out, fps=FPS):
    """rect = (x, y, w) in source pixel space; h is derived as w*16/9 to keep 9:16.

    Uses the frame-counter variable 'n' (not 't') in the crop expressions — this
    ffmpeg build only evaluates w/h/x/y per-frame when driven by 'n'.
    """
    x0, y0, w0 = rect0
    x1, y1, w1 = rect1
    h0 = w0 * 16 / 9
    h1 = w1 * 16 / 9
    total_frames = max(1, round(dur * SRC_FPS))
    x_expr = f"{x0}+({x1}-{x0})*(n/{total_frames})"
    y_expr = f"{y0}+({y1}-{y0})*(n/{total_frames})"
    w_expr = f"{w0}+({w1}-{w0})*(n/{total_frames})"
    h_expr = f"{h0}+({h1}-{h0})*(n/{total_frames})"
    vf = (
        f"crop=w='{w_expr}':h='{h_expr}':x='{x_expr}':y='{y_expr}',"
        f"scale={W}:{H},fps={fps},format=yuv420p"
    )
    cmd = [
        "ffmpeg", "-y", "-ss", str(start), "-t", str(dur), "-i", str(src),
        "-vf", vf, "-an", "-c:v", "libx264", "-crf", "17", "-preset", "medium",
        str(out),
    ]
    run(cmd)


def extract(src, start, dur, out, fps=FPS):
    cmd = [
        "ffmpeg", "-y", "-ss", str(start), "-t", str(dur), "-i", str(src),
        "-vf", f"scale={W}:{H},fps={fps},format=yuv420p",
        "-an", "-c:v", "libx264", "-crf", "17", "-preset", "medium",
        str(out),
    ]
    run(cmd)


clips = []

# ---- 1. Branded intro (logo) + hook, from the existing polished HTML render ----
src_v2 = OUT / "crosslisteu_social_v2.mp4"
extract(src_v2, 0.0, 2.85, WORK / "00_intro.mp4")
clips.append(WORK / "00_intro.mp4")

# Source frame is 1600x1000. A 9:16 crop window has h = w*16/9, so w must stay
# <= 562 to fit the 1000px source height. Pans below sweep x/y/w within that bound.

# Source frame is 1600x1000. A 9:16 crop window has h = w*16/9, so for a given
# y-offset, w must stay <= (1000-y)*9/16 to fit inside the source frame.

# ---- 2. REAL Dashboard — start on stat cards, pan down+in to item rows/photos ----
kenburns_clip(REAL / "01_dashboard.webm", 4.3, 2.2,
              rect0=(270, 30, 540), rect1=(270, 30, 480),
              out=WORK / "10_dash_a.mp4")
kenburns_clip(REAL / "01_dashboard.webm", 6.2, 2.0,
              rect0=(270, 430, 300), rect1=(270, 430, 260),
              out=WORK / "11_dash_b.mp4")
clips += [WORK / "10_dash_a.mp4", WORK / "11_dash_b.mp4"]

# ---- 3. REAL Items list — real product photos, zoom in ----
kenburns_clip(REAL / "02_items.webm", 3.2, 2.6,
              rect0=(270, 340, 340), rect1=(270, 340, 300),
              out=WORK / "20_items.mp4")
clips.append(WORK / "20_items.mp4")

# ---- 4. REAL Platforms — real brand logos, connected badges ----
kenburns_clip(REAL / "03_platforms.webm", 3.2, 2.6,
              rect0=(270, 150, 460), rect1=(270, 150, 400),
              out=WORK / "30_platforms.mp4")
clips.append(WORK / "30_platforms.mp4")

# ---- 5. REAL Analytics — real Chart.js charts with data ----
kenburns_clip(REAL / "04_analytics.webm", 3.8, 2.3,
              rect0=(270, 130, 470), rect1=(270, 130, 410),
              out=WORK / "40_an_a.mp4")
kenburns_clip(REAL / "04_analytics.webm", 5.9, 1.3,
              rect0=(270, 100, 500), rect1=(1080, 100, 460),
              out=WORK / "41_an_b.mp4")
clips += [WORK / "40_an_a.mp4", WORK / "41_an_b.mp4"]

# ---- 6. REAL Margin calculator — live computed results ----
kenburns_clip(REAL / "05_calculator.webm", 5.1, 2.6,
              rect0=(270, 150, 460), rect1=(270, 300, 380),
              out=WORK / "50_calc.mp4")
clips.append(WORK / "50_calc.mp4")

# ---- 7. Branded success burst + CTA from the HTML render ----
extract(src_v2, 13.15, 2.2, WORK / "90_success.mp4")
extract(src_v2, 21.25, 2.35, WORK / "91_cta.mp4")
clips += [WORK / "90_success.mp4", WORK / "91_cta.mp4"]

# ---- Concat with short crossfades ----
XFADE = 0.28
first = str(clips[0])
cur_dur = float(subprocess.run(
    ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", first],
    capture_output=True, text=True
).stdout.strip())

filter_parts = []
inputs = ["-i", first]
last_label = "0:v"
running_offset = cur_dur - XFADE

for i, clip in enumerate(clips[1:], start=1):
    inputs += ["-i", str(clip)]
    dur = float(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(clip)],
        capture_output=True, text=True
    ).stdout.strip())
    out_label = f"v{i}"
    filter_parts.append(
        f"[{last_label}][{i}:v]xfade=transition=fade:duration={XFADE}:offset={running_offset:.3f}[{out_label}]"
    )
    last_label = out_label
    running_offset += dur - XFADE

filter_complex = ";".join(filter_parts)
final_out = OUT / "crosslisteu_real_v3.mp4"
cmd = ["ffmpeg", "-y"] + inputs + [
    "-filter_complex", filter_complex,
    "-map", f"[{last_label}]",
    "-c:v", "libx264", "-crf", "17", "-preset", "medium", "-pix_fmt", "yuv420p",
    str(final_out),
]
subprocess.run(cmd, check=True)
print("Final:", final_out)
