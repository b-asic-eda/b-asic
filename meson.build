project(
    'b_asic',
    'cpp',
    default_options : [
      'cpp_std=c++17',
      'b_lto=true',
      'b_ndebug=if-release',
      'warning_level=2',
    ],
    version : run_command(
      find_program('python3'), '-m', 'setuptools_scm', check: true
    ).stdout().strip(),
    meson_version : '>=1.1',
)

# Python module includes
py3 = import('python').find_installation('python3', pure: false)
py3_dep = py3.dependency()

# Version handling
fs = import('fs')
if fs.exists('_version.py')
    py3.install_sources('_version.py', subdir: 'b_asic')
else
  cfg = configuration_data()
  cfg.set_quoted('VCS_TAG', meson.project_version())
  configure_file(
    input: 'lib/b_asic/_version.py.in',
    output: '_version.py',
    configuration: cfg,
    install: true,
    install_tag: 'python-runtime',
    install_dir: py3.get_install_dir() / 'b_asic')
endif

# fmt
fmt = subproject('fmt', default_options: ['header-only=true'])
fmt_dep = fmt.get_variable('fmt_header_only_dep')

# pybind11
pybind11_dep = dependency('pybind11')

subdir('lib')
subdir('src')
