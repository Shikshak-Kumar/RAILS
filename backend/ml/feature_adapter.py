from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any


def _parse_ts(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        clean = value.strip()
        for fmt in ('%Y-%m-%d %H:%M:%S%z', '%Y-%m-%d %H:%M:%S', '%Y/%m/%d %H:%M', '%Y/%m/%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S%z', '%Y-%m-%dT%H:%M:%S'):
            try:
                dt = datetime.strptime(clean, fmt)
                return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        try:
            dt = datetime.fromisoformat(clean.replace('Z', '+00:00'))
            return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return datetime.now(timezone.utc)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _std(values: list[float]) -> float:
    if not values or len(values) < 2:
        return 0.0
    mean = _mean(values)
    return math.sqrt(sum((v - mean) ** 2 for v in values) / len(values))


TYPE_MAP = {
    'ach': 0,
    'bitcoin': 1,
    'cash': 2,
    'cheque': 3,
    'check': 3,
    'credit card': 4,
    'card': 4,
    'reinvestment': 5,
    'wire': 6,
    'transfer': 0,
}

CURRENCY_MAP = {
    'australian dollar': 0,
    'aud': 0,
    'bitcoin': 1,
    'btc': 1,
    'brazil real': 2,
    'brl': 2,
    'canadian dollar': 3,
    'cad': 3,
    'euro': 4,
    'eur': 4,
    'mexican peso': 5,
    'mxn': 5,
    'ruble': 6,
    'rub': 6,
    'rupee': 7,
    'inr': 7,
    'saudi riyal': 8,
    'sar': 8,
    'shekel': 9,
    'ils': 9,
    'swiss franc': 10,
    'chf': 10,
    'uk pound': 11,
    'gbp': 11,
    'us dollar': 12,
    'usd': 12,
    'yen': 13,
    'jpy': 13,
    'yuan': 14,
    'cny': 14,
}


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
    ts = _parse_ts(timestamp)

    s_hist = [item for item in (sender_history or []) if _parse_ts(item.get('timestamp')) < ts]
    r_hist = [item for item in (receiver_history or []) if _parse_ts(item.get('timestamp')) < ts]
    p_hist = [item for item in (pair_history or []) if _parse_ts(item.get('timestamp')) < ts]

    sender_values = [_safe_float(item.get('amount')) for item in s_hist]
    receiver_values = [_safe_float(item.get('amount')) for item in r_hist]

    amount_float = max(float(amount), 0.0)
    log_amount = math.log1p(amount_float)
    hour = int(ts.hour)
    day_of_week = int(ts.weekday())
    is_weekend = 1 if day_of_week >= 5 else 0
    is_night = 1 if hour < 6 or hour >= 22 else 0

    norm_type = str(transaction_type or 'transfer').lower().strip()
    type_code = TYPE_MAP.get(norm_type, 0)

    norm_curr = str(currency or 'usd').lower().strip()
    currency_code = CURRENCY_MAP.get(norm_curr, 12)

    is_self_transfer = 1 if sender_id == receiver_id else 0

    s_cnt_5m = sum(1 for item in s_hist if (ts - _parse_ts(item.get('timestamp'))).total_seconds() <= 300)
    s_cnt_1h = sum(1 for item in s_hist if (ts - _parse_ts(item.get('timestamp'))).total_seconds() <= 3600)
    s_cnt_24h = sum(1 for item in s_hist if (ts - _parse_ts(item.get('timestamp'))).total_seconds() <= 86400)
    s_amt_1h = sum(_safe_float(item.get('amount')) for item in s_hist if (ts - _parse_ts(item.get('timestamp'))).total_seconds() <= 3600)
    s_amt_24h = sum(_safe_float(item.get('amount')) for item in s_hist if (ts - _parse_ts(item.get('timestamp'))).total_seconds() <= 86400)
    s_hist_cnt = len(s_hist)
    s_hist_mean_log = _mean([math.log1p(_safe_float(item.get('amount'))) for item in s_hist])
    s_hist_std_log = _std([math.log1p(_safe_float(item.get('amount'))) for item in s_hist])
    s_amt_ratio = (s_amt_24h / max(amount_float, 1.0)) if s_amt_24h else 0.0

    if sender_values and len(sender_values) > 1:
        s_mean = _mean(sender_values)
        s_std_val = _std(sender_values)
        s_amt_z = (amount_float - s_mean) / max(s_std_val, 1.0)
    elif sender_values:
        s_amt_z = (amount_float - sender_values[0]) / max(sender_values[0] * 0.1, 1.0)
    else:
        s_amt_z = 0.0

    s_secs_since_last = 0.0
    if s_hist:
        prior_timestamps = [_parse_ts(item.get('timestamp')) for item in s_hist if item.get('timestamp')]
        if prior_timestamps:
            last_ts = max(prior_timestamps)
            diff = (ts - last_ts).total_seconds()
            if diff > 0:
                s_secs_since_last = diff

    r_hist_cnt = len(r_hist)
    r_hist_mean_log = _mean([math.log1p(_safe_float(item.get('amount'))) for item in r_hist])
    r_amt_ratio = (sum(receiver_values) / max(amount_float, 1.0)) if receiver_values else 0.0
    r_in_cnt_1h = sum(1 for item in r_hist if (ts - _parse_ts(item.get('timestamp'))).total_seconds() <= 3600 and item.get('receiver_id') == receiver_id)
    r_in_cnt_24h = sum(1 for item in r_hist if (ts - _parse_ts(item.get('timestamp'))).total_seconds() <= 86400 and item.get('receiver_id') == receiver_id)

    s_out_deg = sum(1 for item in s_hist if item.get('sender_id') == sender_id)
    s_in_deg = sum(1 for item in s_hist if item.get('receiver_id') == sender_id)
    r_in_deg = sum(1 for item in r_hist if item.get('receiver_id') == receiver_id)
    r_out_deg = sum(1 for item in r_hist if item.get('sender_id') == receiver_id)
    s_fanout_ratio = s_out_deg / max(1.0, float(s_in_deg + s_out_deg))
    r_fanin_ratio = r_in_deg / max(1.0, float(r_in_deg + r_out_deg))

    is_new_pair = 1 if len(p_hist) == 0 else 0
    pair_hist_cnt = len(p_hist)
    pair_share = pair_hist_cnt / max(1.0, float(s_hist_cnt + r_hist_cnt))
    reverse_pair_cnt = sum(1 for item in p_hist if item.get('sender_id') == receiver_id and item.get('receiver_id') == sender_id)

    s_inflow_1h = sum(_safe_float(item.get('amount')) for item in s_hist if item.get('receiver_id') == sender_id and (ts - _parse_ts(item.get('timestamp'))).total_seconds() <= 3600)
    s_inflow_24h = sum(_safe_float(item.get('amount')) for item in s_hist if item.get('receiver_id') == sender_id and (ts - _parse_ts(item.get('timestamp'))).total_seconds() <= 86400)
    pass_through_24h = min(s_inflow_24h, s_amt_24h) if (s_inflow_24h > 0 and s_amt_24h > 0) else sum(_safe_float(item.get('amount')) for item in s_hist if item.get('receiver_id') != sender_id and (ts - _parse_ts(item.get('timestamp'))).total_seconds() <= 86400)
    rapid_move_flag = 1 if (s_inflow_1h > 0 and amount_float >= 0.75 * s_inflow_1h) or (s_cnt_24h > 0 and amount_float > (s_amt_24h / max(1, s_cnt_24h)) * 3) else 0

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
        missing = [name for name in feature_order if name not in feature_map]
        if missing:
            raise ValueError(f"Missing required model features: {missing} for transaction {transaction_id}")
        return {name: feature_map[name] for name in feature_order}
    return feature_map
