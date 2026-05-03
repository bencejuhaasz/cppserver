#!/usr/bin/python3

import csv
import sys
from pathlib import Path
from collections import defaultdict
import numpy as np
import matplotlib.pyplot as plt

if len(sys.argv) < 2:
    print("Usage: plot_h1.py <results_dir>")
    sys.exit(1)

RESULTS_DIR = Path(sys.argv[1])
CSV_PATH = RESULTS_DIR / "wrk_results.csv"
OUT_DIR = RESULTS_DIR / "plots"
OUT_DIR.mkdir(exist_ok=True)

N_CORES = 4  # szerver magjainak száma — Little's Law elemzéshez


# ============================================================
# Adatok beolvasása
# ============================================================

def load_data(csv_path):
    data = defaultdict(list)
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            con = int(row["connections"])
            if row["requests_per_sec"] == "":
                continue
            data[con].append({
                "run": int(row["run"]),
                "rps": float(row["requests_per_sec"]),
                "p50": float(row["latency_p50_ms"]) if row["latency_p50_ms"] else None,
                "p90": float(row["latency_p90_ms"]) if row["latency_p90_ms"] else None,
                "p99": float(row["latency_p99_ms"]) if row["latency_p99_ms"] else None,
                "avg": float(row["latency_avg_ms"]) if row["latency_avg_ms"] else None,
            })
    return data


def aggregate(data, key):
    cons = sorted(data.keys())
    means, stds, ns = [], [], []
    for c in cons:
        vals = [r[key] for r in data[c] if r[key] is not None]
        if vals:
            means.append(np.mean(vals))
            stds.append(np.std(vals, ddof=1) if len(vals) > 1 else 0)
            ns.append(len(vals))
        else:
            means.append(np.nan)
            stds.append(np.nan)
            ns.append(0)
    return np.array(cons), np.array(means), np.array(stds), np.array(ns)


# ============================================================
# Plotok
# ============================================================

def plot_latency_curves(data, out_path):
    fig, ax = plt.subplots(figsize=(10, 6))

    for key, label, color in [
        ("p50", "p50 (medián)", "tab:blue"),
        ("p90", "p90", "tab:orange"),
        ("p99", "p99", "tab:red"),
    ]:
        cons, means, stds, _ = aggregate(data, key)
        ax.errorbar(cons, means, yerr=stds, label=label, color=color,
                    marker="o", capsize=3, linewidth=1.5, markersize=5)

    ax.set_xscale("log", base=2)
    ax.set_yscale("log")
    ax.set_xlabel("Párhuzamos kliensek száma")
    ax.set_ylabel("Latency (ms)")
    ax.set_title("H1: Latency a kliensszám függvényében (CPU-bound, log-log)")
    ax.grid(True, which="both", alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"Saved: {out_path}")


def plot_latency_linear(data, out_path):
    """Lineáris skála — a Little's Law lineáris karakterisztikáját mutatja."""
    fig, ax = plt.subplots(figsize=(10, 6))

    cons, means, stds, _ = aggregate(data, "p50")
    ax.errorbar(cons, means, yerr=stds, label="p50 (medián)",
                color="tab:blue", marker="o", capsize=3, linewidth=1.5, markersize=5)

    cons, means, stds, _ = aggregate(data, "avg")
    ax.errorbar(cons, means, yerr=stds, label="átlag latency",
                color="tab:purple", marker="s", capsize=3, linewidth=1.5, markersize=5)

    # Lineáris fit a c >= N_cores tartományon (telített régió)
    mask = cons >= N_CORES
    if mask.sum() >= 2:
        slope, intercept = np.polyfit(cons[mask], means[mask], 1)
        x_fit = np.linspace(0, cons.max(), 100)
        y_fit = slope * x_fit + intercept
        ax.plot(x_fit, y_fit, "--", color="gray", alpha=0.7,
                label=f"lineáris fit: {slope:.2f}·c + {intercept:.1f} ms")

    ax.set_xlabel("Párhuzamos kliensek száma")
    ax.set_ylabel("Latency (ms)")
    ax.set_title("H1: Latency lineáris karakterisztikája — Little's Law")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"Saved: {out_path}")
    return slope, intercept if mask.sum() >= 2 else (None, None)


def plot_throughput(data, out_path):
    fig, ax = plt.subplots(figsize=(10, 6))

    cons, means, stds, _ = aggregate(data, "rps")
    ax.errorbar(cons, means, yerr=stds, color="tab:green",
                marker="o", capsize=3, linewidth=1.5, markersize=5,
                label="Throughput")

    # Telítettségi vonal
    saturation = np.median(means[cons >= N_CORES * 2])
    ax.axhline(y=saturation, color="gray", linestyle="--", alpha=0.5,
               label=f"telítettségi szint: ~{saturation:.0f} req/s")

    ax.set_xscale("log", base=2)
    ax.set_xlabel("Párhuzamos kliensek száma")
    ax.set_ylabel("Throughput (req/s)")
    ax.set_title("H1: Throughput a kliensszám függvényében")
    ax.grid(True, which="both", alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"Saved: {out_path}")
    return saturation


