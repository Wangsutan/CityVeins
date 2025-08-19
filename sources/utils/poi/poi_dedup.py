from __future__ import annotations
import io
import os
from pathlib import Path
from typing import Union, Optional, Literal

import pandas as pd

CSVInput = Union[str, io.StringIO, pd.DataFrame]
KeepStrategy = Literal["best", "first", "last"]


def dedup_poi_csv(
    src: CSVInput,
    *,
    key_cols: tuple[str, str, str] = ("POI名称", "经度", "纬度"),
    weight_col: str = "默认权重",
    dist_col: str = "距离(米)",
    keep: KeepStrategy = "best",
    encoding: str = "utf-8",
) -> pd.DataFrame:
    if isinstance(src, str) and os.path.isfile(src):
        # 如果 src 是一个字符串，并且该字符串表示一个有效的文件路径，则认为它是一个文件。
        df: pd.DataFrame = pd.read_csv(src, encoding=encoding)
    elif isinstance(src, str):
        # 如果 src 是一个字符串，但不是一个有效的文件路径，则认为它是一个 CSV 数据字符串。
        df = pd.read_csv(io.StringIO(src))
    elif isinstance(src, io.StringIO):
        # 如果 src 是一个 StringIO 对象，则认为它是一个内存中的文件类对象。
        src.seek(0)
        df = pd.read_csv(src)
    elif isinstance(src, pd.DataFrame):
        # 如果 src 是一个 pandas.DataFrame 对象，则认为它已经是 DataFrame 格式。
        df = src.copy()
    else:
        # 如果 src 不是上述任何一种支持的类型，则抛出 TypeError。
        raise TypeError

    df["__key"] = (
        df[key_cols[0]].astype(str)
        + "_"
        + df[key_cols[1]].astype(str)
        + "_"
        + df[key_cols[2]].astype(str)
    )

    if keep == "best":
        df = df.sort_values(by=[weight_col, dist_col], ascending=[False, True])
    elif keep == "last":
        df = df.iloc[::-1].reset_index(drop=True)

    df_out = df.drop_duplicates(subset=["__key"], keep="first")
    return df_out.drop(columns=["__key"]).reset_index(drop=True)


def dedup_poi_file(
    in_path: str | os.PathLike[str],
    out_path: Optional[str | os.PathLike[str]] = None,
    **kwargs,
) -> None:
    in_path = Path(in_path)
    out_path = (
        Path(out_path) if out_path else in_path.with_stem(f"{in_path.stem}_unique")
    )
    df = dedup_poi_csv(str(in_path), **kwargs)
    df.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"去重完成 → {out_path}")
