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
