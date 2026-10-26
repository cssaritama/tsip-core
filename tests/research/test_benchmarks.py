import numpy as np
import pandas as pd
import pytest
from tsip.research.benchmarks import total_return_benchmarks, next_open_simulation


def sample():
    return pd.DataFrame({'open': [100., 49., 50.], 'close': [100., 49., 51.],
                         'dividend_amount': [0., 1., 0.], 'split_coefficient': [1., 2., 1.]},
                        index=pd.date_range('2024-01-02', periods=3, freq='B'))


def test_split_and_dividend_post_split_share_units():
    df = sample()
    report = total_return_benchmarks(df, actions_verified=True)
    assert report['action_ledger']['wealth_index'][1]['wealth'] == pytest.approx(1.)
    assert report['action_ledger']['total_return'] == pytest.approx(51/49-1)
    assert report['action_ledger']['dividend_event_count'] == 1
    assert report['action_ledger']['split_event_count'] == 1


def test_adjusted_close_is_not_automatically_verified_or_double_counted():
    df = sample()
    df['adjusted_close'] = [49., 49., 51.]
    report = total_return_benchmarks(df)
    assert not report['total_return_claim_supported_by_caller_assertions']
    assert report['provider_adjusted_close']['total_return'] == pytest.approx(51/49-1)
    assert report['adjustment_reconciliation']['passes_candidate_formula_check']


def test_backward_discount_differs_from_ex_close_reinvestment():
    df = sample()
    df['close'] = [100., 48., 50.]
    df['adjusted_close'] = [49., 48., 50.]
    report = total_return_benchmarks(df, reconciliation_tolerance_bps=0.00001)
    assert report['adjustment_reconciliation']['passes_candidate_formula_check']
    assert report['adjustment_reconciliation']['max_daily_factor_error_vs_ledger_bps'] > 0
    assert report['action_ledger']['total_return'] != report['provider_adjusted_close']['total_return']


def test_corrupted_adjustment_identifies_exact_date():
    df = sample()
    df['adjusted_close'] = [49., 49., 70.]
    result = total_return_benchmarks(df)['adjustment_reconciliation']
    assert result['unexplained_daily_factor_dates'] == ['2024-01-04']


def test_unknown_actions_are_not_fabricated():
    df = sample().drop(columns=['dividend_amount', 'split_coefficient'])
    assert 'action_ledger' not in total_return_benchmarks(df)
    with pytest.raises(ValueError): total_return_benchmarks(df, actions_verified=True)
    with pytest.raises(ValueError): total_return_benchmarks(sample().drop(columns='dividend_amount'))


@pytest.mark.parametrize('bad', [np.nan, np.inf, 0., -1.])
def test_invalid_prices_fail(bad):
    df = sample()
    df.loc[df.index[1], 'close'] = bad
    with pytest.raises(ValueError): total_return_benchmarks(df)


def test_no_same_day_signal_execution_and_cost_accounting():
    df = sample()
    df[['dividend_amount', 'split_coefficient']] = [0., 1.]
    df['open'] = [100., 100., 200.]
    df['close'] = [100., 200., 200.]
    targets = pd.Series([1., 0., 1.], index=df.index)
    out = next_open_simulation(df, targets, transaction_cost_bps=100.)
    assert out['executions'][0]['signal_date'] == '2024-01-02'
    assert out['executions'][0]['execution_date'] == '2024-01-03'
    assert out['wealth_index'][0]['wealth'] == 1.
    assert out['wealth_index'][-1]['wealth'] == pytest.approx(2 * .99 / 1.01)
    changed = targets.copy(); changed.iloc[-1] = 0.
    assert next_open_simulation(df, changed, transaction_cost_bps=100.)['wealth_index'] == out['wealth_index']


def test_ex_date_entitlement_requires_previous_ownership():
    df = sample()
    target = pd.Series([1., 1., 1.], index=df.index)
    out = next_open_simulation(df, target, transaction_cost_bps=0.)
    # Entry is on the ex-date, so no cash dividend or split entitlement beforehand.
    assert out['wealth_index'][1]['wealth'] == pytest.approx(1.)
    assert out['wealth_index'][2]['wealth'] == pytest.approx(51/49)


def test_cash_only_accrues_calendar_days():
    df = sample()
    out = next_open_simulation(df, pd.Series(0., index=df.index), annual_cash_rate=.05)
    assert out['executions'] == []
    assert out['wealth_index'][-1]['wealth'] == pytest.approx(1.05 ** (2/365.2425))


def test_targets_reject_leverage_and_misalignment():
    df = sample()
    with pytest.raises(ValueError): next_open_simulation(df, pd.Series(1.5, index=df.index))
    with pytest.raises(ValueError): next_open_simulation(df, pd.Series(1., index=df.index[::-1]))
