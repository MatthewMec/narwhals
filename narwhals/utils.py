from __future__ import annotations

import re
from typing import TYPE_CHECKING
from typing import Any
from typing import Iterable
from typing import Sequence
from typing import TypeVar
from typing import cast

from narwhals import dtypes
from narwhals.dependencies import get_cudf
from narwhals.dependencies import get_modin
from narwhals.dependencies import get_pandas
from narwhals.dependencies import get_polars
from narwhals.dependencies import get_pyarrow
from narwhals.translate import to_native

if TYPE_CHECKING:
    from narwhals.dataframe import BaseFrame
    from narwhals.series import Series

T = TypeVar("T")


def remove_prefix(text: str, prefix: str) -> str:
    if text.startswith(prefix):
        return text[len(prefix) :]
    return text  # pragma: no cover


def remove_suffix(text: str, suffix: str) -> str:  # pragma: no cover
    if text.endswith(suffix):
        return text[: -len(suffix)]
    return text  # pragma: no cover


def flatten(args: Any) -> list[Any]:
    if not args:
        return []
    if len(args) == 1 and _is_iterable(args[0]):
        return args[0]  # type: ignore[no-any-return]
    return args  # type: ignore[no-any-return]


def tupleify(arg: Any) -> Any:
    if not isinstance(arg, (list, tuple)):  # pragma: no cover
        return (arg,)
    return arg


def _is_iterable(arg: Any | Iterable[Any]) -> bool:
    from narwhals.series import Series

    if (pd := get_pandas()) is not None and isinstance(arg, (pd.Series, pd.DataFrame)):
        msg = f"Expected Narwhals class or scalar, got: {type(arg)}. Perhaps you forgot a `nw.from_native` somewhere?"
        raise TypeError(msg)
    if (pl := get_polars()) is not None and isinstance(
        arg, (pl.Series, pl.Expr, pl.DataFrame, pl.LazyFrame)
    ):
        msg = (
            f"Expected Narwhals class or scalar, got: {type(arg)}.\n\n"
            "Hint: Perhaps you\n"
            "- forgot a `nw.from_native` somewhere?\n"
            "- used `pl.col` instead of `nw.col`?"
        )
        raise TypeError(msg)

    return isinstance(arg, Iterable) and not isinstance(arg, (str, bytes, Series))


def parse_version(version: Sequence[str | int]) -> tuple[int, ...]:
    """Simple version parser; split into a tuple of ints for comparison."""
    # lifted from Polars
    if isinstance(version, str):  # pragma: no cover
        version = version.split(".")
    return tuple(int(re.sub(r"\D", "", str(v))) for v in version)


def isinstance_or_issubclass(obj: Any, cls: Any) -> bool:
    from narwhals.dtypes import DType

    if isinstance(obj, DType):
        return isinstance(obj, cls)
    return isinstance(obj, cls) or issubclass(obj, cls)


def validate_same_library(items: Iterable[Any]) -> None:
    if all(item._is_polars for item in items):
        return
    if all(hasattr(item._dataframe, "_implementation") for item in items) and (
        len({item._dataframe._implementation for item in items}) == 1
    ):
        return
    raise NotImplementedError("Cross-library comparisons aren't supported")


def validate_laziness(items: Iterable[Any]) -> None:
    from narwhals.dataframe import DataFrame
    from narwhals.dataframe import LazyFrame

    if all(isinstance(item, DataFrame) for item in items) or (
        all(isinstance(item, LazyFrame) for item in items)
    ):
        return
    raise NotImplementedError(
        "The items to concatenate should either all be eager, or all lazy"
    )


