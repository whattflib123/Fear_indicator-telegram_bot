#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import requests


FNG_API_URL = "https://api.alternative.me/fng/"
COINGECKO_MARKET_CHART_URL = "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart"
LOOKBACK_DAYS = 183


@dataclass
class FearGreedPoint:
    timestamp: datetime
    value: int
    classification: str


def classify_zone(value: int) -> str:
    if value < 20:
        return "極度恐懼 😱"
    if value < 40:
        return "恐懼 😟"
    if value < 60:
        return "中性 😐"
    if value < 80:
        return "貪婪 🙂"
    return "極度貪婪 🤑"

def load_dotenv(dotenv_path: Path) -> None:
    if not dotenv_path.exists():
        return

    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        os.environ.setdefault(key, value)


def fetch_fear_greed_history() -> List[FearGreedPoint]:
    params = {"limit": 0, "format": "json"}
    response = requests.get(FNG_API_URL, params=params, timeout=20)
    response.raise_for_status()

    payload = response.json()
    rows = payload.get("data", [])
    points: List[FearGreedPoint] = []

    for row in rows:
        ts = datetime.fromtimestamp(int(row["timestamp"]), tz=timezone.utc)
        points.append(
            FearGreedPoint(
                timestamp=ts,
                value=int(row["value"]),
                classification=row.get("value_classification", "Unknown"),
            )
        )

    points.sort(key=lambda p: p.timestamp)
    return points


def fetch_btc_price_history(days: int = LOOKBACK_DAYS) -> List[Tuple[datetime, float]]:
    params = {"vs_currency": "usd", "days": str(days), "interval": "daily"}
    response = requests.get(COINGECKO_MARKET_CHART_URL, params=params, timeout=20)
    response.raise_for_status()

    payload = response.json()
    prices = payload.get("prices", [])
    points: List[Tuple[datetime, float]] = []
    for timestamp_ms, price in prices:
        dt = datetime.fromtimestamp(int(timestamp_ms) / 1000, tz=timezone.utc)
        points.append((dt, float(price)))

    points.sort(key=lambda p: p[0])
    return points


def filter_recent(points: List[FearGreedPoint], days: int = LOOKBACK_DAYS) -> List[FearGreedPoint]:
    if not points:
        return []
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days)
    recent = [point for point in points if point.timestamp >= cutoff]
    return recent if recent else points


def save_chart(
    points: List[FearGreedPoint],
    btc_prices: List[Tuple[datetime, float]],
    output_path: Path,
) -> None:
    dates = [point.timestamp for point in points]
    values = [point.value for point in points]
    btc_dates = [point[0] for point in btc_prices]
    btc_values = [point[1] for point in btc_prices]

    plt.style.use("seaborn-v0_8-whitegrid")
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.axhspan(0, 20, facecolor="#ff4d4f", alpha=0.18)
    ax.axhspan(20, 40, facecolor="#ff9f43", alpha=0.15)
    ax.axhspan(40, 60, facecolor="#ced4da", alpha=0.14)
    ax.axhspan(60, 80, facecolor="#95de64", alpha=0.14)
    ax.axhspan(80, 100, facecolor="#52c41a", alpha=0.18)
    ax.plot(dates, values, linewidth=2, color="#1f77b4", label="Fear & Greed Index")
    ax.fill_between(dates, values, alpha=0.2, color="#1f77b4")
    ax.set_title("Crypto Fear & Greed Index (BTC) - Last 6 Months")
    ax.set_xlabel("Date")
    ax.set_ylabel("Index (0-100)")
    ax.set_ylim(0, 100)

    ax2 = ax.twinx()
    ax2.plot(btc_dates, btc_values, linewidth=1.8, color="#f59f00", alpha=0.9, label="BTC Price (USD)")
    ax2.set_ylabel("BTC Price (USD)")

    ax.text(0.01, 10, "Extreme Fear", transform=ax.get_yaxis_transform(), va="center", fontsize=9, color="#8b0000")
    ax.text(0.01, 30, "Fear", transform=ax.get_yaxis_transform(), va="center", fontsize=9, color="#a85d00")
    ax.text(0.01, 50, "Neutral", transform=ax.get_yaxis_transform(), va="center", fontsize=9, color="#495057")
    ax.text(0.01, 70, "Greed", transform=ax.get_yaxis_transform(), va="center", fontsize=9, color="#2b8a3e")
    ax.text(0.01, 90, "Extreme Greed", transform=ax.get_yaxis_transform(), va="center", fontsize=9, color="#1b5e20")

    lines_1, labels_1 = ax.get_legend_handles_labels()
    lines_2, labels_2 = ax2.get_legend_handles_labels()
    ax.legend(lines_1 + lines_2, labels_1 + labels_2, loc="upper left")

    fig.autofmt_xdate()
    fig.tight_layout()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150)
    plt.close(fig)


