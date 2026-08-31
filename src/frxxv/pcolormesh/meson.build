threads_dep = dependency('threads')

py.install_sources(
  '__init__.py',
  '_pcolormesh.pyi',
  subdir: 'frxxv/pcolormesh',
)

py.extension_module(
  '_pcolormesh',
  'pcolormesh.cpp',
  dependencies: [pybind11_dep, threads_dep],
  subdir: 'frxxv/pcolormesh',
  install: true,
  install_tag: 'runtime',
)
