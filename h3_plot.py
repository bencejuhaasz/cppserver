#!/usr/bin/python3

import csv
import sys
from pathlib import Path
from collections import defaultdict
import numpy as np
import matplotlib.pyplot as plt

if len(sys.argv) < 2:
    print("Usage: plot_h3.py <results_dir>")
    sys.exit(1)

RESULTS_DIR = Path(sys.argv[1])
CSV_PATH = RESULTS_DIR / "wrk_results.csv"
OUT_DIR = RESULTS_DIR / "plots"
OUT_DIR.mkdir(exist_ok=True)


# Színek és stílusok
TASK_STYLES = {
    "cpu": {"color": "tab:blue", "marker": "o", "label": "CPU-bound"},
    "io": {"color": "tab:red", "marker": "s", "label": "IO-bound"},
}

LINE_STYLES = {
    128: "-",
    256: "--",
}


# ============================================================
# Adat beolvasás
# ============================================================

def load_data(csv_path):
    """task -> connections -> queue_size -> list of measurements."""
    data = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

    with open(csv_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["requests_per_sec"] == "":
                continue

            task = row["task"]
            queue_size = int(row["queue_size"])
            connections = int(row["connections"])

            # Összes hibaszám
            errors = (int(row["socket_errors_connect"] or 0) +
                      int(row["socket_errors_read"] or 0) +
                      int(row["socket_errors_write"] or 0) +
                      int(row["socket_errors_timeout"] or 0))
            rejects = int(row["socket_errors_read"] or 0)
            total_requests = int(row["total_requests"] or 0)
            total_attempts = total_requests + errors
            reject_rate = (rejects / total_attempts * 100) if total_attempts > 0 else 0

            data[task][connections][queue_size].append({
                "run": int(row["run"]),
                "rps": float(row["requests_per_sec"]),
                "p50": float(row["latency_p50_ms"]) if row["latency_p50_ms"] else None,
                "p90": float(row["latency_p90_ms"]) if row["latency_p90_ms"] else None,
                "p99": float(row["latency_p99_ms"]) if row["latency_p99_ms"] else None,
                "avg": float(row["latency_avg_ms"]) if row["latency_avg_ms"] else None,
                "rejects": rejects,
                "timeouts": int(row["socket_errors_timeout"] or 0),
                "total_requests": total_requests,
                "reject_rate_pct": reject_rate,
            })
    return data


def aggregate_by_queue(data_per_queue, key):
    """queue_size -> átlag és szórás a megadott metrikára."""
    queues = sorted(data_per_queue.keys())
    means, stds = [], []
    for q in queues:
        vals = [r[key] for r in data_per_queue[q] if r[key] is not None]
        if vals:
            means.append(np.mean(vals))
            stds.append(np.std(vals, ddof=1) if len(vals) > 1 else 0)
        else:
            means.append(np.nan)
            stds.append(np.nan)
    return np.array(queues), np.array(means), np.array(stds)


# ============================================================
# Plotok
# ============================================================

def plot_throughput_vs_queue(data, out_path):
    """Throughput a queue méret függvényében."""
    fig, ax = plt.subplots(figsize=(11, 6.5))

    for task in ["cpu", "io"]:
        if task not in data:
            continue
        style = TASK_STYLES[task]
        for connections in sorted(data[task].keys()):
            queues, means, stds = aggregate_by_queue(data[task][connections], "rps")
            label = f"{style['label']}, c={connections}"
            ax.errorbar(queues, means, yerr=stds,
                        color=style["color"], marker=style["marker"],
                        linestyle=LINE_STYLES.get(connections, "-"),
                        capsize=3, linewidth=1.5, markersize=6,
                        label=label)

    ax.set_xscale("log", base=2)
    ax.set_xlabel("Queue méret")
    ax.set_ylabel("Throughput (sikeres req/s)")
    ax.set_title("H3: Throughput a queue méret függvényében")
    ax.grid(True, which="both", alpha=0.3)
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"Saved: {out_path}")


def plot_latency_vs_queue(data, out_path, latency_key="p99",
                           title_suffix=""):
    """Latency a queue méret függvényében."""
    fig, ax = plt.subplots(figsize=(11, 6.5))

    for task in ["cpu", "io"]:
        if task not in data:
            continue
        style = TASK_STYLES[task]
        for connections in sorted(data[task].keys()):
            queues, means, stds = aggregate_by_queue(
                data[task][connections], latency_key
            )
            label = f"{style['label']}, c={connections}"
            ax.errorbar(queues, means, yerr=stds,
                        color=style["color"], marker=style["marker"],
                        linestyle=LINE_STYLES.get(connections, "-"),
                        capsize=3, linewidth=1.5, markersize=6,
                        label=label)

    ax.set_xscale("log", base=2)
    ax.set_yscale("log")
    ax.set_xlabel("Queue méret")
    ax.set_ylabel(f"{latency_key} latency (ms)")
    ax.set_title(f"H3: {latency_key} latency a queue méret függvényében"
                 f"{title_suffix}")
    ax.grid(True, which="both", alpha=0.3)
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"Saved: {out_path}")


