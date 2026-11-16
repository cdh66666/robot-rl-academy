"""Offline educational first-order actuator identification, using synthetic data.

Only Python's standard library is needed. This script does not access hardware.
"""

from __future__ import annotations

import csv
import json
import math
import random
from pathlib import Path
HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "output"
DT = 0.02
SAMPLES = 1001
SPLIT = 600
SEED = 20261116

# These are known values of a synthetic demonstration, not hardware measurements.
SYNTHETIC_TAU = 0.24
SYNTHETIC_DELAY_STEPS = 8
SYNTHETIC_NOISE_SD = 0.003


def target_at(time_s: float) -> float:
    """A sequence with several transitions, including unseen validation steps."""
    changes = [
        (0.0, 0.0), (1.0, 0.28), (2.2, -0.22), (3.5, 0.15),
        (5.0, -0.30), (6.5, 0.10), (7.8, -0.12), (9.0, 0.25),
        (10.2, 0.05), (12.0, -0.27), (13.4, 0.21), (14.8, -0.10),
        (16.0, 0.30), (17.5, -0.20), (19.0, 0.08),
    ]
    value = 0.0
    for start, target in changes:
        if time_s + 1e-9 < start:
            break
        value = target
    return value


def simulate_segment(
    targets: list[float], start: int, stop: int, initial: float,
    tau_s: float, delay_steps: int,
) -> list[float]:
    """Open-loop prediction; targets before start supply delay history."""
    alpha = 1.0 - math.exp(-DT / tau_s)
    predictions = [initial]
    position = initial
    for index in range(start + 1, stop):
        delayed_index = max(0, index - 1 - delay_steps)
        position += alpha * (targets[delayed_index] - position)
        predictions.append(position)
    return predictions


def write_synthetic_csv(path: Path) -> None:
    times = [i * DT for i in range(SAMPLES)]
    targets = [target_at(t) for t in times]
    truth = simulate_segment(targets, 0, SAMPLES, 0.0, SYNTHETIC_TAU, SYNTHETIC_DELAY_STEPS)
    rng = random.Random(SEED)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["data_kind", "time_s", "command_target_rad", "position_measured_rad"])
        for time_s, target, true_position in zip(times, targets, truth):
            measurement = true_position + rng.gauss(0.0, SYNTHETIC_NOISE_SD)
            writer.writerow(["synthetic", f"{time_s:.3f}", f"{target:.6f}", f"{measurement:.6f}"])


def read_csv(path: Path) -> tuple[list[float], list[float], list[float]]:
    times, commands, positions = [], [], []
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["data_kind"] != "synthetic":
                raise ValueError("This bundled exercise accepts synthetic data only.")
            times.append(float(row["time_s"]))
            commands.append(float(row["command_target_rad"]))
            positions.append(float(row["position_measured_rad"]))
    if len(times) != SAMPLES:
        raise ValueError("Unexpected number of samples.")
    if any(abs((times[i] - times[i - 1]) - DT) > 1e-8 for i in range(1, len(times))):
        raise ValueError("The demonstration requires a uniform, 20 ms time step.")
    if not all(math.isfinite(x) for x in commands + positions):
        raise ValueError("Non-finite data are not allowed.")
    return times, commands, positions


def metrics(actual: list[float], predicted: list[float]) -> dict[str, float]:
    if len(actual) != len(predicted) or not actual:
        raise ValueError("Metric arrays must be the same nonzero length.")
    errors = [p - y for y, p in zip(actual, predicted)]
    return {
        "rmse_rad": math.sqrt(sum(e * e for e in errors) / len(errors)),
        "mae_rad": sum(abs(e) for e in errors) / len(errors),
        "max_abs_error_rad": max(abs(e) for e in errors),
    }


