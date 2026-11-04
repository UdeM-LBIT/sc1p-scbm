"""Draw the global Pareto front from the saved SCBM results."""

import json
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator

here = Path(__file__).resolve().parent
report = json.loads((here / "pareto-global-24.json").read_text())
points = defaultdict(list)
for result in report["results"]:
    points[(result["history_cost"], result["broken_adjacencies"])].append(result)

plt.rcParams.update({"font.family": "sans-serif", "font.size": 11, "pdf.fonttype": 42})
fig, ax = plt.subplots(figsize=(7.2, 5.0), layout="constrained")
coordinates = sorted(points)
ax.plot(*zip(*coordinates), color="#97aab6", linestyle="--", linewidth=1.2, zorder=1)
for cost, broken in coordinates:
    rows = points[(cost, broken)]
    histories = sorted({r["history"].split("(")[-1].rstrip(")") for r in rows})
    label = f"({cost}, {broken})\nI–III : solution{'s' if len(histories) > 1 else ''} {', '.join(histories)}"
    ax.scatter(cost, broken, s=78, color="#195c78", edgecolor="white", linewidth=0.9, zorder=3)
    ax.annotate(label, (cost, broken), xytext=(10, 9), textcoords="offset points", fontsize=9.5)

ax.set(title="Front de Pareto global\n3 points · 5 résultats sur 24 histoires", xlabel="Coût historique", ylabel="Adjacences brisées")
ax.set_xlim(min(c for c, _ in coordinates) - 0.5, max(c for c, _ in coordinates) + 1.6)
ax.set_ylim(21.3, 27.1)
ax.xaxis.set_major_locator(MaxNLocator(integer=True))
ax.yaxis.set_major_locator(MaxNLocator(integer=True))
ax.grid(True, color="#dce3e7", linewidth=0.7)
ax.set_axisbelow(True)
ax.spines[["top", "right"]].set_visible(False)
fig.text(0.02, -0.015, "Pertes : ouverture 1, extension 1 · Gains : ouverture 1, extension 1", fontsize=9, color="#4b5961")
for extension in ("png", "pdf"):
    fig.savefig(here / f"pareto-global-24.{extension}", dpi=300, bbox_inches="tight")
