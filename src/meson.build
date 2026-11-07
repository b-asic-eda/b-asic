# Python module
py3.extension_module(
    '_b_asic',
    sources : files([
        'main.cpp',
	    'simulation.cpp',
        'simulation/compile.cpp',
        'simulation/run.cpp',
        'simulation/simulation.cpp',
    ]),
    dependencies : [py3_dep, pybind11_dep, fmt_dep],
    subdir: 'b_asic',
    install: true,
)

# GUI algorithms have no Qt dependency; all per-design state stays in C++.
py3.extension_module(
    '_sfg_gui',
    sources : files([
        'sfg_gui/module.cpp',
        'sfg_gui/engine.cpp',
        'sfg_gui/placement.cpp',
        'sfg_gui/routing.cpp',
    ]),
    dependencies : [py3_dep, pybind11_dep],
    subdir: 'b_asic',
    install: true,
)
