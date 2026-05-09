#!/usr/bin/python3

import csv
import sys
from pathlib import Path
from collections import defaultdict
import numpy as np
import matplotlib.pyplot as plt

if len(sys.argv) < 2:
    print("Usage: plot_h4.py <results_dir>")
    sys.exit(1)

RESULTS_DIR = Path(sys.argv[1])
CSV_PATH = RESULTS_DIR / "wrk_results.csv"
OUT_DIR = RESULTS_DIR / "plots"
OUT_DIR.mkdir(exist_ok=True)

N_CORES = 4

# Színek és stílusok task típusonként
TASK_STYLES = {
    "cpu": {"color": "tab:blue", "marker": "o", "label": "CPU-bound"},
    "io": {"color": "tab:red", "marker": "s", "label": "IO-bound (disk)"},
    "network": {"color": "tab:green", "marker": "^", "label": "Network proxy"},
}


# ============================================================
# Adat beolvasás
# ============================================================

def load_data(csv_path):
    """task -> connections -> list of measurements."""
    data = defaultdict(lambda: defaultdict(list))

    with open(csv_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["requests_per_sec"] == "":
                continue

            task = row["task"]
            connections = int(row["connections"])

            errors = (int(row["socket_errors_connect"] or 0) +
                      int(row["socket_errors_read"] or 0) +
                      int(row["socket_errors_write"] or 0) +
                      int(row["socket_errors_timeout"] or 0))
            non_2xx = int(row["non_2xx_responses"] or 0)

            data[task][connections].append({
                "run": int(row["run"]),
                "rps": float(row["requests_per_sec"]),
                "p50": float(row["latency_p50_ms"]) if row["latency_p50_ms"] else None,
                "p90": float(row["latency_p90_ms"]) if row["latency_p90_ms"] else None,
                "p99": float(row["latency_p99_ms"]) if row["latency_p99_ms"] else None,
                "avg": float(row["latency_avg_ms"]) if row["latency_avg_ms"] else None,
                "errors": errors,
                "non_2xx": non_2xx,
                "timeouts": int(row["socket_errors_timeout"] or 0),
            })
    return data


def aggregate(data_per_c, key):
    """connections -> átlag és szórás."""
    cons = sorted(data_per_c.keys())
    means, stds, ns = [], [], []
    for c in cons:
        vals = [r[key] for r in data_per_c[c] if r[key] is not None]
        if vals:
            means.append(np.mean(vals))
            stds.append(np.std(vals, ddof=1) if len(vals) > 1 else 0)
            ns.append(len(vals))
        else:
            means.append(np.nan)
            stds.append(np.nan)
            ns.append(0)
    return np.array(cons), np.array(means), np.array(stds), np.array(ns)


def find_knee(cons, p50_means):
    """Egyszerű knee point detektálás:
    a görbe meredekségének legnagyobb növekedése."""
    if len(cons) < 4:
        return None
    log_cons = np.log2(cons)
    log_lat = np.log2(p50_means)
    # Páronkénti meredekségek
    slopes = np.diff(log_lat) / np.diff(log_cons)
    # A legnagyobb növekedés helye
    if len(slopes) < 2:
        return None
    slope_diffs = np.diff(slopes)
    knee_idx = np.argmax(slope_diffs) + 1  # +1, mert diff után 1-gyel csúszik
    return cons[knee_idx]


# ============================================================
# Plotok
# ============================================================

def plot_throughput_vs_clients(data, out_path):
    """Throughput a kliensszám függvényében, mind a 3 task egy ábrán."""
    fig, ax = plt.subplots(figsize=(11, 6.5))

    for task in ["cpu", "io", "network"]:
        if task not in data:
            continue
        style = TASK_STYLES[task]
        cons, means, stds, _ = aggregate(data[task], "rps")
        ax.errorbar(cons, means, yerr=stds,
                    color=style["color"], marker=style["marker"],
                    capsize=3, linewidth=1.5, markersize=7,
                    label=style["label"])

    ax.axvline(x=N_CORES, color="gray", linestyle=":", alpha=0.4,
               label=f"N_cores = {N_CORES}")
    ax.axvline(x=8, color="gray", linestyle="--", alpha=0.4,
               label="N_workers = 8")
    ax.set_xscale("log", base=2)
    ax.set_yscale("log")
    ax.set_xlabel("Párhuzamos kliensek száma")
    ax.set_ylabel("Throughput (req/s)")
    ax.set_title("H4: Throughput skálázódás task típusonként")
    ax.grid(True, which="both", alpha=0.3)
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"Saved: {out_path}")


