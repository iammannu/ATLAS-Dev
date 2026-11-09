
"""ATLAS Dev: standalone Python repository analyzer (Python 3.11)."""

from __future__ import annotations

import argparse
import ast
import json
import os
import tokenize
from pathlib import Path

EXCLUDED = {
    ".git", ".hg", ".svn", ".venv", "venv", "env",
    "__pycache__", ".tox", ".mypy_cache", ".pytest_cache",
    "node_modules", "build", "dist", "site-packages",
}


def discover_python_files(root):
    """Discover Python files recursively without following directory links."""
    root = Path(root).resolve()
    if not root.is_dir():
        raise NotADirectoryError(f"Not a directory: {root}")

    files = []
    def on_error(error):
        raise error

    for directory, dirs, names in os.walk(
        root, followlinks=False, onerror=on_error
    ):
        dirs[:] = sorted(
            name for name in dirs
            if name not in EXCLUDED
            and not (Path(directory) / name).is_symlink()
        )
        files.extend(
            Path(directory) / name
            for name in sorted(names)
            if name.endswith(".py")
        )
    return sorted(files)


def expression_name(node):
    """Return a readable representation of an AST expression."""
    try:
        return ast.unparse(node)
    except (ValueError, TypeError):
        return type(node).__name__


def branch_count(function):
    """Count approximate decision points within one function."""
    total = 0
    stack = list(ast.iter_child_nodes(function))

    while stack:
        node = stack.pop()

        if isinstance(node, (
            ast.FunctionDef, ast.AsyncFunctionDef,
            ast.ClassDef, ast.Lambda
        )):
            continue

        if isinstance(node, (
            ast.If, ast.IfExp, ast.For, ast.AsyncFor,
            ast.While, ast.ExceptHandler
        )):
            total += 1
        elif isinstance(node, ast.BoolOp):
            total += len(node.values) - 1
        elif isinstance(node, ast.Match):
            total += max(0, len(node.cases) - 1)
        elif isinstance(node, ast.comprehension):
            total += 1 + len(node.ifs)

        stack.extend(ast.iter_child_nodes(node))

    return total


def argument_count(node):
    args = node.args
    return (
        len(args.posonlyargs)
        + len(args.args)
        + len(args.kwonlyargs)
        + int(args.vararg is not None)
        + int(args.kwarg is not None)
    )


class StructureVisitor(ast.NodeVisitor):
    """Collect definitions, imports and approximate name usage."""

    def __init__(self):
        self.functions = []
        self.classes = []
        self.imports = []
        self.bindings = []
        self.used_names = set()
        self.exported_names = set()
        self.scope = []

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load):
            self.used_names.add(node.id)

    def visit_Assign(self, node):
        if any(
            isinstance(target, ast.Name) and target.id == "__all__"
            for target in node.targets
        ):
            if isinstance(node.value, (ast.List, ast.Tuple, ast.Set)):
                for item in node.value.elts:
                    if isinstance(item, ast.Constant) and isinstance(
                        item.value, str
                    ):
                        self.exported_names.add(item.value)
        self.generic_visit(node)

    def _function(self, node):
        qualified = ".".join(self.scope + [node.name])
        branches = branch_count(node)

        self.functions.append({
            "name": node.name,
            "qualified_name": qualified,
            "line": node.lineno,
            "end_line": node.end_lineno,
            "length": node.end_lineno - node.lineno + 1,
            "arguments": argument_count(node),
            "branches": branches,
            "complexity_estimate": branches + 1,
            "async": isinstance(node, ast.AsyncFunctionDef),
            "decorators": [
                expression_name(item)
                for item in node.decorator_list
            ],
        })

        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_FunctionDef(self, node):
        self._function(node)

    def visit_AsyncFunctionDef(self, node):
        self._function(node)

    def visit_ClassDef(self, node):
        qualified = ".".join(self.scope + [node.name])
        methods = [
            item.name for item in node.body
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]

        self.classes.append({
            "name": node.name,
            "qualified_name": qualified,
            "line": node.lineno,
            "end_line": node.end_lineno,
            "methods": methods,
            "bases": [expression_name(base) for base in node.bases],
        })

        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_Import(self, node):
        for alias in node.names:
            bound = alias.asname or alias.name.split(".")[0]
            self.imports.append({
                "module": alias.name,
                "name": None,
                "alias": alias.asname,
                "line": node.lineno,
                "scope": ".".join(self.scope),
            })
            self.bindings.append((bound, node.lineno, tuple(self.scope)))

    def visit_ImportFrom(self, node):
        module = "." * node.level + (node.module or "")

        for alias in node.names:
            self.imports.append({
                "module": module,
                "name": alias.name,
                "alias": alias.asname,
                "line": node.lineno,
                "scope": ".".join(self.scope),
            })

            if alias.name != "*" and node.module != "__future__":
                bound = alias.asname or alias.name
                self.bindings.append(
                    (bound, node.lineno, tuple(self.scope))
                )