def plot_reject_rate(data, out_path):
    """Reject ráta (%) a queue méret függvényében."""
    fig, ax = plt.subplots(figsize=(11, 6.5))

    for task in ["cpu", "io"]:
        if task not in data:
            continue
        style = TASK_STYLES[task]
        for connections in sorted(data[task].keys()):
            queues, means, stds = aggregate_by_queue(
                data[task][connections], "reject_rate_pct"
            )
            label = f"{style['label']}, c={connections}"
            ax.errorbar(queues, means, yerr=stds,
                        color=style["color"], marker=style["marker"],
                        linestyle=LINE_STYLES.get(connections, "-"),
                        capsize=3, linewidth=1.5, markersize=6,
                        label=label)

    ax.set_xscale("log", base=2)
    ax.set_xlabel("Queue méret")
    ax.set_ylabel("Reject ráta (%)")
    ax.set_title("H3: Reject ráta a queue méret függvényében")
    ax.grid(True, which="both", alpha=0.3)
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"Saved: {out_path}")


def plot_tradeoff(data, out_path):
    """A H3 hipotézis központi ábrája: latency és reject ráta együtt
    minden queue méreten — vizuálisan láthatóvá teszi a kompromisszumot."""
    fig, axes = plt.subplots(2, 2, figsize=(14, 9), squeeze=False)

    tasks = ["cpu", "io"]
    all_cons = sorted(set(c for t in data.values() for c in t.keys()))

    for i, task in enumerate(tasks):
        if task not in data:
            continue
        for j, connections in enumerate(all_cons):
            if connections not in data[task]:
                continue
            ax = axes[i][j]
            ax2 = ax.twinx()

            queues, p99_means, p99_stds = aggregate_by_queue(
                data[task][connections], "p99"
            )
            queues, reject_means, reject_stds = aggregate_by_queue(
                data[task][connections], "reject_rate_pct"
            )

            l1 = ax.errorbar(queues, p99_means, yerr=p99_stds,
                              color="tab:red", marker="o", capsize=3,
                              linewidth=1.5, markersize=5,
                              label="p99 latency")
            l2 = ax2.errorbar(queues, reject_means, yerr=reject_stds,
                               color="tab:orange", marker="s", capsize=3,
                               linewidth=1.5, markersize=5,
                               label="reject ráta")

            ax.set_xscale("log", base=2)
            ax.set_yscale("log")
            ax.set_xlabel("Queue méret")
            ax.set_ylabel("p99 latency (ms)", color="tab:red")
            ax2.set_ylabel("Reject ráta (%)", color="tab:orange")
            ax.tick_params(axis="y", labelcolor="tab:red")
            ax2.tick_params(axis="y", labelcolor="tab:orange")
            ax.set_title(f"{TASK_STYLES[task]['label']}, c={connections}")
            ax.grid(True, which="both", alpha=0.3)

            # Optimum jelölése — minimális p99, ahol a reject < 1%
            try:
                valid_mask = reject_means < 1.0
                if valid_mask.any():
                    valid_p99 = p99_means.copy()
                    valid_p99[~valid_mask] = np.inf
                    opt_idx = np.nanargmin(valid_p99)
                    opt_q = queues[opt_idx]
                    opt_p99 = p99_means[opt_idx]
                    ax.axvline(x=opt_q, color="green", linestyle=":", alpha=0.5)
                    ax.annotate(f"sweet spot: q={opt_q}",
                                xy=(opt_q, opt_p99),
                                xytext=(8, 10), textcoords="offset points",
                                fontsize=9, color="green")
            except (ValueError, IndexError):
                pass

    fig.suptitle("H3: Latency × reject ráta kompromisszum a queue méret szerint",
                 fontsize=13)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"Saved: {out_path}")