def plot_latency_vs_clients(data, out_path, latency_key="p50",
                              title_suffix=""):
    """Latency a kliensszám függvényében."""
    fig, ax = plt.subplots(figsize=(11, 6.5))

    for task in ["cpu", "io", "network"]:
        if task not in data:
            continue
        style = TASK_STYLES[task]
        cons, means, stds, _ = aggregate(data[task], latency_key)
        ax.errorbar(cons, means, yerr=stds,
                    color=style["color"], marker=style["marker"],
                    capsize=3, linewidth=1.5, markersize=7,
                    label=style["label"])

    ax.axvline(x=N_CORES, color="gray", linestyle=":", alpha=0.4)
    ax.axvline(x=8, color="gray", linestyle="--", alpha=0.4)
    ax.set_xscale("log", base=2)
    ax.set_yscale("log")
    ax.set_xlabel("Párhuzamos kliensek száma")
    ax.set_ylabel(f"{latency_key} latency (ms)")
    ax.set_title(f"H4: {latency_key} latency task típusonként{title_suffix}")
    ax.grid(True, which="both", alpha=0.3)
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"Saved: {out_path}")


def plot_normalized_latency(data, out_path):
    """Latency normalizálva a single-client (c=1) értékhez —
    így a görbék közvetlenül összehasonlíthatók."""
    fig, ax = plt.subplots(figsize=(11, 6.5))

    for task in ["cpu", "io", "network"]:
        if task not in data:
            continue
        style = TASK_STYLES[task]
        cons, means, stds, _ = aggregate(data[task], "p50")
        if len(means) == 0 or np.isnan(means[0]):
            continue
        baseline = means[0]
        normalized = means / baseline
        ax.plot(cons, normalized,
                color=style["color"], marker=style["marker"],
                linewidth=1.5, markersize=7,
                label=f"{style['label']} (c=1: {baseline:.1f}ms)")

    ax.axvline(x=N_CORES, color="gray", linestyle=":", alpha=0.4)
    ax.axvline(x=8, color="gray", linestyle="--", alpha=0.4)
    ax.set_xscale("log", base=2)
    ax.set_yscale("log")
    ax.set_xlabel("Párhuzamos kliensek száma")
    ax.set_ylabel("p50 latency / single-client p50 latency")
    ax.set_title("H4: Normalizált latency skálázódás (c=1 = 1.0)")
    ax.grid(True, which="both", alpha=0.3)
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"Saved: {out_path}")


def plot_combined_panels(data, out_path):
    """3 panel — minden task külön throughput és latency egyszerre."""
    tasks = [t for t in ["cpu", "io", "network"] if t in data]
    fig, axes = plt.subplots(1, len(tasks), figsize=(5*len(tasks), 5),
                              squeeze=False)

    for i, task in enumerate(tasks):
        ax = axes[0][i]
        ax2 = ax.twinx()

        cons, rps_means, rps_stds, _ = aggregate(data[task], "rps")
        cons, p50_means, p50_stds, _ = aggregate(data[task], "p50")

        ax.errorbar(cons, rps_means, yerr=rps_stds,
                    color="tab:green", marker="o", capsize=3,
                    linewidth=1.5, markersize=5, label="Throughput")
        ax2.errorbar(cons, p50_means, yerr=p50_stds,
                     color="tab:red", marker="s", capsize=3,
                     linewidth=1.5, markersize=5, label="p50 latency")

        ax.set_xscale("log", base=2)
        ax.set_xlabel("Párhuzamos kliensek száma")
        ax.set_ylabel("Throughput (req/s)", color="tab:green")
        ax2.set_ylabel("p50 latency (ms)", color="tab:red")
        ax.tick_params(axis="y", labelcolor="tab:green")
        ax2.tick_params(axis="y", labelcolor="tab:red")
        ax.set_title(TASK_STYLES[task]["label"])
        ax.grid(True, which="both", alpha=0.3)

        # Knee point jelölése
        knee = find_knee(cons, p50_means)
        if knee is not None:
            ax.axvline(x=knee, color="purple", linestyle=":", alpha=0.6)
            ax.annotate(f"knee: c={knee}",
                        xy=(knee, rps_means[list(cons).index(knee)]),
                        xytext=(8, 10), textcoords="offset points",
                        fontsize=9, color="purple")

    fig.suptitle("H4: Task típusonkénti throughput és latency", fontsize=13)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"Saved: {out_path}")


