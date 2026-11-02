"""Solver registry with lazily imported backends, shared by ``sc1p`` and ``scbm``.

A backend module registers its class with ``@registry.register(name)`` when it
is imported, and it is only imported when that backend is requested, so the
core packages import without any optional dependency.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable


class SolverRegistry:
    """Backend table for one problem.

    Args:
        package: distribution name, used in installation hints.
        backend_modules: backend name -> module that registers it.
        auto_order: backends tried in order for ``name="auto"``.
        extra_map: backend name -> optional-dependency extra that provides it.
    """

    def __init__(
        self,
        *,
        package: str,
        backend_modules: dict[str, str],
        auto_order: tuple[str, ...],
        extra_map: dict[str, str],
    ) -> None:
        self._package = package
        self._solvers: dict[str, type] = {}
        self._backend_modules = backend_modules
        self._auto_order = auto_order
        self._extra_map = extra_map

    def register(self, name: str) -> Callable[[type], type]:
        def decorator(cls: type) -> type:
            self._solvers[name] = cls
            return cls

        return decorator

    def _try_load(self, name: str) -> bool:
        if name in self._solvers:
            return True
        module = self._backend_modules.get(name)
        if module is None:
            return False
        try:
            importlib.import_module(module)
        except ImportError:
            return False
        return name in self._solvers

    def get(self, name: str = "auto"):
        """Instantiate backend *name*, or the first loadable one for ``"auto"``.

        Raises:
            RuntimeError: ``"auto"`` and no backend can be loaded.
            ImportError: *name* is known but its optional dependency is missing.
            ValueError: *name* is unknown.
        """
        if name == "auto":
            for candidate in self._auto_order:
                if self._try_load(candidate):
                    return self._solvers[candidate]()
            raise RuntimeError(f"no {self._package} backend could be loaded")

        if self._try_load(name):
            return self._solvers[name]()
        if name in self._backend_modules:
            extra = self._extra_map.get(name, "all")
            raise ImportError(
                f"backend {name!r} needs an optional dependency: "
                f"pip install '{self._package}[{extra}]'"
            )
        known = sorted(set(self._solvers) | set(self._backend_modules))
        raise ValueError(f"unknown solver {name!r}; known: {known}")

    def available(self) -> list[str]:
        """Backends whose module imports, followed by externally registered ones."""
        loadable = [name for name in self._backend_modules if self._try_load(name)]
        external = [name for name in self._solvers if name not in self._backend_modules]
        return loadable + external
