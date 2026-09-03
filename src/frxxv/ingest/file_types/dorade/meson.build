python_sources = files(
    '__init__.py',
    'dorade_reader.py',
    'dorade.py',
    'rle_decode_core.pyi'
)

py.install_sources(
    python_sources,
    subdir: 'frxxv/ingest/file_types/dorade',
    install_tag: 'runtime'
)

py.extension_module(
    'rle_decode_core',
    'rle_decode_core.cpp',
    dependencies: pybind11_dep,
    subdir: 'frxxv/ingest/file_types/dorade',
    install: true,
    install_tag: 'runtime',
)
