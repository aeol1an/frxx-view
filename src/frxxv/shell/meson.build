python_sources = files(
    '__init__.py',
    'basic_edits.py',
    'boundary.py',
    'doppler.py',
    'help.py',
    'mask.py',
    'prod_nav.py',
    'shell.py',
)

py.install_sources(
    python_sources,
    subdir: 'frxxv/shell',
    install_tag: 'runtime'
)

subdir('moments')
subdir('spectra')
