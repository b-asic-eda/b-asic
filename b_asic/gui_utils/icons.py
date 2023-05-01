"""B-ASIC icons."""

import qtawesome

ICONS = {
    'save': 'mdi6.content-save',
    'save-as': 'mdi6.content-save-edit',
    'undo': 'mdi6.undo',
    'redo': 'mdi6.redo',
    'new': 'mdi6.file-outline',
    'open': 'mdi6.folder-open',
    'import': 'mdi6.import',
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
    'zoom-to-fit': 'mdi6.fit-to-page',
    'faq': 'mdi6.frequently-asked-questions',
    'sim': 'mdi6.chart-line',
    'reorder': ('msc.graph-left', {'rotated': -90}),
    'full-screen': 'mdi6.fullscreen',
    'full-screen-exit': 'mdi6.fullscreen-exit',
}


def get_icon(name):
    """Return icon for given name"""
    info = ICONS[name]
    if isinstance(info, str):
        return qtawesome.icon(info)
    return qtawesome.icon(info[0], **info[1])
