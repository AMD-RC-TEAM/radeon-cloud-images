"""Renders docs/design/strata-qwen38.png (images#54). Design diagram for images#54 (strata-qwen38): request path, build inputs, model mount, and the 55 GiB memory budget.
Usage: python3 strata_design_diagram.py <out.png>
Colors: the dataviz reference palette (categorical slots 1-3 validated on #fcfcfb; slot 3 is below 3:1, so every bar
segment carries a direct text label). Text stays in ink colors, never series colors."""
import sys
import matplotlib
matplotlib.use("Agg")
from matplotlib import font_manager, pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

for f in font_manager.findSystemFonts():
    if "Lato" in f:
        font_manager.fontManager.addfont(f)
plt.rcParams["font.family"] = "Lato"

SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#d9d8d3"
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"

fig = plt.figure(figsize=(13, 8.2), dpi=150, facecolor=SURFACE)
ax = fig.add_axes([0, 0.30, 1, 0.70]); ax.set_xlim(0, 130); ax.set_ylim(0, 60); ax.axis("off")


def box(x, y, w, h, title, lines=(), edge=INK2, fill="#ffffff", lw=1.2, title_size=11.5):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.25,rounding_size=1.2", fc=fill, ec=edge, lw=lw))
    ax.text(x + 1.2, y + h - 1.6, title, fontsize=title_size, fontweight="bold", color=INK, va="top")
    for i, l in enumerate(lines):
        ax.text(x + 1.2, y + h - 4.6 - i * 2.6, l, fontsize=9.2, color=INK2, va="top")


def arrow(x1, y1, x2, y2, label="", dy=1.2, style="-|>", ls="-"):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle=style, mutation_scale=12, color=INK2, lw=1.4, linestyle=ls))
    if label:
        ax.text((x1 + x2) / 2, (y1 + y2) / 2 + dy, label, fontsize=8.8, color=INK2, ha="center", va="bottom")


ax.text(1, 59, "strata-qwen38: Strata serving Qwen3.8-Flash-Next on one W7900D (test sites only)", fontsize=15, fontweight="bold", color=INK, va="top")

# Request path
box(1, 36, 17, 13, "User", ["browser or notebook", "OpenAI client"])
box(23, 36, 19, 13, "Radeon Cloud gateway", ["per-instance login", "/instances/<id>/", "  proxy/8080/v1"])
arrow(18.3, 42.5, 22.7, 42.5)
# Instance
ax.add_patch(FancyBboxPatch((47, 14), 82, 39, boxstyle="round,pad=0.3,rounding_size=1.6", fc="#f4f6fa", ec=BLUE, lw=1.8))
ax.text(48.3, 51.6, "1-GPU instance pod  ·  limits 55 GiB RAM, 16 CPU, 1 W7900D (48 GB VRAM)", fontsize=11.5, fontweight="bold", color=INK, va="top")
box(49, 34, 26, 14, "JupyterLab :8888", ["started by the platform", "+ jupyter-server-proxy", "/proxy/8080/ → 127.0.0.1:8080"])
box(49, 17, 26, 14, "rc_strata_autostart", ["Jupyter extension in the image", "starts the engine with Jupyter,", "SIGTERM when Jupyter stops (≤25 s)"])
box(81, 34, 46, 14, "Strata engine  ·  127.0.0.1:8080 (OpenAI API)", ["not exposed: reachable only inside the pod / via the proxy",
    "GPU: all 24,576 experts resident in VRAM (40 GB)", "28.8 GB n-gram table: direct NVMe reads, no page cache"])
box(81, 17, 46, 14, "Model mount  /models/qwen38-flash-next-iq3xxs", ["78.2 GB, read-only hostPath on node-local NVMe",
    "staged by ops on 2-3 W7900D nodes, sha256-checked", "Admin template's model_mount pins scheduling there"], edge=AQUA)
arrow(42.3, 42.5, 48.7, 42.5)
arrow(75.3, 41, 80.7, 41, "HTTP")
arrow(62, 31.2, 62, 33.7, "", style="-|>")
ax.text(63, 32.2, "start / stop", fontsize=8.8, color=INK2, va="center")
arrow(104, 31.2, 104, 33.7)
ax.text(105, 32.2, "weights, table rows", fontsize=8.8, color=INK2, va="center")

# Build path
box(1, 2, 40, 22, "Image build (CI, merge = release)", [
    "FROM rocm/dev-ubuntu-24.04:7.2.1-complete@sha256",
    "   (public, pinned; the engine is built for ROCm 7.2.1)",
    "COPY --from=<Harbor> rc-artifacts/strata-bundle@sha256",
    "   engine bundle, sha256 re-checked in the build",
    "+ JupyterLab, jupyter-server-proxy, sshd,",
    "   autostart extension, README + quick-test notebook"], edge=ORANGE)
arrow(41.3, 13, 46.7, 22)

# Memory budget (measured in the instance shape, s-060, 11-26)
bx = fig.add_axes([0.06, 0.07, 0.88, 0.17]); bx.set_facecolor(SURFACE)
segs = [("engine working memory\n~13-15 GiB, not reclaimable", 14.0, BLUE),
        ("conversation cache\n≤12 GiB (bundle v3+)", 12.0, ORANGE),
        ("page cache for the model files\nthe kernel reclaims it at the limit", 55.0 - 26.0, AQUA)]
left = 0
for label, w, c in segs:
    bx.barh(0, w - 0.25, left=left, height=0.55, color=c, edgecolor=SURFACE, linewidth=2)
    bx.text(left + 0.6, 0.47, label, fontsize=9.2, color=INK, va="bottom")
    left += w
bx.axvline(55, color=INK, lw=1.2); bx.text(54.7, -0.42, "55 GiB limit", fontsize=9.2, color=INK, ha="right", va="top")
bx.set_xlim(0, 58); bx.set_ylim(-0.6, 1.25); bx.set_yticks([])
bx.set_xticks(range(0, 56, 5)); bx.tick_params(axis="x", colors=INK2, labelsize=8.5, length=3)
for s in ("top", "right", "left"):
    bx.spines[s].set_visible(False)
bx.spines["bottom"].set_color(GRID)
bx.set_title("Memory budget inside the 55 GiB pod, measured on s-060: 0 OOM kills.  1 / 2 users: bundle v2.1 ~70 / ~79 tok/s, bundle v3.1 ~78 / ~90 tok/s",
             fontsize=10.5, color=INK, loc="left", pad=16, fontweight="bold")
fig.savefig(sys.argv[1], facecolor=SURFACE)
print("wrote", sys.argv[1])