def maybe_align_index(lhs: T, rhs: Series | BaseFrame[Any]) -> T:
    """
    Align `lhs` to the Index of `rhs, if they're both pandas-like.

    Notes:
        This is only really intended for backwards-compatibility purposes,
        for example if your library already aligns indices for users.
        If you're designing a new library, we highly encourage you to not
        rely on the Index.
        For non-pandas-like inputs, this only checks that `lhs` and `rhs`
        are the same length.

    Examples:
        >>> import pandas as pd
        >>> import polars as pl
        >>> import narwhals as nw
        >>> df_pd = pd.DataFrame({"a": [1, 2]}, index=[3, 4])
        >>> s_pd = pd.Series([6, 7], index=[4, 3])
        >>> df = nw.from_native(df_pd)
        >>> s = nw.from_native(s_pd, series_only=True)
        >>> nw.to_native(nw.maybe_align_index(df, s))
           a
        4  2
        3  1
    """
    from narwhals._pandas_like.dataframe import PandasDataFrame
    from narwhals._pandas_like.series import PandasSeries

    def _validate_index(index: Any) -> None:
        if not index.is_unique:
            raise ValueError("given index doesn't have a unique index")

    lhs_any = cast(Any, lhs)
    rhs_any = cast(Any, rhs)
    if isinstance(getattr(lhs_any, "_dataframe", None), PandasDataFrame) and isinstance(
        getattr(rhs_any, "_dataframe", None), PandasDataFrame
    ):
        _validate_index(lhs_any._dataframe._native_dataframe.index)
        _validate_index(rhs_any._dataframe._native_dataframe.index)
        return lhs_any._from_dataframe(  # type: ignore[no-any-return]
            lhs_any._dataframe._from_native_dataframe(
                lhs_any._dataframe._native_dataframe.loc[
                    rhs_any._dataframe._native_dataframe.index
                ]
            )
        )
    if isinstance(getattr(lhs_any, "_dataframe", None), PandasDataFrame) and isinstance(
        getattr(rhs_any, "_series", None), PandasSeries
    ):
        _validate_index(lhs_any._dataframe._native_dataframe.index)
        _validate_index(rhs_any._series._native_series.index)
        return lhs_any._from_dataframe(  # type: ignore[no-any-return]
            lhs_any._dataframe._from_native_dataframe(
                lhs_any._dataframe._native_dataframe.loc[
                    rhs_any._series._native_series.index
                ]
            )
        )
    if isinstance(getattr(lhs_any, "_series", None), PandasSeries) and isinstance(
        getattr(rhs_any, "_dataframe", None), PandasDataFrame
    ):
        _validate_index(lhs_any._series._native_series.index)
        _validate_index(rhs_any._dataframe._native_dataframe.index)
        return lhs_any._from_series(  # type: ignore[no-any-return]
            lhs_any._series._from_native_series(
                lhs_any._series._native_series.loc[
                    rhs_any._dataframe._native_dataframe.index
                ]
            )
        )
    if isinstance(getattr(lhs_any, "_series", None), PandasSeries) and isinstance(
        getattr(rhs_any, "_series", None), PandasSeries
    ):
        _validate_index(lhs_any._series._native_series.index)
        _validate_index(rhs_any._series._native_series.index)
        return lhs_any._from_series(  # type: ignore[no-any-return]
            lhs_any._series._from_native_series(
                lhs_any._series._native_series.loc[rhs_any._series._native_series.index]
            )
        )
    if len(lhs_any) != len(rhs_any):
        msg = f"Expected `lhs` and `rhs` to have the same length, got {len(lhs_any)} and {len(rhs_any)}"
        raise ValueError(msg)
    return lhs


def maybe_set_index(df: T, column_names: str | list[str]) -> T:
    """
    Set columns `columns` to be the index of `df`, if `df` is pandas-like.

    Notes:
        This is only really intended for backwards-compatibility purposes,
        for example if your library already aligns indices for users.
        If you're designing a new library, we highly encourage you to not
        rely on the Index.
        For non-pandas-like inputs, this is a no-op.

    Examples:
        >>> import pandas as pd
        >>> import polars as pl
        >>> import narwhals as nw
        >>> df_pd = pd.DataFrame({"a": [1, 2], "b": [4, 5]})
        >>> df = nw.from_native(df_pd)
        >>> nw.to_native(nw.maybe_set_index(df, "b"))  # doctest: +NORMALIZE_WHITESPACE
           a
        b
        4  1
        5  2
    """
    from narwhals._pandas_like.dataframe import PandasDataFrame

    df_any = cast(Any, df)
    if isinstance(getattr(df_any, "_dataframe", None), PandasDataFrame):
        return df_any._from_dataframe(  # type: ignore[no-any-return]
            df_any._dataframe._from_native_dataframe(
                df_any._dataframe._native_dataframe.set_index(column_names)
            )
        )
    return df


