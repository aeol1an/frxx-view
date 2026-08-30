project(
  'frxx-view',
  'cpp',
  version: '0.1.2',
  license: 'LGPL-3.0-or-later',
  meson_version: '>=1.1.0',
  default_options: ['cpp_std=c++17'],
)

# Keep Python and future native extension modules in the same wheel install
# scheme. Native targets can reuse py and pybind11_dep from subdirectories.
py = import('python').find_installation(pure: false)
pybind11_dep = dependency('pybind11')

py.install_sources('src/frxx_view.py')

install_subdir(
  'src/frxxv',
  install_dir: py.get_install_dir(),
  exclude_directories: [
    '__pycache__',
    'assets/__pycache__',
    'controllers/__pycache__',
    'ingest/__pycache__',
    'ingest/case_types/__pycache__',
    'ingest/file_types/__pycache__',
    'plotting/__pycache__',
    'pcolormesh',
    'shell/__pycache__',
    'shell/moments/__pycache__',
    'shell/spectra/__pycache__',
    'widgets/__pycache__',
    'windows/__pycache__',
  ],
  install_tag: 'runtime',
)

subdir('src/frxxv/pcolormesh')