def fit_train_only(commands: list[float], measured: list[float]) -> tuple[float, int, list[float]]:
    """Grid search on the first 12 s only. The last 8 s remain unseen."""
    best = (math.inf, 0.0, 0, [])
    # Delays are identifiable only at this 20 ms sampling resolution in this grid.
    for delay in range(0, 21):
        for candidate in range(12, 121):  # tau from 0.060 through 0.600 s in 0.005 s steps
            tau = candidate * 0.005
            predictions = simulate_segment(commands, 0, SPLIT, measured[0], tau, delay)
            score = metrics(measured[1:SPLIT], predictions[1:])["rmse_rad"]
            if score < best[0]:
                best = (score, tau, delay, predictions)
    return best[1], best[2], best[3]


def line_path(values: list[float], start: int, x, y) -> str:
    return " ".join(("M" if i == 0 else "L") + f"{x((start+i)*DT):.1f},{y(v):.1f}" for i, v in enumerate(values))


def write_svg(path: Path, times: list[float], commands: list[float], measured: list[float],
              train_prediction: list[float], validation_prediction: list[float],
              tau_s: float, delay_s: float, validation_rmse: float) -> None:
    width, height = 1280, 620
    left, right, top, bottom = 95, 1240, 130, 525
    x = lambda t: left + (right - left) * t / times[-1]
    y = lambda v: bottom - (v + 0.42) / 0.84 * (bottom - top)
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="1280" height="620" fill="#f7faf9"/>',
        '<text x="95" y="48" fill="#15363c" font-family="Microsoft YaHei, sans-serif" font-size="28" font-weight="700">合成伺服响应：拟合与留出验证</text>',
        '<text x="95" y="80" fill="#567278" font-family="Microsoft YaHei, sans-serif" font-size="17">示例数据由程序生成，不代表真实电机。有效延迟并不等于纯通信延迟。</text>',
        f'<rect x="{x(12):.1f}" y="{top}" width="{right-x(12):.1f}" height="{bottom-top}" fill="#e8f2ee"/>',
    ]
    for tick in range(0, 21, 2):
        xp = x(tick)
        lines.append(f'<line x1="{xp:.1f}" y1="{top}" x2="{xp:.1f}" y2="{bottom}" stroke="#d9e5e2"/>')
        lines.append(f'<text x="{xp:.1f}" y="{bottom+27}" text-anchor="middle" fill="#617b7d" font-family="sans-serif" font-size="15">{tick}</text>')
    for tick in [-0.4, -0.2, 0.0, 0.2, 0.4]:
        yp = y(tick)
        lines.append(f'<line x1="{left}" y1="{yp:.1f}" x2="{right}" y2="{yp:.1f}" stroke="#d9e5e2"/>')
        lines.append(f'<text x="{left-12}" y="{yp+5:.1f}" text-anchor="end" fill="#617b7d" font-family="sans-serif" font-size="15">{tick:.1f}</text>')
    lines += [
        f'<line x1="{x(12):.1f}" y1="{top}" x2="{x(12):.1f}" y2="{bottom}" stroke="#8caaa2" stroke-width="2" stroke-dasharray="7 6"/>',
        '<text x="120" y="155" fill="#587572" font-family="Microsoft YaHei, sans-serif" font-size="18">拟合段（0–12 秒）</text>',
        f'<text x="{x(12)+20:.1f}" y="155" fill="#39715e" font-family="Microsoft YaHei, sans-serif" font-size="18">留出验证段（12–20 秒）</text>',
        f'<path d="{line_path(commands, 0, x, y)}" fill="none" stroke="#e89968" stroke-width="2.5" stroke-dasharray="8 5"/>',
        f'<path d="{line_path(measured, 0, x, y)}" fill="none" stroke="#788d91" stroke-width="1.5" opacity="0.72"/>',
        f'<path d="{line_path(train_prediction, 0, x, y)}" fill="none" stroke="#087f83" stroke-width="3"/>',
        f'<path d="{line_path(validation_prediction, SPLIT, x, y)}" fill="none" stroke="#087f83" stroke-width="3"/>',
        f'<text x="{(left+right)/2:.1f}" y="{bottom+57}" text-anchor="middle" fill="#405f64" font-family="Microsoft YaHei, sans-serif" font-size="17">时间（秒）</text>',
        '<text x="20" y="110" fill="#405f64" font-family="Microsoft YaHei, sans-serif" font-size="16">角度 rad</text>',
        '<line x1="100" y1="110" x2="138" y2="110" stroke="#e89968" stroke-width="3" stroke-dasharray="8 5"/><text x="146" y="115" fill="#405f64" font-family="Microsoft YaHei, sans-serif" font-size="16">目标</text>',
        '<line x1="245" y1="110" x2="283" y2="110" stroke="#788d91" stroke-width="2"/><text x="291" y="115" fill="#405f64" font-family="Microsoft YaHei, sans-serif" font-size="16">合成测量</text>',
        '<line x1="430" y1="110" x2="468" y2="110" stroke="#087f83" stroke-width="3"/><text x="476" y="115" fill="#405f64" font-family="Microsoft YaHei, sans-serif" font-size="16">模型预测</text>',
        f'<text x="710" y="115" fill="#087f83" font-family="Microsoft YaHei, sans-serif" font-size="16">估计 τ={tau_s:.3f} s · 有效延迟={delay_s:.3f} s · 验证 RMSE={validation_rmse:.5f} rad</text>',
        '<text x="95" y="607" fill="#607a7d" font-family="Microsoft YaHei, sans-serif" font-size="15">验证段首个测量用于初始化，之后逐步开环预测；参数只由拟合段计算。</text>',
        '</svg>',
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT.mkdir(exist_ok=True)
    csv_path = OUTPUT / "synthetic_servo_response.csv"
    write_synthetic_csv(csv_path)
    times, commands, measured = read_csv(csv_path)
    tau, delay_steps, train_pred = fit_train_only(commands, measured)
    # The first held-out measured position is used only to initialize this
    # independent rollout; remaining validation samples do not tune parameters.
    validation_pred = simulate_segment(commands, SPLIT, len(times), measured[SPLIT], tau, delay_steps)
    train_metrics = metrics(measured[1:SPLIT], train_pred[1:])
    validation_metrics = metrics(measured[SPLIT+1:], validation_pred[1:])
    report = {
        "data_provenance": "synthetic; generated by this script; no hardware access",
        "seed": SEED,
        "sampling_interval_s": DT,
        "training_range_s": [times[0], times[SPLIT-1]],
        "validation_range_s": [times[SPLIT], times[-1]],
        "validation_protocol": "Initialize with first validation measurement; predict all following samples open loop. No validation sample is used for parameter fitting.",
        "model": "y[k+1] = y[k] + (1-exp(-dt/tau)) * (u[k-delay_steps]-y[k])",
        "search_grid": {"tau_min_s": 0.060, "tau_max_s": 0.600, "tau_step_s": 0.005,
                        "delay_min_s": 0.0, "delay_max_s": 0.4, "delay_step_s": DT},
        "synthetic_generating_parameters": {"tau_s": SYNTHETIC_TAU,
                                            "effective_delay_s": SYNTHETIC_DELAY_STEPS * DT,
                                            "measurement_noise_standard_deviation_rad": SYNTHETIC_NOISE_SD},
        "estimated_parameters": {"tau_s": tau, "effective_delay_s": delay_steps * DT},
        "training_metrics": train_metrics,
        "held_out_metrics": validation_metrics,
        "warning": "Synthetic example only. Effective response delay can include sampling, filtering, communication, drive and actuator effects; it is not a pure communication delay or a real motor measurement.",
    }
    (OUTPUT / "identification_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_svg(OUTPUT / "response_fit.svg", times, commands, measured, train_pred, validation_pred,
              tau, delay_steps * DT, validation_metrics["rmse_rad"])
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\nWritten: {csv_path}, {OUTPUT / 'identification_report.json'}, {OUTPUT / 'response_fit.svg'}")


if __name__ == "__main__":
    main()
