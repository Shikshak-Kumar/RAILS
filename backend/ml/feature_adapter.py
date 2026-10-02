from __future__ import annotations

import math
from datetime import datetime
from typing import Any


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _std(values: list[float]) -> float:
    if not values:
        return 0.0
    mean = _mean(values)
    return math.sqrt(sum((v - mean) ** 2 for v in values) / len(values))


def build_feature_row(
    *,
    transaction_id: str,
    sender_id: str,
    receiver_id: str,
    amount: float,
    timestamp: datetime,
    sender_history: list[dict[str, Any]] | None,
    receiver_history: list[dict[str, Any]] | None,
    pair_history: list[dict[str, Any]] | None,
    feature_order: list[str] | None = None,
    transaction_type: str | None = None,
    currency: str | None = None,
) -> dict[str, float | int]:
    sender_history = sender_history or []
    receiver_history = receiver_history or []
    pair_history = pair_history or []

    sender_values = [float(item.get('amount', 0.0)) for item in sender_history]
    receiver_values = [float(item.get('amount', 0.0)) for item in receiver_history]
    pair_values = [float(item.get('amount', 0.0)) for item in pair_history]

    amount_float = max(float(amount), 0.0)
    log_amount = math.log1p(amount_float)
    hour = int(timestamp.hour)
    day_of_week = int(timestamp.weekday())
    is_weekend = 1 if day_of_week >= 5 else 0
    is_night = 1 if hour < 6 or hour >= 22 else 0
    type_code = 1 if (transaction_type or 'transfer').lower() in {'transfer', 'wire', 'ach'} else 0
    currency_code = 1 if (currency or 'usd').upper() == 'USD' else 0
    is_self_transfer = 1 if sender_id == receiver_id else 0

    s_cnt_5m = sum(1 for item in sender_history if (timestamp - item.get('timestamp', timestamp)).total_seconds() <= 300)
    s_cnt_1h = sum(1 for item in sender_history if (timestamp - item.get('timestamp', timestamp)).total_seconds() <= 3600)
    s_cnt_24h = sum(1 for item in sender_history if (timestamp - item.get('timestamp', timestamp)).total_seconds() <= 86400)
    s_amt_1h = sum(float(item.get('amount', 0.0)) for item in sender_history if (timestamp - item.get('timestamp', timestamp)).total_seconds() <= 3600)
    s_amt_24h = sum(float(item.get('amount', 0.0)) for item in sender_history if (timestamp - item.get('timestamp', timestamp)).total_seconds() <= 86400)
    s_hist_cnt = len(sender_history)
    s_hist_mean_log = _mean([math.log1p(float(item.get('amount', 0.0))) for item in sender_history])
    s_hist_std_log = _std([math.log1p(float(item.get('amount', 0.0))) for item in sender_history])
    s_amt_ratio = (s_amt_24h / max(amount_float, 1.0)) if s_amt_24h else 0.0
    s_amt_z = sum(v for v in sender_values if v > 0) / max(len(sender_values), 1)
    s_secs_since_last = 0.0
    for item in sender_history:
        diff = (timestamp - item.get('timestamp', timestamp)).total_seconds()
        if diff > 0:
            s_secs_since_last = min(s_secs_since_last or diff, diff)
    s_secs_since_last = float(s_secs_since_last or 0.0)

    r_hist_cnt = len(receiver_history)
    r_hist_mean_log = _mean([math.log1p(float(item.get('amount', 0.0))) for item in receiver_history])
    r_amt_ratio = (sum(float(item.get('amount', 0.0)) for item in receiver_history) / max(amount_float, 1.0)) if receiver_history else 0.0
    r_in_cnt_1h = sum(1 for item in receiver_history if (timestamp - item.get('timestamp', timestamp)).total_seconds() <= 3600)
    r_in_cnt_24h = sum(1 for item in receiver_history if (timestamp - item.get('timestamp', timestamp)).total_seconds() <= 86400)

    s_out_deg = sum(1 for item in sender_history if item.get('sender_id') == sender_id)
    s_in_deg = sum(1 for item in sender_history if item.get('receiver_id') == sender_id)
    r_in_deg = sum(1 for item in receiver_history if item.get('receiver_id') == receiver_id)
    r_out_deg = sum(1 for item in receiver_history if item.get('sender_id') == receiver_id)
    s_fanout_ratio = s_out_deg / max(1.0, s_in_deg + s_out_deg)
    r_fanin_ratio = r_in_deg / max(1.0, r_in_deg + r_out_deg)
    is_new_pair = 0 if pair_history else 1
    pair_hist_cnt = len(pair_history)
    pair_share = pair_hist_cnt / max(1.0, s_hist_cnt + r_hist_cnt)
    reverse_pair_cnt = sum(1 for item in pair_history if item.get('sender_id') == receiver_id and item.get('receiver_id') == sender_id)
    s_inflow_1h = sum(float(item.get('amount', 0.0)) for item in sender_history if item.get('receiver_id') == sender_id and (timestamp - item.get('timestamp', timestamp)).total_seconds() <= 3600)
    s_inflow_24h = sum(float(item.get('amount', 0.0)) for item in sender_history if item.get('receiver_id') == sender_id and (timestamp - item.get('timestamp', timestamp)).total_seconds() <= 86400)
    pass_through_24h = sum(float(item.get('amount', 0.0)) for item in sender_history if item.get('receiver_id') != sender_id and (timestamp - item.get('timestamp', timestamp)).total_seconds() <= 86400)
    rapid_move_flag = 1 if amount_float > (s_amt_24h / max(1, s_cnt_24h)) * 3 else 0

    feature_map: dict[str, float | int] = {
        'amount': amount_float,
        'log_amount': log_amount,
        'hour': hour,
        'day_of_week': day_of_week,
        'is_weekend': is_weekend,
        'is_night': is_night,
        'type_code': type_code,
        'currency_code': currency_code,
        'is_self_transfer': is_self_transfer,
        's_cnt_5m': float(s_cnt_5m),
        's_cnt_1h': float(s_cnt_1h),
        's_cnt_24h': float(s_cnt_24h),
        's_amt_1h': float(s_amt_1h),
        's_amt_24h': float(s_amt_24h),
        's_hist_cnt': float(s_hist_cnt),
        's_hist_mean_log': float(s_hist_mean_log),
        's_hist_std_log': float(s_hist_std_log),
        's_amt_ratio': float(s_amt_ratio),
        's_amt_z': float(s_amt_z),
        's_secs_since_last': float(s_secs_since_last),
        'r_hist_cnt': float(r_hist_cnt),
        'r_hist_mean_log': float(r_hist_mean_log),
        'r_amt_ratio': float(r_amt_ratio),
        'r_in_cnt_1h': float(r_in_cnt_1h),
        'r_in_cnt_24h': float(r_in_cnt_24h),
        's_out_deg': float(s_out_deg),
        's_in_deg': float(s_in_deg),
        'r_in_deg': float(r_in_deg),
        'r_out_deg': float(r_out_deg),
        's_fanout_ratio': float(s_fanout_ratio),
        'r_fanin_ratio': float(r_fanin_ratio),
        'is_new_pair': float(is_new_pair),
        'pair_hist_cnt': float(pair_hist_cnt),
        'pair_share': float(pair_share),
        'reverse_pair_cnt': float(reverse_pair_cnt),
        's_inflow_1h': float(s_inflow_1h),
        's_inflow_24h': float(s_inflow_24h),
        'pass_through_24h': float(pass_through_24h),
        'rapid_move_flag': float(rapid_move_flag),
    }

    if feature_order is not None:
        ordered = {name: feature_map.get(name, 0.0) for name in feature_order}
        return ordered
    return feature_map
