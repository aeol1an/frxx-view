from __future__ import annotations

from dataclasses import dataclass, field
from importlib import import_module
from pathlib import Path
from typing import Any, Callable


ImportTarget = str | type
BackendDetector = Callable[[Path], bool]


@dataclass(frozen=True)
class BackendDefinition:
    name: str
    case_type: str
    file_type: str
    case_kwargs: dict[str, Any] = field(default_factory=dict)
    detector: BackendDetector | None = None
    auto_priority: int | None = None
    implemented: bool = True


_CASE_TYPES: dict[str, ImportTarget] = {}
_FILE_TYPES: dict[str, ImportTarget] = {}
_BACKENDS: dict[str, BackendDefinition] = {}


def _key(name: str) -> str:
    value = name.strip().casefold()
    if not value:
        raise ValueError("Registry names cannot be empty")
    return value


def _register(registry, name, target, replace):
    name = _key(name)
    if name in registry and not replace:
        raise ValueError(f"{name!r} is already registered")
    registry[name] = target


def register_case_type(
    name: str,
    target: ImportTarget,
    *,
    replace: bool = False,
) -> None:
    _register(_CASE_TYPES, name, target, replace)


def register_file_type(
    name: str,
    target: ImportTarget,
    *,
    replace: bool = False,
) -> None:
    _register(_FILE_TYPES, name, target, replace)


def register_backend(
    name: str,
    *,
    case_type: str,
    file_type: str,
    case_kwargs: dict[str, Any] | None = None,
    detector: BackendDetector | None = None,
    auto_priority: int | None = None,
    implemented: bool = True,
    replace: bool = False,
) -> None:
    name = _key(name)
    if name in _BACKENDS and not replace:
        raise ValueError(f"Backend {name!r} is already registered")
    _BACKENDS[name] = BackendDefinition(
        name=name,
        case_type=_key(case_type),
        file_type=_key(file_type),
        case_kwargs=dict(case_kwargs or {}),
        detector=detector,
        auto_priority=auto_priority,
        implemented=implemented,
    )


def available_backends() -> tuple[str, ...]:
    return tuple(sorted(_BACKENDS))


def available_case_types() -> tuple[str, ...]:
    return tuple(sorted(_CASE_TYPES))


def available_file_types() -> tuple[str, ...]:
    return tuple(sorted(_FILE_TYPES))


def get_backend(name: str) -> BackendDefinition:
    name = _key(name)
    try:
        backend = _BACKENDS[name]
    except KeyError as error:
        available = ", ".join(available_backends())
        raise ValueError(
            f"Unknown backend {name!r}; available backends: {available}"
        ) from error
    if not backend.implemented:
        raise NotImplementedError(f"The {name} backend is not implemented")
    return backend


def select_backend(starting_directory: Path | str, backend: str) -> str:
    starting_directory = Path(starting_directory)
    requested = _key(backend)
    if requested != "auto":
        return get_backend(requested).name

    candidates = sorted(
        (
            definition
            for definition in _BACKENDS.values()
            if definition.detector is not None
            and definition.auto_priority is not None
        ),
        key=lambda definition: definition.auto_priority,
    )
    for definition in candidates:
        if definition.detector(starting_directory):
            return get_backend(definition.name).name
    raise FileNotFoundError(
        f"Could not detect a supported radar backend in {starting_directory}"
    )


def create_case(backend: str, directory: Path | str):
    definition = get_backend(backend)
    case_type = _resolve_type(
        _CASE_TYPES,
        definition.case_type,
        "case type",
    )
    file_type = _resolve_type(
        _FILE_TYPES,
        definition.file_type,
        "file type",
    )
    return case_type(
        directory,
        loader=file_type,
        **definition.case_kwargs,
    )


def _resolve_type(registry, name, kind):
    try:
        target = registry[name]
    except KeyError as error:
        raise ValueError(f"Backend references unregistered {kind} {name!r}") from error
    if isinstance(target, str):
        module_name, separator, attribute = target.partition(":")
        if not separator or not module_name or not attribute:
            raise ValueError(
                f"Invalid import target {target!r}; expected 'module:attribute'"
            )
        target = getattr(import_module(module_name), attribute)
    return target


def _has_directory(name: str) -> BackendDetector:
    return lambda directory: (directory / name).is_dir()


def _has_files(pattern: str) -> BackendDetector:
    return lambda directory: any(
        path.is_file() for path in directory.glob(pattern)
    )


register_case_type(
    "directory",
    "frxxv.ingest.case_types.directory:Directory",
)

register_file_type(
    "cfradial",
    "frxxv.ingest.file_types.cfradial:CfradialFile",
)
register_file_type(
    "dorade",
    "frxxv.ingest.file_types.dorade:DoradeFile",
)
register_file_type(
    "pyart",
    "frxxv.ingest.file_types.pyart:PyartFile",
)

register_backend(
    "frxx",
    case_type="frxx",
    file_type="frxx",
    detector=_has_directory("frxx_cases"),
    auto_priority=0,
    implemented=False,
)
register_backend(
    "cfradial",
    case_type="directory",
    file_type="cfradial",
    case_kwargs={"file_globs": ("cfradial.*.nc",)},
    detector=_has_files("cfradial.*.nc"),
    auto_priority=10,
)
register_backend(
    "dorade",
    case_type="directory",
    file_type="dorade",
    case_kwargs={"file_globs": ("swp.*",)},
    detector=_has_files("swp.*"),
    auto_priority=20,
)
register_backend(
    "pyart",
    case_type="directory",
    file_type="pyart",
    implemented=False,
)
