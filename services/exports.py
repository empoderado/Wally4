from __future__ import annotations

import io
from datetime import datetime

import pandas as pd


def dataframe_to_excel_bytes(sheets: dict[str, pd.DataFrame]) -> bytes:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        for sheet_name, df in sheets.items():
            safe_name = sheet_name[:31] or "Datos"
            df.to_excel(writer, index=False, sheet_name=safe_name)
            workbook = writer.book
            worksheet = writer.sheets[safe_name]
            header_fmt = workbook.add_format({"bold": True, "bg_color": "#17365D", "font_color": "#FFFFFF"})
            for col_num, value in enumerate(df.columns.values):
                worksheet.write(0, col_num, value, header_fmt)
                width = max(10, min(34, max(len(str(value)), *(len(str(x)) for x in df[value].head(200).fillna("").tolist())) + 2))
                worksheet.set_column(col_num, col_num, width)
            worksheet.freeze_panes(1, 0)
            worksheet.autofilter(0, 0, max(len(df), 1), max(len(df.columns) - 1, 0))
    return output.getvalue()


def export_filename(prefix: str, extension: str = "xlsx") -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{stamp}.{extension}"