def _build_daily_range(start: date, end: date) -> List[date]:
    total_days = (end - start).days
    return [start + timedelta(days=offset) for offset in range(total_days + 1)]


def _forward_fill_by_day(series: Dict[date, float], days: List[date]) -> Dict[date, float]:
    filled: Dict[date, float] = {}
    last_value: Optional[float] = None

    for day in days:
        if day in series:
            last_value = series[day]
        if last_value is not None:
            filled[day] = last_value

    return filled


def _daily_returns(series: Dict[date, float], days: List[date]) -> Dict[date, float]:
    returns: Dict[date, float] = {}
    for idx in range(1, len(days)):
        prev_day = days[idx - 1]
        day = days[idx]
        prev_value = series.get(prev_day)
        value = series.get(day)
        if prev_value is None or value is None or prev_value == 0:
            continue
        returns[day] = (value - prev_value) / prev_value
    return returns


def _average_ranks(values: List[float]) -> List[float]:
    indexed = list(enumerate(values))
    indexed.sort(key=lambda item: item[1])

    ranks = [0.0] * len(values)
    i = 0
    while i < len(indexed):
        j = i + 1
        while j < len(indexed) and indexed[j][1] == indexed[i][1]:
            j += 1
        avg_rank = (i + 1 + j) / 2.0
        for k in range(i, j):
            original_index = indexed[k][0]
            ranks[original_index] = avg_rank
        i = j

    return ranks


def _pearson_correlation(xs: List[float], ys: List[float]) -> Optional[float]:
    if len(xs) != len(ys) or len(xs) < 2:
        return None

    n = len(xs)
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n

    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    var_x = sum((x - mean_x) ** 2 for x in xs)
    var_y = sum((y - mean_y) ** 2 for y in ys)

    if var_x == 0 or var_y == 0:
        return None

    return cov / (var_x ** 0.5 * var_y ** 0.5)


def _prepare_aligned_daily_returns(
    recent_points: List[FearGreedPoint],
    btc_prices: List[Tuple[datetime, float]],
) -> Optional[Tuple[List[float], List[float]]]:
    if len(recent_points) < 3 or len(btc_prices) < 3:
        return None

    fng_by_day: Dict[date, float] = {point.timestamp.date(): float(point.value) for point in recent_points}
    btc_by_day: Dict[date, float] = {timestamp.date(): price for timestamp, price in btc_prices}

    overlap_days = sorted(set(fng_by_day.keys()) & set(btc_by_day.keys()))
    if len(overlap_days) < 3:
        return None

    day_range = _build_daily_range(overlap_days[0], overlap_days[-1])
    fng_filled = _forward_fill_by_day(fng_by_day, day_range)
    btc_filled = _forward_fill_by_day(btc_by_day, day_range)

    fng_returns = _daily_returns(fng_filled, day_range)
    btc_returns = _daily_returns(btc_filled, day_range)

    aligned_days = sorted(set(fng_returns.keys()) & set(btc_returns.keys()))
    if len(aligned_days) < 3:
        return None

    fng_values = [fng_returns[day] for day in aligned_days]
    btc_values = [btc_returns[day] for day in aligned_days]
    return fng_values, btc_values


