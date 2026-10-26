"""Auditable ETF benchmarks, without claiming that an adjusted close is licensed.

Canonical actions use EX-DATES, cash dividends per POST-SPLIT share, and split
coefficient = new shares / old shares. Prices must be genuinely unadjusted. Some
vendors call split-adjusted prices 'raw'; reconcile their convention first.
"""
from __future__ import annotations

import math
import numpy as np
import pandas as pd


def _checked(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    if not isinstance(df.index, pd.DatetimeIndex) or df.index.tz is not None:
        raise ValueError('Use timezone-naive exchange session dates as DatetimeIndex')
    if df.index.hasnans or df.index.has_duplicates or not df.index.is_monotonic_increasing:
        raise ValueError('Session dates must be unique, non-null and ascending')
    if not (df.index == df.index.normalize()).all() or len(df) < 2:
        raise ValueError('At least two normalized daily session dates required')
    missing = set(columns) - set(df.columns)
    if missing:
        raise ValueError(f'Missing columns: {sorted(missing)}')
    out = df.copy()
    for col in columns:
        out[col] = pd.to_numeric(out[col], errors='raise')
        if not np.isfinite(out[col].to_numpy(dtype=float)).all():
            raise ValueError(f'{col} must be finite')
        if (out[col] < 0).any() or (col != 'dividend_amount' and (out[col] == 0).any()):
            raise ValueError(f'Invalid {col}')
    return out


def _metrics(wealth: pd.Series) -> dict:
    returns = wealth.pct_change().dropna()
    years = (wealth.index[-1] - wealth.index[0]).days / 365.2425
    total = float(wealth.iloc[-1] / wealth.iloc[0] - 1)
    return {
        'total_return': total,
        'cagr_actual_calendar_days': float((1 + total) ** (1 / years) - 1) if years else None,
        'annualized_volatility_252': float(returns.std(ddof=1) * math.sqrt(252)) if len(returns) > 1 else None,
        'max_drawdown': float((wealth / wealth.cummax() - 1).min()),
    }


def _curve(wealth: pd.Series, include_series: bool) -> dict:
    result = _metrics(wealth)
    if include_series:
        result['wealth_index'] = [
            {'date': d.date().isoformat(), 'wealth': float(v)} for d, v in wealth.items()
        ]
    return result


def total_return_benchmarks(
    df: pd.DataFrame,
    *,
    symbol: str = 'UNSPECIFIED',
    actions_verified: bool = False,
    adjustment_verified: bool = False,
    reconciliation_tolerance_bps: float = 5.0,
    include_series: bool = True,
) -> dict:
    """Compute distinct price, action-ledger and vendor-adjusted benchmarks.

    Verified flags are caller assertions about independent provenance/QA, never
    grants of usage rights. They default to false. No fees or taxes are included.
    The ledger credits dividends and reinvests at the EX-DATE close, a conventional
    hypothetical total return, not investable cash received on the payable date.
    First-row actions cannot be applied without a prior close and are excluded.
    """
    if type(actions_verified) is not bool or type(adjustment_verified) is not bool:
        raise ValueError('Verification assertions must be booleans')
    if not math.isfinite(reconciliation_tolerance_bps) or reconciliation_tolerance_bps < 0:
        raise ValueError('Reconciliation tolerance must be finite and nonnegative')
    action_columns = {'dividend_amount', 'split_coefficient'}
    present = action_columns.intersection(df.columns)
    if present and present != action_columns:
        raise ValueError('Dividends and split coefficients must be supplied together')
    if actions_verified and not present:
        raise ValueError('Verified actions requested without action history')
    if adjustment_verified and 'adjusted_close' not in df:
        raise ValueError('Verified adjustment requested without adjusted_close')
    columns = ['close'] + sorted(present)
    if 'adjusted_close' in df:
        columns.append('adjusted_close')
    df = _checked(df, columns)
    report = {
        'schema_version': '1.0', 'symbol': symbol,
        'data_origin': 'CALLER_SUPPLIED_NOT_INFERRED',
        'start': df.index[0].date().isoformat(), 'end': df.index[-1].date().isoformat(),
        'n_observations': len(df), 'n_return_intervals': len(df) - 1,
        'rights_assessed_by_this_function': False,
        'actions_verified_by_caller': actions_verified,
        'adjustment_verified_by_caller': adjustment_verified,
        'total_return_claim_supported_by_caller_assertions': actions_verified or adjustment_verified,
        'raw_close_ratio': _curve(df.close / df.close.iloc[0], include_series),
        'raw_close_ratio_warning': 'Price only; not an economic return across splits or cash distributions.',
        'conventions': {
            'actions': 'ex-date; cash per post-split share; split = new/old shares',
            'ledger_reinvestment': 'hypothetical ex-date close, before tax, fees and spread',
            'ledger_factor': 'split_coefficient * (close + dividend_amount) / previous_close',
            'vendor_backward_discount_factor': 'split_coefficient * close / (previous_close - split_coefficient * dividend_amount)',
            'first_row': 'base close; first-row corporate actions excluded',
            'calendar': 'Caller must independently establish a complete exchange-session history.',
        },
        'limitations': [
            'No strategy edge, OOS performance or profitable strategy is established.',
            'Latest adjusted histories are revised data, not point-in-time signal inputs.',
            'Vendor backward dividend adjustment and ex-date-close reinvestment need not match exactly.',
            'Actions verification and licensing remain external controls.',
        ],
    }
    ledger_factor = backward_factor = None
    if present:
        previous = df.close.shift(1)
        ledger_factor = df.split_coefficient * (df.close + df.dividend_amount) / previous
        denominator = previous - df.split_coefficient * df.dividend_amount
        if (denominator.iloc[1:] <= 0).any():
            raise ValueError('Dividend/split convention inconsistent with prior close')
        backward_factor = df.split_coefficient * df.close / denominator
        ledger_factor.iloc[0] = backward_factor.iloc[0] = 1.0
        report['action_ledger'] = _curve(ledger_factor.cumprod(), include_series)
        report['action_ledger']['status'] = 'CALLER_VERIFIED_ACTIONS' if actions_verified else 'UNVERIFIED_ACTION_HISTORY'
        report['action_ledger']['dividend_event_count'] = int((df.dividend_amount.iloc[1:] > 0).sum())
        report['action_ledger']['split_event_count'] = int((df.split_coefficient.iloc[1:] != 1).sum())
    if 'adjusted_close' in df:
        report['provider_adjusted_close'] = _curve(df.adjusted_close / df.adjusted_close.iloc[0], include_series)
        report['provider_adjusted_close']['status'] = 'CALLER_VERIFIED_ADJUSTMENT' if adjustment_verified else 'ADJUSTMENT_SEMANTICS_UNVERIFIED'
        if ledger_factor is not None:
            actual = df.adjusted_close.pct_change().add(1)
            ledger_error = (actual - ledger_factor).abs().iloc[1:] * 10000
            backward_error = (actual - backward_factor).abs().iloc[1:] * 10000
            nearest = pd.concat([ledger_error, backward_error], axis=1).min(axis=1)
            report['adjustment_reconciliation'] = {
                'tolerance_bps': reconciliation_tolerance_bps,
                'max_daily_factor_error_vs_ledger_bps': float(ledger_error.max()),
                'max_daily_factor_error_vs_backward_discount_bps': float(backward_error.max()),
                'unexplained_daily_factor_dates': [d.date().isoformat() for d in nearest.index[nearest > reconciliation_tolerance_bps]],
                'passes_candidate_formula_check': bool((nearest <= reconciliation_tolerance_bps).all()),
                'interpretation': 'Diagnostic against two conventions; passing does not independently verify corporate actions or vendor methodology.',
            }
    return report


def next_open_simulation(
    df: pd.DataFrame,
    target_at_close: pd.Series,
    *,
    transaction_cost_bps: float = 10.0,
    annual_cash_rate: float = 0.0,
) -> dict:
    """Long-only 0..100% daily simulator; decision close t -> open t+1.

    All corporate actions must be supplied; dividend cash is credited on ex-date
    (hypothetical accounting, not payable-date cash). Fractional shares permitted.
    Cash accrues at a constant exogenous annual rate over calendar-day intervals.
    Cost is proportional to traded notional; target allocation solves after-cost
    wealth exactly. No leverage, shorts, tax, bid/ask feed, impact or broker orders.
    An initial close NAV of 1 is cash; the first possible order is row 1 open.
    """
    df = _checked(df, ['open', 'close', 'dividend_amount', 'split_coefficient'])
    if not isinstance(target_at_close, pd.Series) or not target_at_close.index.equals(df.index):
        raise ValueError('Targets must have exactly the same session index as prices')
    targets = pd.to_numeric(target_at_close, errors='raise')
    if not np.isfinite(targets).all() or ((targets < 0) | (targets > 1)).any():
        raise ValueError('Targets must be finite fractions in [0, 1]')
    if not math.isfinite(transaction_cost_bps) or not 0 <= transaction_cost_bps < 10000:
        raise ValueError('Transaction costs must be in [0, 10000) bps')
    if not math.isfinite(annual_cash_rate) or annual_cash_rate <= -1:
        raise ValueError('Cash rate must be finite and greater than -1')
    cost = transaction_cost_bps / 10000
    cash, shares, costs = 1.0, 0.0, 0.0
    wealth = pd.Series(1.0, index=df.index)
    executions = []
    for i in range(1, len(df)):
        row = df.iloc[i]
        days = (df.index[i] - df.index[i-1]).days
        cash *= (1 + annual_cash_rate) ** (days / 365.2425)
        shares *= row.split_coefficient
        cash += shares * row.dividend_amount
        asset_value = shares * row.open
        nav_open = cash + asset_value
        target = float(targets.iloc[i-1])
        gap = target * nav_open - asset_value
        traded = gap / (1 + target * cost) if gap >= 0 else gap / (1 - target * cost)
        fee = abs(traded) * cost
        shares += traded / row.open
        cash -= traded + fee
        costs += fee
        if cash < -1e-10 or shares < -1e-10:
            raise ArithmeticError('Unexpected negative cash or shares')
        cash, shares = max(0.0, cash), max(0.0, shares)
        wealth.iloc[i] = cash + shares * row.close
        if abs(traded) > 1e-15:
            executions.append({'signal_date': df.index[i-1].date().isoformat(),
                               'execution_date': df.index[i].date().isoformat(),
                               'signed_notional': float(traded), 'fee': float(fee)})
    return {
        'status': 'HYPOTHETICAL_SIMULATION_NOT_VALIDATED_STRATEGY',
        'initial_wealth': 1.0, 'initial_position': 'cash_at_first_close',
        'decision_timing': 'previous_session_close_to_next_session_open',
        'transaction_cost_bps': transaction_cost_bps, 'annual_cash_rate': annual_cash_rate,
        'total_cost_in_initial_wealth_units': float(costs),
        'metrics': _metrics(wealth), 'wealth_index': _curve(wealth, True)['wealth_index'],
        'executions': executions,
        'limitations': 'Ex-date cash approximation; fractional shares; no impact, taxes, payable-date financing, delisting or execution feed. Missing sessions must be rejected upstream.',
    }