def plot_tail_ratio(data, out_path):
    """p99 / p50 arány — a tail latency érzékenysége."""
    fig, ax = plt.subplots(figsize=(11, 6.5))

    for task in ["cpu", "io", "network"]:
        if task not in data:
            continue
        style = TASK_STYLES[task]
        cons = sorted(data[task].keys())
        ratios = []
        for c in cons:
            p50_vals = [r["p50"] for r in data[task][c] if r["p50"]]
            p99_vals = [r["p99"] for r in data[task][c] if r["p99"]]
            if p50_vals and p99_vals:
                ratio = np.mean(p99_vals) / np.mean(p50_vals)
                ratios.append(ratio)
            else:
                ratios.append(np.nan)

        ax.plot(cons, ratios,
                color=style["color"], marker=style["marker"],
                linewidth=1.5, markersize=7,
                label=style["label"])

    ax.axhline(y=1, color="gray", linestyle=":", alpha=0.4)
    ax.set_xscale("log", base=2)
    ax.set_xlabel("Párhuzamos kliensek száma")
    ax.set_ylabel("p99 / p50 latency arány")
    ax.set_title("H4: Tail latency aránya (p99/p50) task típusonként")
    ax.grid(True, which="both", alpha=0.3)
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"Saved: {out_path}")


def plot_relative_throughput(data, out_path):
    """Throughput minden task-on a saját maximumához normalizálva.
    Ez mutatja, mennyi kliens kell a saját telítettséghez."""
    fig, ax = plt.subplots(figsize=(11, 6.5))

    for task in ["cpu", "io", "network"]:
        if task not in data:
            continue
        style = TASK_STYLES[task]
        cons, means, _, _ = aggregate(data[task], "rps")
        if len(means) == 0 or np.all(np.isnan(means)):
            continue
        max_rps = np.nanmax(means)
        normalized = means / max_rps
        ax.plot(cons, normalized * 100,
                color=style["color"], marker=style["marker"],
                linewidth=1.5, markersize=7,
                label=f"{style['label']} (max: {max_rps:.0f} req/s)")

    ax.axhline(y=100, color="gray", linestyle=":", alpha=0.4)
    ax.axvline(x=N_CORES, color="gray", linestyle=":", alpha=0.4)
    ax.axvline(x=8, color="gray", linestyle="--", alpha=0.4)
    ax.set_xscale("log", base=2)
    ax.set_xlabel("Párhuzamos kliensek száma")
    ax.set_ylabel("Throughput (a saját maximum %-ában)")
    ax.set_title("H4: Telítettségi profil — hány kliens kell a maximumhoz?")
    ax.grid(True, which="both", alpha=0.3)
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"Saved: {out_path}")


# ============================================================
# Számszerű összefoglaló
# ============================================================