def plot_effective_throughput(data, out_path):
    """Effektív throughput = sikeres req/s × (1 - reject_rate).
    Más szóval: a felhasználói szempontból elérhető hasznos throughput."""
    fig, ax = plt.subplots(figsize=(11, 6.5))

    for task in ["cpu", "io"]:
        if task not in data:
            continue
        style = TASK_STYLES[task]
        for connections in sorted(data[task].keys()):
            queues = sorted(data[task][connections].keys())
            eff_means = []
            eff_stds = []
            for q in queues:
                rows = data[task][connections][q]
                effs = []
                for r in rows:
                    if r["rps"] is not None:
                        # Az rps már a sikereseket méri — ennek átlaga az effektív
                        effs.append(r["rps"])
                if effs:
                    eff_means.append(np.mean(effs))
                    eff_stds.append(np.std(effs, ddof=1) if len(effs) > 1 else 0)
                else:
                    eff_means.append(np.nan)
                    eff_stds.append(np.nan)

            label = f"{style['label']}, c={connections}"
            ax.errorbar(queues, eff_means, yerr=eff_stds,
                        color=style["color"], marker=style["marker"],
                        linestyle=LINE_STYLES.get(connections, "-"),
                        capsize=3, linewidth=1.5, markersize=6,
                        label=label)

    ax.set_xscale("log", base=2)
    ax.set_xlabel("Queue méret")
    ax.set_ylabel("Effektív throughput (sikeres req/s)")
    ax.set_title("H3: Effektív (sikeres) throughput a queue méret függvényében")
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
    print("\n" + "=" * 95)
    print("H3 MÉRÉSI ÖSSZEFOGLALÓ")
    print("=" * 95)

    for task in ["cpu", "io"]:
        if task not in data:
            continue
        for connections in sorted(data[task].keys()):
            print(f"\n--- task={task}, c={connections} ---")
            print(f"{'queue':>6} {'n':>3} {'rps_avg':>10} {'p50':>10} "
                  f"{'p99':>10} {'reject%':>10} {'rejects':>10}")
            print("-" * 70)

            for q in sorted(data[task][connections].keys()):
                rows = data[task][connections][q]
                rps_vals = [r["rps"] for r in rows if r["rps"]]
                p50_vals = [r["p50"] for r in rows if r["p50"]]
                p99_vals = [r["p99"] for r in rows if r["p99"]]
                reject_vals = [r["reject_rate_pct"] for r in rows]
                reject_count_vals = [r["rejects"] for r in rows]

                if rps_vals:
                    print(f"{q:>6} {len(rows):>3} "
                          f"{np.mean(rps_vals):>10.1f} "
                          f"{np.mean(p50_vals):>10.2f} "
                          f"{np.mean(p99_vals):>10.2f} "
                          f"{np.mean(reject_vals):>10.2f} "
                          f"{np.mean(reject_count_vals):>10.0f}")


def find_optimum(data):
    print("\n" + "=" * 95)
    print("H3 OPTIMUM ELEMZÉS")
    print("=" * 95)
    print("Optimum kritérium: minimális p99 latency, ahol reject ráta < 1%")

    for task in ["cpu", "io"]:
        if task not in data:
            continue
        for connections in sorted(data[task].keys()):
            queues = sorted(data[task][connections].keys())
            p99_means = []
            reject_means = []
            for q in queues:
                rows = data[task][connections][q]
                p99_vals = [r["p99"] for r in rows if r["p99"]]
                reject_vals = [r["reject_rate_pct"] for r in rows]
                p99_means.append(np.mean(p99_vals) if p99_vals else float("nan"))
                reject_means.append(np.mean(reject_vals) if reject_vals else 0)

            queues = np.array(queues)
            p99_means = np.array(p99_means)
            reject_means = np.array(reject_means)

            # Minimum p99, ahol reject < 1%
            valid = reject_means < 1.0
            print(f"\n--- task={task}, c={connections} ---")
            if valid.any():
                p99_filtered = p99_means.copy()
                p99_filtered[~valid] = np.inf
                opt_idx = np.nanargmin(p99_filtered)
                opt_q = queues[opt_idx]
                opt_p99 = p99_means[opt_idx]
                opt_reject = reject_means[opt_idx]
                print(f"  Sweet spot: queue={opt_q}, p99={opt_p99:.1f}ms, "
                      f"reject={opt_reject:.2f}%")
            else:
                print(f"  Nincs olyan queue méret, ahol a reject < 1% lenne!")

            # Bufferbloat hatás: legnagyobb queue p99 vs sweet spot p99
            max_q_idx = -1
            max_p99 = p99_means[max_q_idx]
            print(f"  Legnagyobb queue ({queues[max_q_idx]}): "
                  f"p99={max_p99:.1f}ms, reject={reject_means[max_q_idx]:.2f}%")


# ============================================================
# Main
# ============================================================

def main():
    data = load_data(CSV_PATH)

    print_summary(data)
    find_optimum(data)

    plot_throughput_vs_queue(data, OUT_DIR / "h3_throughput.png")
    plot_latency_vs_queue(data, OUT_DIR / "h3_latency_p50.png", "p50",
                           " (medián)")
    plot_latency_vs_queue(data, OUT_DIR / "h3_latency_p99.png", "p99",
                           " (tail)")
    plot_reject_rate(data, OUT_DIR / "h3_reject_rate.png")
    plot_effective_throughput(data, OUT_DIR / "h3_effective_throughput.png")
    plot_tradeoff(data, OUT_DIR / "h3_tradeoff.png")

    print(f"\nMinden plot: {OUT_DIR}/")


if __name__ == "__main__":
    main()
