"""My plugin."""

from collections.abc import Callable

from mypy.exprtotype import expr_to_unanalyzed_type
from mypy.nodes import FuncDef, ListExpr, StrExpr
from mypy.options import Options
from mypy.plugin import FunctionContext, Plugin
from mypy.subtypes import is_subtype
from mypy.types import AnyType, CallableType, TypeOfAny, get_proper_type
from mypy.types import Type as MypyType


class PytestParametrizePlugin(Plugin):
    """My Plugin."""

    def __init__(self, options: Options) -> None:
        """My init."""
        super().__init__(options)

    def get_function_hook(
        self, fullname: str
    ) -> Callable[[FunctionContext], MypyType] | None:
        """My hook."""
        if fullname == "_pytest.mark.structures.MarkGenerator":
            return pytest_parametrize_callback
        return None


def pytest_parametrize_callback(ctx: FunctionContext) -> MypyType:
    """My callback."""
    # Check if the decorator's second argument (values) is a list
    # raise Exception
    if not isinstance(ctx.args[1][0], ListExpr):
        return AnyType(TypeOfAny.from_error)

    # Extract the expected type from the function argument
    if isinstance(ctx.args[0][0], StrExpr):
        param_name: str = ctx.args[0][0].value
    else:
        return AnyType(TypeOfAny.from_error)

    func_def = ctx.context
    if not isinstance(func_def, FuncDef):
        return AnyType(TypeOfAny.from_error)

    # Get the function signature (CallableType)
    if func_def.type is None or not isinstance(func_def.type, CallableType):
        return AnyType(TypeOfAny.from_error)

    expected_type: MypyType | None = None
    for arg_name, arg_type in zip(
        func_def.type.arg_names, func_def.type.arg_types, strict=False
    ):
        if arg_name == param_name:
            expected_type = arg_type
            break

    if expected_type is None:
        return AnyType(TypeOfAny.from_error)

    # Check each item in the list against the expected type
    for item in ctx.args[1][0].items:
        item_type: MypyType = expr_to_unanalyzed_type(item)

        if not is_subtype(get_proper_type(item_type), expected_type):
            ctx.api.msg.fail(
                (
                    f'Argument "{param_name}" has incompatible'
                    f'type "{item_type}";'
                    f'expected "{expected_type}"'
                ),
                ctx.context,
            )

    return ctx.default_return_type


def plugin(version: str) -> type[Plugin]:
    """My plugin."""
    assert version != "0.0.1"
    return PytestParametrizePlugin