def maybe_convert_dtypes(df: T, *args: bool, **kwargs: bool | str) -> T:
    """
    Convert columns to the best possible dtypes using dtypes supporting ``pd.NA``, if df is pandas-like.

    Notes:
        For non-pandas-like inputs, this is a no-op.
        Also, `args` and `kwargs` just get passed down to the underlying library as-is.

    Examples:
        >>> import pandas as pd
        >>> import polars as pl
        >>> import narwhals as nw
        >>> import numpy as np
        >>> df_pd = pd.DataFrame(
        ...     {
        ...         "a": pd.Series([1, 2, 3], dtype=np.dtype("int32")),
        ...         "b": pd.Series([True, False, np.nan], dtype=np.dtype("O")),
        ...     }
        ... )
        >>> df = nw.from_native(df_pd)
        >>> nw.to_native(nw.maybe_convert_dtypes(df)).dtypes  # doctest: +NORMALIZE_WHITESPACE
        a             Int32
        b           boolean
        dtype: object
    """
    from narwhals._pandas_like.dataframe import PandasDataFrame

    df_any = cast(Any, df)
    if isinstance(getattr(df_any, "_dataframe", None), PandasDataFrame):
        return df_any._from_dataframe(  # type: ignore[no-any-return]
            df_any._dataframe._from_native_dataframe(
                df_any._dataframe._native_dataframe.convert_dtypes(*args, **kwargs)
            )
        )
    return df


def is_ordered_categorical(series: Series) -> bool:
    """
    Return whether indices of categories are semantically meaningful.

    This is a convenience function to accessing what would otherwise be
    the `is_ordered` property from the DataFrame Interchange Protocol,
    see https://data-apis.org/dataframe-protocol/latest/API.html.

    - For Polars:
      - Enums are always ordered.
      - Categoricals are ordered if `dtype.ordering == "physical"`.
    - For pandas-like APIs:
      - Categoricals are ordered if `dtype.cat.ordered == True`.
    - For PyArrow table:
      - Categoricals are ordered if `dtype.type.ordered == True`.

    Examples:
        >>> import narwhals as nw
        >>> import pandas as pd
        >>> import polars as pl
        >>> data = ["x", "y"]
        >>> s_pd = pd.Series(data, dtype=pd.CategoricalDtype(ordered=True))
        >>> s_pl = pl.Series(data, dtype=pl.Categorical(ordering="physical"))

        Let's define a library-agnostic function:

        >>> @nw.narwhalify
        ... def func(s):
        ...     return nw.is_ordered_categorical(s)

        Then, we can pass any supported library to `func`:

        >>> func(s_pd)
        True
        >>> func(s_pl)
        True
    """
    if series.dtype == dtypes.Enum:
        return True
    if series.dtype != dtypes.Categorical:
        return False
    native_series = to_native(series)
    if (pl := get_polars()) is not None and isinstance(native_series, pl.Series):
        return native_series.dtype.ordering == "physical"  # type: ignore[no-any-return]
    if (pd := get_pandas()) is not None and isinstance(native_series, pd.Series):
        return native_series.cat.ordered  # type: ignore[no-any-return]
    if (mpd := get_modin()) is not None and isinstance(
        native_series, mpd.Series
    ):  # pragma: no cover
        return native_series.cat.ordered  # type: ignore[no-any-return]
    if (cudf := get_cudf()) is not None and isinstance(
        native_series, cudf.Series
    ):  # pragma: no cover
        return native_series.cat.ordered  # type: ignore[no-any-return]
    if (pa := get_pyarrow()) is not None and isinstance(native_series, pa.ChunkedArray):
        return native_series.type.ordered  # type: ignore[no-any-return]
    # If it doesn't match any of the above, let's just play it safe and return False.
    return False  # pragma: no cover