def calculate_spearman_correlation(
    recent_points: List[FearGreedPoint],
    btc_prices: List[Tuple[datetime, float]],
) -> Optional[float]:
    aligned_returns = _prepare_aligned_daily_returns(recent_points, btc_prices)
    if aligned_returns is None:
        return None

    fng_values, btc_values = aligned_returns

    rank_fng = _average_ranks(fng_values)
    rank_btc = _average_ranks(btc_values)
    return _pearson_correlation(rank_fng, rank_btc)


def describe_correlation(correlation: Optional[float]) -> str:
    if correlation is None:
        return "N/A（資料不足）"

    abs_corr = abs(correlation)
    if abs_corr < 0.2:
        strength = "極弱"
    elif abs_corr < 0.4:
        strength = "偏弱"
    elif abs_corr < 0.6:
        strength = "中等"
    elif abs_corr < 0.8:
        strength = "偏強"
    else:
        strength = "極強"

    if correlation > 0:
        direction = "正相關 📈"
    elif correlation < 0:
        direction = "負相關 📉"
    else:
        direction = "無明顯方向 ➖"

    return f"{correlation:.2f}（{strength}. {direction}）"

def build_message(
    latest: FearGreedPoint,
    recent_points: List[FearGreedPoint],
    spearman_text: str,
) -> str:
    latest_zone = classify_zone(latest.value)
    previous_value = recent_points[-2].value if len(recent_points) >= 2 else latest.value
    delta = latest.value - previous_value
    if delta > 0:
        delta_text = f"+{delta}"
    elif delta < 0:
        delta_text = f"{delta}"
    else:
        delta_text = "0"

    latest_date = latest.timestamp.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return "\n".join(
        [
            "📊 BTC 市場情緒更新",
            f"🧭 最新指數：{latest.value}（{latest_zone}）",
            f"🔁 與前次相比：{delta_text}",
            f"🕒 時間：{latest_date}",
            f"🔗 Spearman相關性：{spearman_text}",
        ]
    )

def send_telegram_message(bot_token: str, chat_id: str, text: str) -> None:
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    response = requests.post(
        url,
        data={"chat_id": chat_id, "text": text},
        timeout=20,
    )
    response.raise_for_status()


def send_telegram_photo(bot_token: str, chat_id: str, image_path: Path, caption: str) -> None:
    url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
    with image_path.open("rb") as image_file:
        response = requests.post(
            url,
            data={"chat_id": chat_id, "caption": caption},
            files={"photo": image_file},
            timeout=30,
        )
    response.raise_for_status()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch BTC fear/greed data, generate chart, and send to Telegram.",
    )
    parser.add_argument(
        "--bot-token",
        default=os.getenv("TELEGRAM_BOT_TOKEN", ""),
        help="Telegram Bot Token, defaults to TELEGRAM_BOT_TOKEN",
    )
    parser.add_argument(
        "--chat-id",
        default=os.getenv("TELEGRAM_CHAT_ID", ""),
        help="Telegram Chat ID, defaults to TELEGRAM_CHAT_ID",
    )
    parser.add_argument(
        "--chart-path",
        default="output/fear_greed_last_6_months.png",
        help="Output chart path",
    )
    return parser.parse_args()


def main() -> None:
    project_root = Path(__file__).resolve().parent.parent
    load_dotenv(project_root / ".env")
    args = parse_args()

    if not args.bot_token or not args.chat_id:
        raise SystemExit("Please provide TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID.")

    all_points = fetch_fear_greed_history()
    if not all_points:
        raise SystemExit("No fear & greed data available.")

    recent_points = filter_recent(all_points, days=LOOKBACK_DAYS)
    btc_prices = fetch_btc_price_history(days=LOOKBACK_DAYS)

    latest = all_points[-1]
    chart_path = Path(args.chart_path)
    save_chart(recent_points, btc_prices, chart_path)

    spearman_correlation = calculate_spearman_correlation(recent_points, btc_prices)
    spearman_text = describe_correlation(spearman_correlation)

    message = build_message(latest, recent_points, spearman_text)
    send_telegram_message(args.bot_token, args.chat_id, message)
    send_telegram_photo(args.bot_token, args.chat_id, chart_path, "BTC fear/greed chart (last 6 months)")

    print(message)
    print(f"Chart saved to: {chart_path.resolve()}")


if __name__ == "__main__":
    main()



