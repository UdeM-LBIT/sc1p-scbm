#!/bin/sh
# Run the annotated resolutions without observed leaf orders.
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repo_dir=$(CDPATH= cd -- "$script_dir/../.." && pwd)
output_dir=${1:-"$script_dir/results-no-leaf-orders"}
mkdir -p "$output_dir"
output_dir=$(CDPATH= cd -- "$output_dir" && pwd)

cd "$repo_dir"
found=0
for tree in "$script_dir"/crispr-class1-resolv*-out-lo20-le10-go1.nhx; do
    [ -f "$tree" ] || continue
    found=1
    name=$(basename "$tree" .nhx)
    output="$output_dir/$name-scbm.json"
    temporary=$(mktemp "$output_dir/.scbm.XXXXXXXX")
    if uv run --all-extras scbm history "$tree" \
        --loss-open 20 --loss-ext 10 --gain-open 1 --gain-ext 0 \
        --mode pareto --all > "$temporary"; then
        mv -f "$temporary" "$output"
        python3 - "$output" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
report = json.loads(path.read_text())
resolution = path.name.removeprefix("crispr-class1-resolv").split("-out-", 1)[0]
print(f"\nRésolution {resolution}")
for history in report["histories"]:
    results = [r for r in report["results"] if r["history"] == history["solution"]]
    if not results:
        print(f"  Histoire {history['solution']} : aucune solution")
        continue
    optimum = min(r["history_cost"] for r in results)
    optimal = [r for r in results if r["history_cost"] == optimum]
    print(f"  Coût InOutParsimony : {history['recomputed_inout_cost']}")
    print(f"  Coût segmental optimal : {optimum}")
    reversal = " (à renversement près)" if report["orders_up_to_reversal"] else ""
    print(f"  Ordres optimaux{reversal} : {len(optimal)}")
    print("  Exemple optimal : " + " · ".join(optimal[0]["order"]))
print(f"  Résultats complets : {path}")
PY
    else
        rm -f "$temporary"
        printf 'Failed: %s\n' "$tree" >&2
        exit 1
    fi
done

if [ "$found" -eq 0 ]; then
    printf 'No annotated resolution files found in %s\n' "$script_dir" >&2
    exit 1
fi