def print_summary(data):
    print("\n" + "=" * 80)
    print("H4 MÉRÉSI ÖSSZEFOGLALÓ")
    print("=" * 80)

    for task in ["cpu", "io", "network"]:
        if task not in data:
            continue
        print(f"\n--- task={task} ({TASK_STYLES[task]['label']}) ---")
        print(f"{'cons':>6} {'n':>3} {'rps_avg':>10} {'rps_std':>8} "
              f"{'p50':>10} {'p99':>10} {'p99/p50':>8} {'errors':>8}")
        print("-" * 75)

        for c in sorted(data[task].keys()):
            rows = data[task][c]
            rps_vals = [r["rps"] for r in rows if r["rps"]]
            p50_vals = [r["p50"] for r in rows if r["p50"]]
            p99_vals = [r["p99"] for r in rows if r["p99"]]
            err_vals = [r["errors"] for r in rows]

            if rps_vals:
                rps_avg = np.mean(rps_vals)
                rps_std = np.std(rps_vals, ddof=1) if len(rps_vals) > 1 else 0
                p50_avg = np.mean(p50_vals) if p50_vals else float("nan")
                p99_avg = np.mean(p99_vals) if p99_vals else float("nan")
                ratio = p99_avg / p50_avg if p50_avg else float("nan")
                err_avg = np.mean(err_vals)
                print(f"{c:>6} {len(rows):>3} {rps_avg:>10.1f} {rps_std:>8.1f} "
                      f"{p50_avg:>10.1f} {p99_avg:>10.1f} {ratio:>8.2f} "
                      f"{err_avg:>8.0f}")


def comparative_analysis(data):
    """A H4 hipotézis kvantitatív tesztje."""
    print("\n" + "=" * 80)
    print("H4 ÖSSZEHASONLÍTÓ ELEMZÉS")
    print("=" * 80)

    for task in ["cpu", "io", "network"]:
        if task not in data:
            continue
        cons, rps_means, _, _ = aggregate(data[task], "rps")
        cons, p50_means, _, _ = aggregate(data[task], "p50")
        cons, p99_means, _, _ = aggregate(data[task], "p99")

        if len(rps_means) == 0:
            continue

        max_rps = np.nanmax(rps_means)
        max_rps_idx = np.nanargmax(rps_means)
        max_rps_c = cons[max_rps_idx]

        baseline_p50 = p50_means[0] if not np.isnan(p50_means[0]) else float("nan")
        max_p50 = np.nanmax(p50_means)

        knee = find_knee(cons, p50_means)

        print(f"\n--- task={task} ({TASK_STYLES[task]['label']}) ---")
        print(f"  Maximális throughput: {max_rps:.1f} req/s @ c={max_rps_c}")
        print(f"  Single-client p50:    {baseline_p50:.1f} ms")
        print(f"  Maximum p50 (c={cons[-1]}): {max_p50:.1f} ms")
        print(f"  Latency növekedés: {max_p50/baseline_p50:.1f}x")
        if knee is not None:
            print(f"  Knee point (becslés): c={knee}")

    # Throughput arányok a 3 task között
    print(f"\n--- Throughput arányok ---")
    rps_max = {}
    for task in ["cpu", "io", "network"]:
        if task in data:
            _, rps_means, _, _ = aggregate(data[task], "rps")
            if len(rps_means) > 0:
                rps_max[task] = np.nanmax(rps_means)
    if "cpu" in rps_max and "io" in rps_max:
        print(f"  CPU/IO throughput arány: {rps_max['cpu']/rps_max['io']:.2f}")
    if "cpu" in rps_max and "network" in rps_max:
        print(f"  CPU/Network throughput arány: {rps_max['cpu']/rps_max['network']:.2f}")
    if "io" in rps_max and "network" in rps_max:
        print(f"  IO/Network throughput arány: {rps_max['io']/rps_max['network']:.2f}")


# ============================================================
# Main
# ============================================================

def main():
    data = load_data(CSV_PATH)

    print_summary(data)
    comparative_analysis(data)

    plot_throughput_vs_clients(data, OUT_DIR / "h4_throughput.png")
    plot_latency_vs_clients(data, OUT_DIR / "h4_latency_p50.png", "p50",
                              " (medián)")
    plot_latency_vs_clients(data, OUT_DIR / "h4_latency_p99.png", "p99",
                              " (tail)")
    plot_normalized_latency(data, OUT_DIR / "h4_normalized_latency.png")
    plot_combined_panels(data, OUT_DIR / "h4_panels.png")
    plot_tail_ratio(data, OUT_DIR / "h4_tail_ratio.png")
    plot_relative_throughput(data, OUT_DIR / "h4_relative_throughput.png")

    print(f"\nMinden plot: {OUT_DIR}/")


if __name__ == "__main__":
    main()