def analyze_file(path, root):
    """Analyze one Python file and return JSON-compatible findings."""
    relative = path.relative_to(root).as_posix()
    result = {
        "path": relative,
        "functions": [],
        "classes": [],
        "imports": [],
        "dependencies": [],
        "syntax_error": None,
        "read_error": None,
        "unused_imports": [],
        "metrics": {},
    }

    try:
        with tokenize.open(path) as handle:
            source = handle.read()
    except (OSError, UnicodeError, SyntaxError, ValueError) as exc:
        result["read_error"] = str(exc)
        return result

    result["metrics"]["lines"] = len(source.splitlines())

    try:
        tree = ast.parse(source, filename=str(path))
    except (SyntaxError, ValueError) as exc:
        result["syntax_error"] = {
            "message": getattr(exc, "msg", str(exc)),
            "line": getattr(exc, "lineno", None),
            "column": getattr(exc, "offset", None),
        }
        return result

    visitor = StructureVisitor()
    visitor.visit(tree)

    result["functions"] = visitor.functions
    result["classes"] = visitor.classes
    result["imports"] = visitor.imports
    result["dependencies"] = sorted({
        item["module"] for item in visitor.imports
        if item["module"]
    })

    # HEURISTIC: name-based, not scope-aware. May produce false
    # positives or negatives for shadowing, re-exports and annotations.
    used = visitor.used_names | visitor.exported_names
    result["unused_imports"] = [
        {"name": name, "line": line, "heuristic": True}
        for name, line, scope in visitor.bindings
        if name not in used and path.name != "__init__.py"
    ]

    functions = visitor.functions
    result["metrics"].update({
        "function_count": len(functions),
        "class_count": len(visitor.classes),
        "import_count": len(visitor.imports),
        "max_function_length": max(
            (item["length"] for item in functions), default=0
        ),
        "max_branch_count": max(
            (item["branches"] for item in functions), default=0
        ),
        "total_branches": sum(
            item["branches"] for item in functions
        ),
    })
    return result


def analyze_repository(root):
    """Analyze a repository and produce a serializable project report."""
    root = Path(root).resolve()
    files = [
        analyze_file(path, root)
        for path in discover_python_files(root)
    ]

    return {
        "tool": "ATLAS Dev Code Intelligence Engine",
        "root": str(root),
        "summary": {
            "files": len(files),
            "parsed": sum(
                item["syntax_error"] is None
                and item["read_error"] is None
                for item in files
            ),
            "syntax_errors": sum(
                item["syntax_error"] is not None for item in files
            ),
            "read_errors": sum(
                item["read_error"] is not None for item in files
            ),
            "functions": sum(
                len(item["functions"]) for item in files
            ),
            "classes": sum(
                len(item["classes"]) for item in files
            ),
            "heuristic_unused_imports": sum(
                len(item["unused_imports"]) for item in files
            ),
        },
        "files": files,
    }


def main():
    parser = argparse.ArgumentParser(
        description="ATLAS Dev Python repository analyzer"
    )
    parser.add_argument("repository", help="Repository directory")
    parser.add_argument(
        "-o", "--output", help="Optional JSON report destination"
    )
    args = parser.parse_args()

    try:
        report = analyze_repository(args.repository)
        content = json.dumps(report, indent=2, ensure_ascii=False)

        if args.output:
            Path(args.output).write_text(
                content + "\n", encoding="utf-8"
            )
            print(f"Report saved to {args.output}")
        else:
            print(content)
    except (OSError, ValueError) as exc:
        parser.exit(2, f"Error: {exc}\n")


if __name__ == "__main__":
    main()
