python_sources = files(
    '__init__.py',
    'case_ingest.py',
    'file_ingestible.py',
    'registry.py'
)

py.install_sources(
    python_sources,
    subdir: 'frxxv/ingest',
    install_tag: 'runtime'
)

subdir('case_types')
subdir('file_types')
