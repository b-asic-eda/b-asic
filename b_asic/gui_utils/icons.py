"""B-ASIC icons."""

import qtawesome

ICONS = {
    'save': 'mdi6.content-save',
    'new': 'mdi6.file-outline',
    'open': 'mdi6.folder-open',
    'legend': 'mdi6.map-legend',
    'close': 'mdi6.close',
    'all': 'mdi6.select-all',
    'none': 'mdi6.select-remove',
    'new-sfg': 'mdi6.new-box',
    'plot-schedule': 'mdi6.chart-gantt',
}


def get_icon(name):
    """Return icon for given name"""
    return qtawesome.icon(ICONS[name])
