from __future__ import annotations

from pathlib import Path

from src.common.schemas import DependencyEdge, ParsedFile, ProjectGraph


class DependencyExtractor:
    def build_graph(self, parsed_files: list[ParsedFile]) -> ProjectGraph:
        nodes = [item.path for item in parsed_files]
        python_modules = self._build_python_module_index(parsed_files)
        edges: list[DependencyEdge] = []

        for parsed_file in parsed_files:
            for imported_module in parsed_file.imports:
                target = python_modules.get(imported_module)
                edges.append(
                    DependencyEdge(
                        source=parsed_file.path,
                        target=target or imported_module,
                        resolution_confidence=1.0 if target else 0.3,
                        resolved=target is not None,
                    )
                )

        return ProjectGraph(nodes=nodes, edges=edges)

    def _build_python_module_index(self, parsed_files: list[ParsedFile]) -> dict[str, str]:
        index: dict[str, str] = {}
        for parsed_file in parsed_files:
            if parsed_file.language != "python":
                continue

            path = Path(parsed_file.path)
            module_name = ".".join(path.with_suffix("").parts)
            index[module_name] = parsed_file.path

            if path.name == "__init__.py":
                package_name = ".".join(path.parent.parts)
                if package_name:
                    index[package_name] = parsed_file.path

        return index
