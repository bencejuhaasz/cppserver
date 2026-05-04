#!/usr/bin/python3

import csv
import sys
from pathlib import Path
from collections import defaultdict
import numpy as np
import matplotlib.pyplot as plt

if len(sys.argv) < 2:
    print("Usage: plot_h2.py <results_dir>")
    sys.exit(1)

RESULTS_DIR = Path(sys.argv[1])
CSV_PATH = RESULTS_DIR / "wrk_results.csv"
OUT_DIR = RESULTS_DIR / "plots"
OUT_DIR.mkdir(exist_ok=True)

N_CORES = 4

# Színek és stílusok task típusonként
TASK_STYLES = {
    "cpu": {"color": "tab:blue", "marker": "o", "label": "CPU-bound"},
    "io": {"color": "tab:red", "marker": "s", "label": "IO-bound"},
}

# Vonalstílusok kliensszámonként
LINE_STYLES = {
    8: "-",
    64: "--",
}


# ============================================================
# Adat beolvasás
# ============================================================

def load_data(csv_path):
    """phase -> task -> connections -> workers -> list of measurements."""
    data = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(list))))

    with open(csv_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["requests_per_sec"] == "":
                continue

            phase = row["phase"]
            task = row["task"]
            workers = int(row["workers"])
            connections = int(row["connections"])

            data[phase][task][connections][workers].append({
                "run": int(row["run"]),
                "rps": float(row["requests_per_sec"]),
                "p50": float(row["latency_p50_ms"]) if row["latency_p50_ms"] else None,
                "p90": float(row["latency_p90_ms"]) if row["latency_p90_ms"] else None,
                "p99": float(row["latency_p99_ms"]) if row["latency_p99_ms"] else None,
                "avg": float(row["latency_avg_ms"]) if row["latency_avg_ms"] else None,
                "timeout": int(row["socket_errors_timeout"]) if row["socket_errors_timeout"] else 0,
            })
    return data


def aggregate_workers(data_per_workers, key):
    """worker_count -> átlag és szórás."""
    workers = sorted(data_per_workers.keys())
    means, stds, ns = [], [], []
    for w in workers:
        vals = [r[key] for r in data_per_workers[w] if r[key] is not None]
        if vals:
            means.append(np.mean(vals))
            stds.append(np.std(vals, ddof=1) if len(vals) > 1 else 0)
            ns.append(len(vals))
        else:
            means.append(np.nan)
            stds.append(np.nan)
            ns.append(0)
    return np.array(workers), np.array(means), np.array(stds), np.array(ns)


def find_optimum(workers, values, mode="min"):
    """Visszaadja az optimális worker számot és értékét."""
    if mode == "min":
        idx = np.nanargmin(values)
    else:
        idx = np.nanargmax(values)
    return workers[idx], values[idx]


# ============================================================
# Plotok
# ============================================================

def plot_throughput_vs_workers(data, out_path):
    """Throughput a worker szám függvényében, task és kliensszám szerint."""
    fig, ax = plt.subplots(figsize=(11, 6.5))

    main_data = data["main"]
    for task in ["cpu", "io"]:
        if task not in main_data:
            continue
        style = TASK_STYLES[task]
        for connections in sorted(main_data[task].keys()):
            workers, means, stds, _ = aggregate_workers(
                main_data[task][connections], "rps"
            )
            label = f"{style['label']}, c={connections}"
            ax.errorbar(workers, means, yerr=stds,
                        color=style["color"], marker=style["marker"],
                        linestyle=LINE_STYLES.get(connections, "-"),
                        capsize=3, linewidth=1.5, markersize=6,
                        label=label)

    ax.axvline(x=N_CORES, color="gray", linestyle=":", alpha=0.5,
               label=f"N_cores = {N_CORES}")
    ax.set_xscale("log", base=2)
    ax.set_xlabel("Worker pool mérete")
    ax.set_ylabel("Throughput (req/s)")
    ax.set_title("H2: Throughput a worker pool méretének függvényében")
    ax.grid(True, which="both", alpha=0.3)
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"Saved: {out_path}")


def plot_latency_vs_workers(data, out_path, latency_key="p50",
                             title_suffix=""):
    """Latency a worker szám függvényében."""
    fig, ax = plt.subplots(figsize=(11, 6.5))

    main_data = data["main"]
    for task in ["cpu", "io"]:
        if task not in main_data:
            continue
        style = TASK_STYLES[task]
        for connections in sorted(main_data[task].keys()):
            workers, means, stds, _ = aggregate_workers(
                main_data[task][connections], latency_key
            )
            label = f"{style['label']}, c={connections}"
            ax.errorbar(workers, means, yerr=stds,
                        color=style["color"], marker=style["marker"],
                        linestyle=LINE_STYLES.get(connections, "-"),
                        capsize=3, linewidth=1.5, markersize=6,
                        label=label)

    ax.axvline(x=N_CORES, color="gray", linestyle=":", alpha=0.5,
               label=f"N_cores = {N_CORES}")
    ax.set_xscale("log", base=2)
    ax.set_yscale("log")
    ax.set_xlabel("Worker pool mérete")
    ax.set_ylabel(f"{latency_key} latency (ms)")
    ax.set_title(f"H2: {latency_key} latency a worker pool méretének függvényében"
                 f"{title_suffix}")
    ax.grid(True, which="both", alpha=0.3)
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"Saved: {out_path}")


