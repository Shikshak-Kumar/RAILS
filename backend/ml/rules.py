from __future__ import annotations

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


def evaluate_transaction_rules(
    *,
    transaction_id: str,
    sender_id: str,
    receiver_id: str,
    amount: float,
    timestamp: datetime,
    sender_history: list[dict[str, Any]] | None = None,
    receiver_history: list[dict[str, Any]] | None = None,
    pair_history: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Deterministic, auditable rule evaluation based strictly on pre-transaction history."""
    ts = _parse_ts(timestamp)
    amount_float = max(float(amount), 0.0)

    # Strictly prior history (timestamp < ts)
    s_hist = [item for item in (sender_history or []) if _parse_ts(item.get('timestamp')) < ts]
    r_hist = [item for item in (receiver_history or []) if _parse_ts(item.get('timestamp')) < ts]
    p_hist = [item for item in (pair_history or []) if _parse_ts(item.get('timestamp')) < ts]

    # Sender stats
    s_cnt_1h = sum(1 for item in s_hist if (ts - _parse_ts(item.get('timestamp'))).total_seconds() <= 3600)
    s_cnt_24h = sum(1 for item in s_hist if (ts - _parse_ts(item.get('timestamp'))).total_seconds() <= 86400)
    s_inflow_1h = sum(float(item.get('amount', 0.0)) for item in s_hist if item.get('receiver_id') == sender_id and (ts - _parse_ts(item.get('timestamp'))).total_seconds() <= 3600)
    s_inflow_24h = sum(float(item.get('amount', 0.0)) for item in s_hist if item.get('receiver_id') == sender_id and (ts - _parse_ts(item.get('timestamp'))).total_seconds() <= 86400)
    s_out_deg = sum(1 for item in s_hist if item.get('sender_id') == sender_id)
    s_in_deg = sum(1 for item in s_hist if item.get('receiver_id') == sender_id)
    r_in_deg = sum(1 for item in r_hist if item.get('receiver_id') == receiver_id)
    r_out_deg = sum(1 for item in r_hist if item.get('sender_id') == receiver_id)

    sender_amounts = [float(item.get('amount', 0.0)) for item in s_hist if float(item.get('amount', 0.0)) > 0]
    sender_median = 0.0
    if sender_amounts:
        sorted_amts = sorted(sender_amounts)
        mid = len(sorted_amts) // 2
        sender_median = sorted_amts[mid] if len(sorted_amts) % 2 != 0 else (sorted_amts[mid - 1] + sorted_amts[mid]) / 2.0

    rules: list[dict[str, Any]] = []

    # Rule 1: High transaction velocity
    v_triggered = s_cnt_1h >= 5 or s_cnt_24h >= 20
    rules.append({
        'rule': 'high_transaction_velocity',
        'triggered': v_triggered,
        'value': s_cnt_1h,
        'threshold': 5,
        'description': f"Sender initiated {s_cnt_1h} transactions in the last hour (threshold: 5) and {s_cnt_24h} in 24h (threshold: 20)",
    })

    # Rule 2: Unusually large amount compared with sender history
    amt_baseline_triggered = bool(sender_median > 0 and amount_float >= 5.0 * sender_median and len(sender_amounts) >= 3)
    rules.append({
        'rule': 'amount_above_sender_baseline',
        'triggered': amt_baseline_triggered,
        'value': round(amount_float, 2),
        'threshold': round(5.0 * sender_median, 2) if sender_median > 0 else 0.0,
        'description': f"Transaction amount ${amount_float:,.2f} is >= 5x sender historical median (${sender_median:,.2f})",
    })

    # Rule 3: Rapid movement through accounts (pass-through layering)
    rapid_move_triggered = bool(s_inflow_1h > 0 and amount_float >= 0.75 * s_inflow_1h)
    rules.append({
        'rule': 'rapid_movement_through_accounts',
        'triggered': rapid_move_triggered,
        'value': round(amount_float, 2),
        'threshold': round(0.75 * s_inflow_1h, 2),
        'description': f"Immediate outflow of ${amount_float:,.2f} corresponds to >= 75% of recent 1h inflow (${s_inflow_1h:,.2f})",
    })

    # Rule 4: High fan-out (rapid dispersal from one sender to multiple distinct receivers in 24h)
    s_distinct_receivers_24h = len({
        str(item.get('receiver_id'))
        for item in s_hist
        if item.get('sender_id') == sender_id and (ts - _parse_ts(item.get('timestamp'))).total_seconds() <= 86400
    })
    s_fanout_ratio = s_out_deg / max(1.0, float(s_in_deg + s_out_deg))
    fanout_triggered = bool(s_out_deg >= 5 and s_fanout_ratio >= 0.8 and s_distinct_receivers_24h >= 4)
    rules.append({
        'rule': 'high_fanout',
        'triggered': fanout_triggered,
        'value': round(s_fanout_ratio, 2),
        'threshold': 0.8,
        'description': f"Rapid fan-out: {s_distinct_receivers_24h} distinct receivers in 24h (ratio: {s_fanout_ratio:.2f})",
    })

    # Rule 5: High fan-in (rapid aggregation into one receiver from multiple distinct senders in 24h)
    r_distinct_senders_24h = len({
        str(item.get('sender_id'))
        for item in r_hist
        if item.get('receiver_id') == receiver_id and (ts - _parse_ts(item.get('timestamp'))).total_seconds() <= 86400
    })
    r_fanin_ratio = r_in_deg / max(1.0, float(r_in_deg + r_out_deg))
    fanin_triggered = bool(r_in_deg >= 5 and r_fanin_ratio >= 0.8 and r_distinct_senders_24h >= 4)
    rules.append({
        'rule': 'high_fanin',
        'triggered': fanin_triggered,
        'value': round(r_fanin_ratio, 2),
        'threshold': 0.8,
        'description': f"Rapid fan-in: {r_distinct_senders_24h} distinct senders in 24h (ratio: {r_fanin_ratio:.2f})",
    })

    # Rule 6: New counterparty
    is_new_pair = len(p_hist) == 0
    rules.append({
        'rule': 'new_counterparty',
        'triggered': is_new_pair,
        'value': len(p_hist),
        'threshold': 1,
        'description': "First transaction recorded between this sender and receiver account pair",
    })

    # Rule 7: Sudden sender behavior change (dormant/low activity to sudden spike)
    dormant_burst = bool(len(s_hist) >= 5 and s_cnt_24h == 0 and s_cnt_1h >= 3)
    rules.append({
        'rule': 'sudden_sender_behavior_change',
        'triggered': dormant_burst,
        'value': s_cnt_1h,
        'threshold': 3,
        'description': f"Dormant account surge: {s_cnt_1h} transactions in 1 hour after dormancy",
    })

    # Rule 8: Suspicious transaction chain / pass-through volume
    high_chain_flow = bool(s_inflow_24h > 10000.0 and amount_float >= 0.8 * s_inflow_24h)
    rules.append({
        'rule': 'suspicious_transaction_chain',
        'triggered': high_chain_flow,
        'value': round(amount_float, 2),
        'threshold': round(0.8 * s_inflow_24h, 2),
        'description': f"Large pass-through chain: outflow ${amount_float:,.2f} mirrors 24h inflow ${s_inflow_24h:,.2f}",
    })

    triggered_rules = [r['rule'] for r in rules if r['triggered']]
    triggered_details = [r for r in rules if r['triggered']]

    # Determine deterministic escalation impact
    critical_triggers = sum(1 for r in rules if r['triggered'] and r['rule'] in {'rapid_movement_through_accounts', 'suspicious_transaction_chain'} and amount_float >= 50000.0)
    high_triggers = sum(1 for r in rules if r['triggered'] and r['rule'] in {'high_transaction_velocity', 'amount_above_sender_baseline', 'rapid_movement_through_accounts', 'high_fanout', 'high_fanin'})

    rule_risk_level = 'LOW'
    if critical_triggers >= 1 or high_triggers >= 3:
        rule_risk_level = 'CRITICAL'
    elif high_triggers >= 1:
        rule_risk_level = 'HIGH'
    elif triggered_rules:
        rule_risk_level = 'MEDIUM'

    return {
        'transaction_id': transaction_id,
        'signals': triggered_rules,
        'rule_details': rules,
        'triggered_details': triggered_details,
        'rule_risk_level': rule_risk_level,
    }
