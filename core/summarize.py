from collections import namedtuple, OrderedDict

import math
import numpy as np
import pandas as pd

from core.utils import format_date, to_storage_display_unit, tenth_round

ServiceSummary = namedtuple('ServiceSummary', 'service_summary storage_by_group')
SummaryComparison = namedtuple('SummaryComparison', 'storage_by_category storage_by_group compute')


def compare_summaries(summaries_by_date):
    storage_by_cat_series = []
    storage_by_group_series = []
    compute_series = []
    dates = sorted(list(summaries_by_date))
    for date in dates:
        summary_data = summaries_by_date[date]
        storage_by_cat_series.append(summary_data.storage.by_category['Rounded Total'])
        storage_by_group_series.append(summary_data.storage.by_group['Rounded Total'])
        compute_series.append(summary_data.compute[['CPU Total', 'RAM Total', 'VMs Total']])

    first_date = list(summaries_by_date)[0]
    group_series = summaries_by_date[first_date].storage.by_category['Group']
    storage_by_cat_series.append(group_series)

    keys = [format_date(date) for date in dates]
    storage_by_cat = _combine_summary_data(storage_by_cat_series, keys + ['Group'])
    storage_by_group = _combine_summary_data(storage_by_group_series, keys, False)
    compute = _combine_summary_data(compute_series, keys)
    return SummaryComparison(storage_by_cat, storage_by_group, compute)


def incremental_summaries(summary_comparisons, summary_dates):
    storage_by_cat_series = []
    storage_by_group_series = []
    compute_series = []
    keys = [format_date(date) for date in summary_dates]

    def _get_incremental(loop_count, keys, data):
        key = keys[loop_count]
        if loop_count == 0:
            return data[key]
        else:
            previous_key = keys[loop_count - 1]
            return data[key] - data[previous_key]

    for i, key in enumerate(keys):
        storage_by_cat_series.append(_get_incremental(i, keys, summary_comparisons.storage_by_category))
        storage_by_group_series.append(_get_incremental(i, keys, summary_comparisons.storage_by_group))
        compute_series.append(_get_incremental(i, keys, summary_comparisons.compute))

    storage_by_cat_series.append(summary_comparisons.storage_by_category['Group'])
    return SummaryComparison(
        _combine_summary_data(storage_by_cat_series, keys + ['Group'], False),
        _combine_summary_data(storage_by_group_series, keys, False),
        _combine_summary_data(compute_series, keys, False),
    )


def _combine_summary_data(series, keys, add_total=True):
    df = pd.concat(series, axis=1, keys=keys)
    if add_total:
        total = df.sum()
        total.name = 'Total'
        df = df.append(total, ignore_index=False)
    return df


def summarize_service_data(config, service_data, summary_date):
    snapshot = service_data.loc[summary_date]
    storage_units = config.storage_display_unit
    to_display = to_storage_display_unit(storage_units)
    to_gb = to_storage_display_unit('GB')
    summary_df = pd.DataFrame()
    for service_name, service_def in config.services.items():
        service_snapshot = snapshot[service_name]
        compute = service_snapshot['Compute']
        storage = service_snapshot['Storage']
        ram_buffer = compute['RAM'] * float(config.estimation_buffer)
        cpu_buffer = compute['CPU'] * float(config.estimation_buffer)
        node_buffer = compute['Nodes'] * float(config.estimation_buffer)
        data_storage_buffer = (storage['Data Storage'] * float(config.estimation_buffer + config.storage_buffer))
        os_storage_buffer = storage['OS Storage'] + (node_buffer * config.vm_os_storage_gb)
        data = OrderedDict([
            ('Cores Per Node', service_def.process.cores_per_node),
            ('Cores Needed', compute['CPU']),
            ('Cores Buffer', cpu_buffer),
            ('Cores Total', math.ceil(compute['CPU'] + cpu_buffer)),
            ('RAM Per Node', service_def.process.ram_per_node),
            ('RAM Needed', compute['RAM']),
            ('RAM Buffer', ram_buffer),
            ('RAM Total (GB)', math.ceil(compute['RAM'] + ram_buffer)),
            ('Data Storage Per Node (GB)', to_gb((storage['Data Storage'] / compute['Nodes']) if compute['Nodes'] else 0)),
            ('Data Storage Needed (%s)' % storage_units, to_display(storage['Data Storage'])),
            ('Data Storage Buffer (GB)', to_gb(data_storage_buffer)),
            ('Data Storage Total (%s)' % storage_units, to_display(math.ceil(storage['Data Storage'] + data_storage_buffer))),
            ('Data Storage Total Rounded (%s)' % storage_units, tenth_round(to_display(math.ceil(storage['Data Storage'] + data_storage_buffer)))),
            ('Nodes Needed', compute['Nodes']),
            ('Node Buffer', node_buffer),
            ('Nodes Total', math.ceil(compute['Nodes'] + node_buffer)),
            ('OS Storage Needed (GB)', to_display(storage['OS Storage'])),
            ('OS Storage Buffer (GB)', to_display(os_storage_buffer)),
            ('OS Storage Total (GB)', to_display(math.ceil(storage['OS Storage'] + os_storage_buffer))),
            ('Storage Group', service_def.storage.group)
        ])
        combined = pd.Series(name=service_name, data=data)
        summary_df[service_name] = combined

    summary_by_service = summary_df.T
    summary_by_service.sort_index(inplace=True)

    by_type = summary_by_service.groupby('Storage Group')['Data Storage Total Rounded (%s)' % storage_units].sum()
    by_type.index.name = None
    storage_by_group = pd.DataFrame({
        'Rounded Total (%s)' % storage_units: by_type,
    })

    total = summary_by_service.sum()
    total.name = 'Total'
    summary_by_service = summary_by_service.append(total, ignore_index=False)

    storage_by_group.sort_index(inplace=True)
    return ServiceSummary(summary_by_service, storage_by_group)


def compare_summaries_new(config, summaries_by_date):
    data_storage_series = []
    storage_by_group_series = []
    compute_series = []
    dates = sorted(list(summaries_by_date))
    storage_units = config.storage_display_unit
    for date in dates:
        summary_data = summaries_by_date[date]
        data_storage_series.append(summary_data.service_summary['Data Storage Total Rounded (%s)' % storage_units])
        storage_by_group_series.append(summary_data.storage_by_group['Rounded Total (%s)' % storage_units])
        compute_series.append(summary_data.service_summary[['Cores Total', 'RAM Total (GB)', 'Nodes Total']])

    first_date = list(summaries_by_date)[0]
    group_series = summaries_by_date[first_date].service_summary['Storage Group']
    data_storage_series.append(group_series)

    keys = [format_date(date) for date in dates]

    storage_by_cat = _combine_summary_data(data_storage_series, keys + ['Group'])
    storage_by_cat = storage_by_cat[storage_by_cat != 0.0].dropna(how='all')

    storage_by_group = _combine_summary_data(storage_by_group_series, keys)

    compute = _combine_summary_data(compute_series, keys)
    compute = compute[compute > 0].dropna()
    return SummaryComparison(storage_by_cat, storage_by_group, compute)
