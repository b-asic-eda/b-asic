"""B-ASIC icons."""

import qtawesome

ICONS = {
    'save': 'mdi6.content-save',
    'undo': 'mdi6.undo',
    'redo': 'mdi6.redo',
    'new': 'mdi6.file-outline',
    'open': 'mdi6.folder-open',
    'legend': 'mdi6.map-legend',
    'close': 'mdi6.close',
    'all': 'mdi6.select-all',
    'none': 'mdi6.select-remove',
    'new-sfg': 'ph.selection-plus',
    'plot-schedule': 'mdi6.chart-gantt',
    'increase-timeresolution': 'ph.clock-clockwise',
    'decrease-timeresolution': 'ph.clock-counter-clockwise',
    'quit': 'ph.power',
    'info': 'ph.info',
    'gitlab': 'ph.gitlab-logo-simple',
    'docs': 'ph.book',
    'about': 'ph.question',
    'keys': 'ph.keyboard',
    'add-operations': 'ph.math-operations',
}


def get_icon(name):
    """Return icon for given name"""
    return qtawesome.icon(ICONS[name])
