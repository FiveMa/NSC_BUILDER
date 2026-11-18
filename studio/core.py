"""Static Squirrel CLI metadata and argument assembly for NSCB Studio."""

import ast
import tokenize
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Option:
    """A CLI declaration; prefer its first long spelling as the primary flag."""

    flag: str
    aliases: tuple[str, ...]
    help: str
    nargs: int | str | None
    action: str


def _literal(node: ast.expr | None, default):
    if isinstance(node, ast.Constant) and type(node.value) is type(default):
        return node.value
    return default


def load_catalog(path: Path) -> list[Option]:
    """Read direct argparse declarations in source order without running Squirrel.

    Only literal argument names are cataloged. Non-literal or suppressed help
    is empty. Registration after a parser's first parse call is ignored.
    """
    with tokenize.open(path) as source:
        tree = ast.parse(source.read(), filename=str(path))

    catalog = []
    parsers = set()
    statements = (node for node in ast.walk(tree) if isinstance(node, (ast.Assign, ast.Expr)))
    for statement in sorted(statements, key=lambda node: (node.lineno, node.col_offset)):
        call = statement.value
        if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Attribute):
            continue
        receiver = call.func.value
        if not isinstance(receiver, ast.Name):
            continue
        method = call.func.attr
        if isinstance(statement, ast.Assign) and receiver.id == 'argparse' and method == 'ArgumentParser':
            parsers.update(target.id for target in statement.targets if isinstance(target, ast.Name))
        elif receiver.id in parsers and method in {'parse_args', 'parse_known_args'}:
            parsers.remove(receiver.id)
        elif receiver.id in parsers and method == 'add_argument':
            names = tuple(_literal(arg, '') for arg in call.args)
            if not names or not all(names):
                continue
            primary = next((i for i, name in enumerate(names) if name.startswith('--')), 0)
            keywords = {kw.arg: kw.value for kw in call.keywords}
            nargs = keywords.get('nargs')
            catalog.append(Option(
                names[primary], names[:primary] + names[primary + 1:],
                _literal(keywords.get('help'), ''),
                nargs.value if isinstance(nargs, ast.Constant) and type(nargs.value) in (str, int) else None,
                _literal(keywords.get('action'), 'store'),
            ))
    return catalog


_NO_VALUE_ACTIONS = {'store_true', 'store_false', 'store_const', 'append_const', 'count', 'help', 'version'}


def _validate_arity(option: Option, count: int) -> None:
    nargs = 0 if option.action in _NO_VALUE_ACTIONS else option.nargs
    if nargs is None:
        nargs = 1
    if isinstance(nargs, int) and nargs >= 0:
        minimum = maximum = nargs
        expected = str(nargs)
    elif nargs == '?':
        minimum, maximum = 0, 1
        expected = 'zero or one'
    elif nargs in ('*', '+'):
        minimum, maximum = int(nargs == '+'), None
        expected = 'at least one' if minimum else 'any number of'
    else:
        raise ValueError(f'{option.flag}: unsupported nargs {nargs!r}')
    if count < minimum or (maximum is not None and count > maximum):
        raise ValueError(f'{option.flag}: expected {expected} value(s), got {count}')


def build_arguments(selections: Iterable[tuple[Option, list[str]]]) -> list[str]:
    """Build argv tokens (without executable/script) from selected declarations.

    Supply positionals in declaration order. They follow an end-of-options
    marker so a variadic option cannot consume them. Invalid selections raise
    ValueError; option values starting with a hyphen are rejected except '-'.
    """
    argv = []
    positionals = []
    seen = set()
    for option, values in selections:
        names = (option.flag, *option.aliases)
        if not seen.isdisjoint(names):
            raise ValueError(f'{option.flag}: duplicate selection')
        seen.update(names)
        _validate_arity(option, len(values))
        if option.flag.startswith('-'):
            for value in values:
                if value.startswith('-') and value != '-':
                    raise ValueError(f'{option.flag}: option-like value {value!r}')
            argv.extend((option.flag, *values))
        else:
            positionals.extend(values)
    return argv + (['--', *positionals] if positionals else [])
