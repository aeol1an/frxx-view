project(
  'frxx-view',
  'cpp',
  version: '0.1.4.1',
  license: 'LGPL-3.0-or-later',
  meson_version: '>=1.1.0',
  default_options: ['cpp_std=c++17'],
)

# Keep Python and future native extension modules in the same wheel install
# scheme. Native targets can reuse py and pybind11_dep from subdirectories.
py = import('python').find_installation(pure: false)
pybind11_dep = dependency('pybind11')
threads_dep = dependency('threads')

subdir('src')