def plot_optimum_visualization(data, out_path):
    """4 panel — task × kliensszám, mindegyik throughput és latency együtt."""
    main_data = data["main"]
    n_tasks = len([t for t in ["cpu", "io"] if t in main_data])
    n_cons = len(set(c for t in main_data.values() for c in t.keys()))

    fig, axes = plt.subplots(n_tasks, n_cons, figsize=(13, 4*n_tasks),
                              squeeze=False)

    tasks = [t for t in ["cpu", "io"] if t in main_data]
    all_cons = sorted(set(c for t in main_data.values() for c in t.keys()))

    for i, task in enumerate(tasks):
        for j, connections in enumerate(all_cons):
            if connections not in main_data[task]:
                continue
            ax = axes[i][j]
            ax2 = ax.twinx()

            workers, rps_means, rps_stds, _ = aggregate_workers(
                main_data[task][connections], "rps"
            )
            workers, p50_means, p50_stds, _ = aggregate_workers(
                main_data[task][connections], "p50"
            )

            ax.errorbar(workers, rps_means, yerr=rps_stds,
                        color="tab:green", marker="o", capsize=3,
                        linewidth=1.5, markersize=5, label="Throughput")
            ax2.errorbar(workers, p50_means, yerr=p50_stds,
                         color="tab:red", marker="s", capsize=3,
                         linewidth=1.5, markersize=5, label="p50 latency")

            # Optimum jelölése
            try:
                opt_w, opt_rps = find_optimum(workers, rps_means, "max")
                ax.axvline(x=opt_w, color="tab:green", linestyle=":", alpha=0.5)
                ax.annotate(f"optimum: {opt_w} worker",
                            xy=(opt_w, opt_rps),
                            xytext=(8, 8), textcoords="offset points",
                            fontsize=9, color="tab:green")
            except (ValueError, IndexError):
                pass

            ax.axvline(x=N_CORES, color="gray", linestyle=":", alpha=0.4)
            ax.set_xscale("log", base=2)
            ax.set_xlabel("Worker pool mérete")
            ax.set_ylabel("Throughput (req/s)", color="tab:green")
            ax2.set_ylabel("p50 latency (ms)", color="tab:red")
            ax.tick_params(axis="y", labelcolor="tab:green")
            ax2.tick_params(axis="y", labelcolor="tab:red")
            ax.set_title(f"{TASK_STYLES[task]['label']}, c={connections}")
            ax.grid(True, which="both", alpha=0.3)

    fig.suptitle("H2: Optimum keresése task × kliensszám szerint", fontsize=13)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"Saved: {out_path}")


def plot_tail_latency(data, out_path):
    """p99 / p50 arány — a tail latency elszállását mutatja."""
    fig, ax = plt.subplots(figsize=(11, 6.5))

    main_data = data["main"]
    for task in ["cpu", "io"]:
        if task not in main_data:
            continue
        style = TASK_STYLES[task]
        for connections in sorted(main_data[task].keys()):
            workers_data = main_data[task][connections]
            workers = sorted(workers_data.keys())
            ratios = []
            for w in workers:
                p50_vals = [r["p50"] for r in workers_data[w] if r["p50"]]
                p99_vals = [r["p99"] for r in workers_data[w] if r["p99"]]
                if p50_vals and p99_vals:
                    ratio = np.mean(p99_vals) / np.mean(p50_vals)
                    ratios.append(ratio)
                else:
                    ratios.append(np.nan)

            label = f"{style['label']}, c={connections}"
            ax.plot(workers, ratios, color=style["color"],
                    marker=style["marker"],
                    linestyle=LINE_STYLES.get(connections, "-"),
                    linewidth=1.5, markersize=6, label=label)

    ax.axhline(y=1, color="gray", linestyle=":", alpha=0.4)
    ax.axvline(x=N_CORES, color="gray", linestyle=":", alpha=0.4)
    ax.set_xscale("log", base=2)
    ax.set_xlabel("Worker pool mérete")
    ax.set_ylabel("p99 / p50 latency arány")
    ax.set_title("H2: Tail latency aránya (p99/p50) — magas érték = instabil viselkedés")
    ax.grid(True, which="both", alpha=0.3)
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"Saved: {out_path}")


# ============================================================
# Számszerű összefoglaló és optimum-keresés
# ============================================================