def plot_combined(data, out_path):
    fig, ax1 = plt.subplots(figsize=(10, 6))

    cons_l, lat_means, lat_stds, _ = aggregate(data, "p99")
    cons_r, rps_means, rps_stds, _ = aggregate(data, "rps")

    color_l = "tab:red"
    ax1.errorbar(cons_l, lat_means, yerr=lat_stds, color=color_l,
                 marker="o", capsize=3, linewidth=1.5, markersize=5,
                 label="p99 latency")
    ax1.set_xlabel("Párhuzamos kliensek száma")
    ax1.set_ylabel("p99 latency (ms)", color=color_l)
    ax1.tick_params(axis="y", labelcolor=color_l)
    ax1.set_xscale("log", base=2)
    ax1.set_yscale("log")
    ax1.grid(True, which="both", alpha=0.3)

    ax2 = ax1.twinx()
    color_r = "tab:green"
    ax2.errorbar(cons_r, rps_means, yerr=rps_stds, color=color_r,
                 marker="s", capsize=3, linewidth=1.5, markersize=5,
                 label="Throughput")
    ax2.set_ylabel("Throughput (req/s)", color=color_r)
    ax2.tick_params(axis="y", labelcolor=color_r)

    fig.suptitle("H1: Throughput és p99 latency együttes viselkedése")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"Saved: {out_path}")


def plot_run_variation(data, out_path):
    fig, ax = plt.subplots(figsize=(10, 6))

    cons = sorted(data.keys())
    for c in cons:
        vals = [r["p99"] for r in data[c] if r["p99"] is not None]
        if vals:
            ax.scatter([c] * len(vals), vals, alpha=0.5, s=20, color="tab:red")

    cons_arr, means, _, _ = aggregate(data, "p99")
    ax.plot(cons_arr, means, color="black", linewidth=2, label="átlag")

    ax.set_xscale("log", base=2)
    ax.set_yscale("log")
    ax.set_xlabel("Párhuzamos kliensek száma")
    ax.set_ylabel("p99 latency (ms)")
    ax.set_title("Diagnosztika: ismétlések szórása p99 latency-ben")
    ax.grid(True, which="both", alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"Saved: {out_path}")


# ============================================================
# Számszerű összefoglaló
# ============================================================

def print_summary(data):
    print("\n=== Mérési összefoglaló ===")
    print(f"{'cons':>6} {'n':>3} {'rps_avg':>10} {'rps_std':>10} "
          f"{'p50_avg':>10} {'p99_avg':>10} {'p99_std':>10}")
    print("-" * 70)

    cons = sorted(data.keys())
    for c in cons:
        rows = data[c]
        rps_vals = [r["rps"] for r in rows if r["rps"] is not None]
        p50_vals = [r["p50"] for r in rows if r["p50"] is not None]
        p99_vals = [r["p99"] for r in rows if r["p99"] is not None]

        rps_avg = np.mean(rps_vals) if rps_vals else float("nan")
        rps_std = np.std(rps_vals, ddof=1) if len(rps_vals) > 1 else 0
        p50_avg = np.mean(p50_vals) if p50_vals else float("nan")
        p99_avg = np.mean(p99_vals) if p99_vals else float("nan")
        p99_std = np.std(p99_vals, ddof=1) if len(p99_vals) > 1 else 0

        print(f"{c:>6} {len(rows):>3} {rps_avg:>10.1f} {rps_std:>10.1f} "
              f"{p50_avg:>10.2f} {p99_avg:>10.2f} {p99_std:>10.2f}")


def little_law_analysis(data, saturation, slope, intercept):
    """Little's Law: L = λ × W értelmezése."""
    print("\n=== Little's Law-elemzés ===")
    if saturation:
        print(f"Telítettségi throughput (λ_max): {saturation:.1f} req/s")
        print(f"  Per mag: {saturation/N_CORES:.1f} req/s/mag "
              f"({N_CORES} mag)")
        service_time = 1000.0 * N_CORES / saturation
        print(f"  Effektív kiszolgálási idő: {service_time:.2f} ms/request")
    if slope:
        print(f"\nLatency lineáris fit (telített régió, c >= {N_CORES}):")
        print(f"  W(c) ≈ {slope:.3f}·c + {intercept:.2f} ms")
        print(f"  Meredekség {slope:.3f} ms/kliens — minden további kliens "
              f"ennyi ms várakozást ad hozzá")
        print(f"  Elméleti meredekség Little's Law-ból: "
              f"1/λ_max × 1000 = {1000.0/saturation:.3f} ms/kliens")


# ============================================================
# Main
# ============================================================

def main():
    data = load_data(CSV_PATH)
    print(f"Beolvasott pontok: {sum(len(v) for v in data.values())}")
    print(f"Kliensszám-értékek: {sorted(data.keys())}")

    print_summary(data)

    plot_latency_curves(data, OUT_DIR / "h1_latency_loglog.png")
    slope, intercept = plot_latency_linear(data, OUT_DIR / "h1_latency_linear.png")
    saturation = plot_throughput(data, OUT_DIR / "h1_throughput.png")
    plot_combined(data, OUT_DIR / "h1_combined.png")
    plot_run_variation(data, OUT_DIR / "h1_diagnostic.png")

    little_law_analysis(data, saturation, slope, intercept)

    print(f"\nMinden plot: {OUT_DIR}/")


if __name__ == "__main__":
    main()
