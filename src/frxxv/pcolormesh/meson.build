py.install_sources(
  '__init__.py',
  'pcolormesh.pyi',
  subdir: 'frxxv/pcolormesh',
  install_tag: 'runtime'
)

py.extension_module(
  'pcolormesh',
  'pcolormesh.cpp',
  dependencies: [pybind11_dep, threads_dep],
  subdir: 'frxxv/pcolormesh',
  install: true,
  install_tag: 'runtime',
)