def print_summary(data):
    print("\n" + "=" * 80)
    print("H2 MÉRÉSI ÖSSZEFOGLALÓ")
    print("=" * 80)

    main_data = data["main"]
    for task in ["cpu", "io"]:
        if task not in main_data:
            continue
        for connections in sorted(main_data[task].keys()):
            print(f"\n--- task={task}, c={connections} ---")
            print(f"{'workers':>8} {'n':>3} {'rps_avg':>10} {'rps_std':>8} "
                  f"{'p50_avg':>10} {'p99_avg':>10} {'p99/p50':>8}")
            print("-" * 70)

            workers_data = main_data[task][connections]
            for w in sorted(workers_data.keys()):
                rows = workers_data[w]
                rps_vals = [r["rps"] for r in rows if r["rps"]]
                p50_vals = [r["p50"] for r in rows if r["p50"]]
                p99_vals = [r["p99"] for r in rows if r["p99"]]

                if rps_vals:
                    rps_avg = np.mean(rps_vals)
                    rps_std = np.std(rps_vals, ddof=1) if len(rps_vals) > 1 else 0
                    p50_avg = np.mean(p50_vals) if p50_vals else float("nan")
                    p99_avg = np.mean(p99_vals) if p99_vals else float("nan")
                    ratio = p99_avg / p50_avg if p50_avg else float("nan")
                    print(f"{w:>8} {len(rows):>3} {rps_avg:>10.1f} {rps_std:>8.1f} "
                          f"{p50_avg:>10.2f} {p99_avg:>10.2f} {ratio:>8.2f}")


def find_optima(data):
    print("\n" + "=" * 80)
    print("OPTIMUM ELEMZÉS")
    print("=" * 80)

    main_data = data["main"]
    for task in ["cpu", "io"]:
        if task not in main_data:
            continue
        for connections in sorted(main_data[task].keys()):
            workers_data = main_data[task][connections]
            workers = sorted(workers_data.keys())

            rps_means = []
            p50_means = []
            for w in workers:
                rows = workers_data[w]
                rps_vals = [r["rps"] for r in rows if r["rps"]]
                p50_vals = [r["p50"] for r in rows if r["p50"]]
                rps_means.append(np.mean(rps_vals) if rps_vals else float("nan"))
                p50_means.append(np.mean(p50_vals) if p50_vals else float("nan"))

            workers = np.array(workers)
            rps_means = np.array(rps_means)
            p50_means = np.array(p50_means)

            try:
                opt_w_rps = workers[np.nanargmax(rps_means)]
                max_rps = np.nanmax(rps_means)
                opt_w_lat = workers[np.nanargmin(p50_means)]
                min_lat = np.nanmin(p50_means)

                print(f"\n--- task={task}, c={connections} ---")
                print(f"  Maximális throughput: {max_rps:.1f} req/s @ "
                      f"workers={opt_w_rps}")
                print(f"  Minimális p50 latency: {min_lat:.2f} ms @ "
                      f"workers={opt_w_lat}")
            except (ValueError, IndexError):
                pass


def validation_check(data):
    """A validációs mérések c=256 vs c=512 telítettségi ellenőrzése."""
    print("\n" + "=" * 80)
    print("VALIDÁCIÓS ELLENŐRZÉS (32 workeren)")
    print("=" * 80)

    val_data = data.get("validation", {})
    for task in ["cpu", "io"]:
        if task not in val_data:
            continue
        cons_list = sorted(val_data[task].keys())
        if len(cons_list) < 2:
            continue

        print(f"\n--- task={task} ---")
        for c in cons_list:
            workers_data = val_data[task][c]
            for w in workers_data:
                rps_vals = [r["rps"] for r in workers_data[w] if r["rps"]]
                p99_vals = [r["p99"] for r in workers_data[w] if r["p99"]]
                if rps_vals:
                    rps_avg = np.mean(rps_vals)
                    p99_avg = np.mean(p99_vals) if p99_vals else float("nan")
                    print(f"  c={c:>4}: rps={rps_avg:.1f}, p99={p99_avg:.1f}ms")

        # Throughput különbség
        c_low, c_high = cons_list[0], cons_list[-1]
        for w in val_data[task][c_low]:
            rps_low = np.mean([r["rps"] for r in val_data[task][c_low][w] if r["rps"]])
            if w in val_data[task][c_high]:
                rps_high = np.mean([r["rps"] for r in val_data[task][c_high][w] if r["rps"]])
                diff = abs(rps_high - rps_low) / rps_low * 100
                if diff < 5:
                    verdict = "TELÍTETT (eltérés < 5%)"
                else:
                    verdict = f"NEM TELÍTETT (eltérés {diff:.1f}%)"
                print(f"  Verdikt: {verdict}")


# ============================================================
# Main
# ============================================================

def main():
    data = load_data(CSV_PATH)

    print_summary(data)
    find_optima(data)
    validation_check(data)

    plot_throughput_vs_workers(data, OUT_DIR / "h2_throughput.png")
    plot_latency_vs_workers(data, OUT_DIR / "h2_latency_p50.png", "p50",
                             " (medián)")
    plot_latency_vs_workers(data, OUT_DIR / "h2_latency_p99.png", "p99",
                             " (tail)")
    plot_tail_latency(data, OUT_DIR / "h2_tail_ratio.png")
    plot_optimum_visualization(data, OUT_DIR / "h2_optimum_panels.png")

    print(f"\nMinden plot: {OUT_DIR}/")


if __name__ == "__main__":
    main()
