from __future__ import annotations

import io
from datetime import date, datetime
from typing import Any

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    KeepTogether,
    LongTable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
    Image,
)
from services.formatting import money, number, percent
from modules.dashboard_wally import _branch_total_row
from services.executive_tables import (
    _append_daily_total,
    _branch_range_total,
    _append_shipment_total,
    _line_performance_total,
)
from services.charts import build_branch_chart, build_line_chart, build_daily_chart



REPORT_TITLES = {
    "R-DASH-01": "KPIs Ventas",
    "T-DASH-01": "Resumen por sucursal",
    "T-GER-05": "Análisis de desempeño comercial por línea",
    "T-GER-04": "Comparativo 4 años rango fecha",
    "T-GER-03": "Tendencia de facturación por día contra históricos",
    "T-EXI-02": "Rotación por Embarque (15)",
}

MARGIN_CM = 1
MARGIN_INCHES = MARGIN_CM / 2.54


def _clean_value(value: Any) -> Any:
    if value is None or pd.isna(value):
        return ""
    if isinstance(value, (pd.Timestamp, datetime, date)):
        return value.strftime("%d/%m/%Y")
    return value


def _excel_value(value: Any) -> Any:
    cleaned = _clean_value(value)
    if isinstance(cleaned, (int, float, str, bool)):
        return cleaned
    return str(cleaned)


def executive_report_to_excel_bytes(
    sections: dict[str, pd.DataFrame],
    start_date: date,
    end_date: date,
) -> bytes:
    output = io.BytesIO()
    period = f"{start_date:%d/%m/%Y} al {end_date:%d/%m/%Y}"
    generated = datetime.now().strftime("%d/%m/%Y %H:%M")
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        workbook = writer.book
        title_format = workbook.add_format(
            {
                "bold": True,
                "font_size": 16,
                "font_color": "#17365D",
                "align": "left",
            }
        )
        meta_format = workbook.add_format({"font_color": "#475569", "font_size": 10})
        header_format = workbook.add_format(
            {
                "bold": True,
                "bg_color": "#17365D",
                "font_color": "#FFFFFF",
                "border": 1,
                "align": "center",
                "valign": "vcenter",
                "text_wrap": True,
            }
        )
        body_format = workbook.add_format({"border": 1, "valign": "top"})
        numeric_format = workbook.add_format({"border": 1, "num_format": "#,##0.00"})

        for index, (code, frame) in enumerate(sections.items(), start=1):
            sheet_name = code[:31]
            data = frame.copy() if isinstance(frame, pd.DataFrame) else pd.DataFrame()
            data = data.map(_excel_value)
            data.to_excel(writer, sheet_name=sheet_name, startrow=5, index=False, header=False)
            worksheet = writer.sheets[sheet_name]
            title = REPORT_TITLES.get(code, code)
            last_column = max(len(data.columns) - 1, 0)
            worksheet.merge_range(0, 0, 0, last_column, "Wally4 - Resumen Ejecutivo", title_format)
            worksheet.merge_range(1, 0, 1, last_column, f"Codigo: {code} | {title}", meta_format)
            worksheet.merge_range(2, 0, 2, last_column, f"Periodo: {period}", meta_format)
            worksheet.merge_range(3, 0, 3, last_column, f"Generado: {generated}", meta_format)

            for column_number, column in enumerate(data.columns):
                worksheet.write(5, column_number, str(column), header_format)
                values = data[column].astype(str).head(250).tolist()
                width = max([len(str(column)), *[len(value) for value in values]] or [10])
                worksheet.set_column(column_number, column_number, min(max(width + 2, 10), 28))
                if pd.api.types.is_numeric_dtype(frame[column]):
                    worksheet.set_column(column_number, column_number, min(max(width + 2, 10), 18), numeric_format)
                else:
                    worksheet.set_column(column_number, column_number, min(max(width + 2, 10), 28), body_format)

            worksheet.freeze_panes(6, 0)
            worksheet.autofilter(5, 0, max(len(data) + 5, 5), last_column)
            worksheet.set_landscape()
            worksheet.set_paper(1)
            worksheet.fit_to_pages(1, 0)
            worksheet.set_margins(
                left=MARGIN_INCHES,
                right=MARGIN_INCHES,
                top=MARGIN_INCHES,
                bottom=MARGIN_INCHES,
            )
            worksheet.repeat_rows(0, 5)
            worksheet.set_header("&LWally4 - Resumen Ejecutivo&R" + code)
            worksheet.set_footer("&LPeriodo: " + period + "&CPagina &P de &N&RGenerado: " + generated)
            worksheet.print_area(0, 0, max(len(data) + 5, 5), last_column)
            worksheet.hide_gridlines(2)
            worksheet.set_tab_color(["#17365D", "#C00000", "#70AD47"][index % 3])
    return output.getvalue()


def format_pct(val, already_multiplied=True):
    if val is None or pd.isna(val):
        return "-"
    try:
        f_val = float(val)
        if already_multiplied:
            f_val = f_val / 100.0
        return percent(f_val)
    except Exception:
        return str(val)


def get_year_headers(columns, years_dict=None):
    headers = []
    y_hist_1 = str(years_dict.get("hist_1", "2023")) if years_dict else "2023"
    y_hist_2 = str(years_dict.get("hist_2", "2024")) if years_dict else "2024"
    y_previous = str(years_dict.get("previous", "2025")) if years_dict else "2025"
    y_current = str(years_dict.get("current", "2026")) if years_dict else "2026"
    
    for col in columns:
        if "Historico2023Unid" in col:
            headers.append(f"{y_hist_1} Unid")
        elif "Historico2023VentaNeta" in col:
            headers.append(f"{y_hist_1} Vta")
        elif "Historico2024Unid" in col:
            headers.append(f"{y_hist_2} Unid")
        elif "Historico2024VentaNeta" in col:
            headers.append(f"{y_hist_2} Vta")
        elif "AnioAnteriorUnid" in col:
            headers.append(f"{y_previous} Unid")
        elif "AnioAnteriorVentaNeta" in col:
            headers.append(f"{y_previous} Vta")
        elif "HoyUnid" in col:
            headers.append(f"{y_current} Unid")
        elif "HoyVentaNeta" in col:
            headers.append(f"{y_current} Vta")
        elif "VariacionUnidPct" in col:
            headers.append("Var Unid %")
        elif "VariacionVentaPct" in col:
            headers.append("Var Vta %")
        elif "VariacionPromUnidPct" in col:
            headers.append("Var Prom Unid %")
        elif "VariacionPromVentaPct" in col:
            headers.append("Var Prom Vta %")
        elif "PromHistoricoUnid" in col:
            headers.append("Prom Hist Unid")
        elif "PromHistoricoVentaNeta" in col:
            headers.append("Prom Hist Vta")
        elif col == "Ranking":
            headers.append("Rk")
        else:
            headers.append(col)
    return headers


def get_semaforo_paragraph(value: str) -> Paragraph:
    status = str(value).strip().lower()
    if "verde" in status:
        style = ParagraphStyle(
            "GreenSemaforo",
            fontName="Helvetica-Bold",
            fontSize=5.5,
            leading=6.5,
            textColor=colors.HexColor("#166534"),
            backColor=colors.HexColor("#dcfce7"),
            borderPadding=1.5,
            alignment=TA_CENTER
        )
        txt = "VERDE"
    elif "amarillo" in status:
        style = ParagraphStyle(
            "YellowSemaforo",
            fontName="Helvetica-Bold",
            fontSize=5.5,
            leading=6.5,
            textColor=colors.HexColor("#92400e"),
            backColor=colors.HexColor("#fef3c7"),
            borderPadding=1.5,
            alignment=TA_CENTER
        )
        txt = "AMARILLO"
    else: # Rojo
        style = ParagraphStyle(
            "RedSemaforo",
            fontName="Helvetica-Bold",
            fontSize=5.5,
            leading=6.5,
            textColor=colors.HexColor("#991b1b"),
            backColor=colors.HexColor("#fee2e2"),
            borderPadding=1.5,
            alignment=TA_CENTER
        )
        txt = "ROJO"
    return Paragraph(txt, style)


def make_kpi_card(label: str, value_str: str, bar_color: colors.Color, card_width: float) -> Table:
    label_style = ParagraphStyle(
        "KPILabel",
        fontName="Helvetica-Bold",
        fontSize=6.5,
        leading=8,
        textColor=colors.HexColor("#64748b"),
    )
    value_style = ParagraphStyle(
        "KPIValue",
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=14,
        textColor=colors.HexColor("#0e0c15"),
    )
    
    content_p = [
        Paragraph(label.upper(), label_style),
        Spacer(1, 4),
        Paragraph(value_str, value_style)
    ]
    
    card_table = Table(
        [[ "", content_p ]],
        colWidths=[3, card_width - 3]
    )
    card_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.white),
        ('BACKGROUND', (0, 0), (0, 0), bar_color),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (1, 0), (1, 0), 8),
        ('RIGHTPADDING', (1, 0), (1, 0), 8),
        ('TOPPADDING', (1, 0), (1, 0), 6),
        ('BOTTOMPADDING', (1, 0), (1, 0), 6),
        ('TOPPADDING', (0, 0), (0, 0), 0),
        ('BOTTOMPADDING', (0, 0), (0, 0), 0),
        ('LEFTPADDING', (0, 0), (0, 0), 0),
        ('RIGHTPADDING', (0, 0), (0, 0), 0),
    ]))
    return card_table


def build_kpi_grid(frame: pd.DataFrame, available_width: float) -> Table:
    cards = []
    for idx, row in frame.iterrows():
        indicator = str(row["Indicador"])
        val = row["Valor"]
        
        if indicator in ["Venta Neta Q", "Ticket Promedio", "Vr Unidad Promedio", "Margen Q", "Descuento Q"]:
            formatted = money(val)
        elif indicator == "% Margen":
            formatted = percent(val)
        elif indicator == "UPT":
            formatted = number(val, 2)
        else:
            formatted = number(val, 0)
            
        if "Margen" in indicator:
            bar_color = colors.HexColor("#0f766e")
        elif "Venta" in indicator:
            bar_color = colors.HexColor("#6c1c36")
        elif "Descuento" in indicator:
            bar_color = colors.HexColor("#d97706")
        else:
            bar_color = colors.HexColor("#3b82f6")
            
        card_width = (available_width - 24) / 3
        card = make_kpi_card(indicator, formatted, bar_color, card_width)
        cards.append(card)
        
    col_w = [(available_width - 24) / 3, 12, (available_width - 24) / 3, 12, (available_width - 24) / 3]
    grid_data = [
        [cards[0], "", cards[1], "", cards[2]],
        ["", "", "", "", ""],
        [cards[3], "", cards[4], "", cards[5]],
        ["", "", "", "", ""],
        [cards[6], "", cards[7], "", cards[8]]
    ]
    grid_table = Table(grid_data, colWidths=col_w, rowHeights=[38, 12, 38, 12, 38])
    grid_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    return grid_table


def build_pdf_table(code: str, frame: pd.DataFrame, available_width: float, years_dict: dict = None) -> LongTable:
    if frame.empty:
        return Table([[Paragraph("No hay datos para esta sección.", ParagraphStyle("EmptyText", fontName="Helvetica", fontSize=8, leading=10))]], colWidths=[available_width])
    data = frame.copy()
    if code == "T-DASH-01":
        total_row = _branch_total_row(data)
        data = pd.concat([data, pd.DataFrame([total_row])], ignore_index=True)
        data = data[["Ranking", "Sucursal", "Unidades", "VentaNetaQ", "Facturas", "Upt", "FactProm", "VrPromedioUnidad", "MargenQ", "%Margen", "DescuentoQ", "%Desc", "%VentaSuc", "Semáforo"]]
    elif code == "T-GER-05":
        data = _line_performance_total(data)
        data = data[["Linea", "StockUnidades", "VentasUnidades", "VentaQ", "VentaDolar", "PorcVenta", "PresupuestoUnidades", "PresupuestoVenta", "CumplUnidades", "CumplVenta"]]
    elif code == "T-GER-04":
        data = _branch_range_total(data)
        data = data[["Ranking", "Sucursal", "Historico2023Unid", "Historico2023VentaNeta", "Historico2024Unid", "Historico2024VentaNeta", "AnioAnteriorUnid", "AnioAnteriorVentaNeta", "HoyUnid", "HoyVentaNeta", "VariacionUnidPct", "VariacionVentaPct"]]
    elif code == "T-GER-03":
        data = _append_daily_total(data)
        data = data[["Dia", "Historico2023Unid", "Historico2023VentaNeta", "Historico2024Unid", "Historico2024VentaNeta", "AnioAnteriorUnid", "AnioAnteriorVentaNeta", "PromHistoricoUnid", "PromHistoricoVentaNeta", "HoyUnid", "HoyVentaNeta", "VariacionUnidPct", "VariacionVentaPct", "VariacionPromUnidPct", "VariacionPromVentaPct"]]
    elif code == "T-EXI-02":
        data = _append_shipment_total(data)
        data = data[["Embarque", "Fecha Entrada Dia 1", "TVida", "Entrada", "Existencia Fisica", "Unidades Facturadas", "%Rotacion"]]
    
    col_headers = []
    col_alignments = []
    col_formats = []
    col_widths = []
    
    if code == "T-DASH-01":
        col_headers = ["Rk", "Sucursal", "Unidades", "Venta Neta", "Facturas", "UPT", "T. Prom", "V. Unid", "Margen", "% Marg", "Desc.", "% Desc", "% Vta", "Semáforo"]
        col_alignments = [1, 0, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1]
        col_formats = ['int', 'text', 'int', 'money', 'int', 'float2', 'money', 'money', 'money', 'percent', 'money', 'percent', 'percent', 'semaforo']
        raw_widths = [20, 85, 42, 65, 42, 30, 52, 52, 58, 42, 52, 42, 42, 50]
        total_raw = sum(raw_widths)
        col_widths = [w * (available_width / total_raw) for w in raw_widths]
        
    elif code == "T-GER-05":
        col_headers = ["Línea", "Stock", "Vtas Unid", "Venta (Q)", "Venta (USD)", "% Vta", "Pto Unid", "Pto Vta (Q)", "% C. Unid", "% C. Vta"]
        col_alignments = [0, 2, 2, 2, 2, 2, 2, 2, 2, 2]
        col_formats = ['text', 'int', 'int', 'money', 'usd', 'percent_raw', 'int', 'money', 'percent_raw', 'percent_raw']
        raw_widths = [110, 55, 55, 75, 75, 55, 60, 75, 60, 60]
        total_raw = sum(raw_widths)
        col_widths = [w * (available_width / total_raw) for w in raw_widths]
        
    elif code == "T-GER-04":
        col_headers = get_year_headers(data.columns, years_dict)
        col_alignments = [1, 0] + [2] * (len(data.columns) - 2)
        for col in data.columns:
            if col == "Ranking":
                col_formats.append('int')
            elif col == "Sucursal":
                col_formats.append('text')
            elif "Pct" in col:
                col_formats.append('percent_raw')
            elif "Unid" in col:
                col_formats.append('int')
            elif "VentaNeta" in col or "Venta" in col:
                col_formats.append('money')
            else:
                col_formats.append('text')
        raw_widths = [22, 110, 42, 60, 42, 60, 42, 60, 42, 60, 45, 45]
        total_raw = sum(raw_widths)
        col_widths = [w * (available_width / total_raw) for w in raw_widths]
        
    elif code == "T-GER-03":
        col_headers = get_year_headers(data.columns, years_dict)
        col_alignments = [1] + [2] * (len(data.columns) - 1)
        for col in data.columns:
            if col == "Dia":
                col_formats.append('text')
            elif "Pct" in col:
                col_formats.append('percent_raw')
            elif "Unid" in col:
                col_formats.append('int')
            elif "VentaNeta" in col or "Venta" in col:
                col_formats.append('money')
            else:
                col_formats.append('text')
        raw_widths = [35] + [48] * (len(data.columns) - 1)
        total_raw = sum(raw_widths)
        col_widths = [w * (available_width / total_raw) for w in raw_widths]
        
    elif code == "T-EXI-02":
        col_headers = ["Embarque", "Fecha Entrada Día 1", "T. Vida (días)", "Entrada", "Exist. Física", "Unid. Facturadas", "% Rotación"]
        col_alignments = [0, 1, 2, 2, 2, 2, 2]
        col_formats = ['text', 'date', 'int', 'int', 'int', 'int', 'percent_raw']
        raw_widths = [120, 90, 70, 70, 70, 80, 70]
        total_raw = sum(raw_widths)
        col_widths = [w * (available_width / total_raw) for w in raw_widths]
        
    else:
        col_headers = list(data.columns)
        col_alignments = [0] * len(data.columns)
        col_formats = ['text'] * len(data.columns)
        col_widths = [available_width / len(data.columns)] * len(data.columns)
        
    is_dense = (code in ["T-DASH-01", "T-GER-03", "T-GER-04"])
    header_font_size = 5.5 if is_dense else 6.5
    body_font_size = 5.0 if is_dense else 6.0
    leading_ratio = 1.2
    
    header_style = ParagraphStyle(
        "TableHeader",
        fontName="Helvetica-Bold",
        fontSize=header_font_size,
        leading=header_font_size * leading_ratio,
        textColor=colors.white,
        alignment=TA_CENTER
    )
    
    header_cells = [Paragraph(str(h), header_style) for h in col_headers]
    rows = [header_cells]
    
    total_row_indices = []
    for r_idx, row in data.iterrows():
        is_total = False
        if code == "T-DASH-01" and str(row.get("Sucursal", "")).strip().lower() == "total":
            is_total = True
        elif code == "T-GER-05" and str(row.get("Linea", "")).strip().upper() == "TOTAL":
            is_total = True
        elif code == "T-GER-04" and str(row.get("Sucursal", "")).strip().lower() == "total":
            is_total = True
        elif code == "T-GER-03" and str(row.get("Dia", "")).strip().lower() == "total acumulado":
            is_total = True
        elif code == "T-EXI-02" and str(row.get("Embarque", "")).strip().lower() == "total":
            is_total = True
            
        if is_total:
            total_row_indices.append(r_idx + 1)
            
        row_cells = []
        for c_idx, val in enumerate(row):
            fmt = col_formats[c_idx]
            align = col_alignments[c_idx]
            
            if fmt == 'semaforo':
                row_cells.append(get_semaforo_paragraph(str(val)))
                continue
                
            formatted_str = ""
            if val is None or pd.isna(val) or val == "":
                formatted_str = "-"
            else:
                try:
                    if fmt == 'int':
                        if c_idx == 0 and is_total:
                            formatted_str = ""
                        else:
                            formatted_str = number(val, 0)
                    elif fmt == 'float2':
                        formatted_str = number(val, 2)
                    elif fmt == 'money':
                        formatted_str = money(val)
                    elif fmt == 'percent':
                        formatted_str = percent(val)
                    elif fmt == 'percent_raw':
                        formatted_str = format_pct(val, already_multiplied=True)
                    elif fmt == 'usd':
                        formatted_str = f"US$ {number(val, 0)}"
                    elif fmt == 'date':
                        if isinstance(val, (pd.Timestamp, datetime, date)):
                            formatted_str = val.strftime("%d/%m/%Y")
                        else:
                            formatted_str = str(val)
                    else:
                        formatted_str = str(val)
                except Exception:
                    formatted_str = str(val)
                    
            font_name = "Helvetica-Bold" if is_total else "Helvetica"
            text_color = colors.HexColor("#0f172a")
            
            if fmt == 'percent_raw' and not is_total and formatted_str != "-":
                try:
                    pct_val = float(val)
                    if pct_val > 0:
                        text_color = colors.HexColor("#047857")
                        formatted_str = "▲ " + formatted_str
                    elif pct_val < 0:
                        text_color = colors.HexColor("#dc2626")
                        formatted_str = "▼ " + formatted_str
                except Exception:
                    pass
                    
            cell_style = ParagraphStyle(
                f"Cell_{code}_{r_idx}_{c_idx}",
                fontName=font_name,
                fontSize=body_font_size,
                leading=body_font_size * leading_ratio,
                textColor=text_color,
                alignment=align
            )
            row_cells.append(Paragraph(formatted_str, cell_style))
            
        rows.append(row_cells)
        
    table = LongTable(rows, colWidths=col_widths, repeatRows=1, hAlign="LEFT")
    
    pad_val = 2 if is_dense else 3
    t_style = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#6c1c36")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#E2E8F0")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), pad_val),
        ("RIGHTPADDING", (0, 0), (-1, -1), pad_val),
        ("TOPPADDING", (0, 0), (-1, -1), pad_val),
        ("BOTTOMPADDING", (0, 0), (-1, -1), pad_val),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#FCFBFA")]),
    ]
    
    for t_idx in total_row_indices:
        t_style.extend([
            ("BACKGROUND", (0, t_idx), (-1, t_idx), colors.HexColor("#fef2f2")),
            ("LINEABOVE", (0, t_idx), (-1, t_idx), 1, colors.HexColor("#6c1c36")),
        ])
        
    table.setStyle(TableStyle(t_style))
    return table


def executive_report_to_pdf_bytes(
    sections: dict[str, pd.DataFrame],
    start_date: date,
    end_date: date,
    years: dict[str, int] = None,
) -> bytes:
    output = io.BytesIO()
    page_size = landscape(letter)
    period = f"{start_date:%d/%m/%Y} al {end_date:%d/%m/%Y}"
    generated = datetime.now().strftime("%d/%m/%Y %H:%M")
    
    # Filter sections to strictly include only the approved ones in the correct order
    allowed_keys = ["R-DASH-01", "T-DASH-01", "T-GER-05", "T-GER-04", "T-GER-03", "T-EXI-02"]
    filtered_sections = {k: sections[k] for k in allowed_keys if k in sections}
    
    document = SimpleDocTemplate(
        output,
        pagesize=page_size,
        leftMargin=MARGIN_CM * cm,
        rightMargin=MARGIN_CM * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        title="Resumen Ejecutivo Bagneres",
        author="Wally4",
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ExecutiveTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#6c1c36"),
        spaceAfter=3,
    )
    section_style = ParagraphStyle(
        "ExecutiveSection",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
        textColor=colors.HexColor("#6c1c36"),
        spaceAfter=6,
    )
    meta_style = ParagraphStyle(
        "ExecutiveMeta",
        parent=styles["Normal"],
        fontSize=9,
        leading=11,
        textColor=colors.HexColor("#475569"),
    )

    story = [
        Paragraph("Resumen Ejecutivo Bagneres", title_style),
        Paragraph(f"Período: {period} | Generado: {generated}", meta_style),
        Spacer(1, 8),
    ]
    for index, (code, frame) in enumerate(filtered_sections.items()):
        if index:
            story.append(PageBreak())
        title = REPORT_TITLES.get(code, code)
        heading = KeepTogether(
            [
                Paragraph(f"{code} | {title}", section_style),
                Spacer(1, 3),
            ]
        )
        story.append(heading)
        if frame.empty:
            story.append(Paragraph("No hay datos para el periodo seleccionado.", meta_style))
        else:
            if code == "T-EXI-02" and len(frame) > 15:
                frame_to_render = frame.head(15)
            else:
                frame_to_render = frame
                
            if code == "R-DASH-01":
                story.append(build_kpi_grid(frame_to_render, document.width))
            else:
                story.append(build_pdf_table(code, frame_to_render, document.width, years_dict=years))
                
                # Check if we need to export a Plotly chart below the table
                if code in ["T-DASH-01", "T-GER-05", "T-GER-03"]:
                    try:
                        chart_w = int(document.width)
                        chart_h = 220
                        if code == "T-DASH-01":
                            fig = build_branch_chart(frame_to_render, height=chart_h)
                        elif code == "T-GER-05":
                            fig = build_line_chart(frame_to_render, height=chart_h)
                        else: # T-GER-03
                            fig = build_daily_chart(frame_to_render, years=years, height=chart_h)
                            
                        img_bytes = fig.to_image(format="png", width=chart_w, height=chart_h)
                        img_buf = io.BytesIO(img_bytes)
                        chart_img = Image(img_buf, width=chart_w, height=chart_h)
                        story.append(Spacer(1, 10))
                        story.append(chart_img)
                    except Exception as e:
                        # Log error inside PDF or simply pass to avoid crashes
                        err_style = ParagraphStyle(
                            "ChartError",
                            fontName="Helvetica-Oblique",
                            fontSize=7,
                            leading=9,
                            textColor=colors.HexColor("#dc2626")
                        )
                        story.append(Spacer(1, 5))
                        story.append(Paragraph(f"Error al generar gráfico {code}: {str(e)}", err_style))

    def draw_page(canvas, doc) -> None:
        canvas.saveState()
        width, height = page_size
        
        # --- Running Header ---
        canvas.setFont("Helvetica-Bold", 7.5)
        canvas.setFillColor(colors.HexColor("#6c1c36"))
        canvas.drawString(MARGIN_CM * cm, height - 0.9 * cm, "Resumen Ejecutivo Bagneres")
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.HexColor("#475569"))
        canvas.drawRightString(width - MARGIN_CM * cm, height - 0.9 * cm, f"Período: {period}")
        
        canvas.setStrokeColor(colors.HexColor("#E2E8F0"))
        canvas.setLineWidth(0.5)
        canvas.line(MARGIN_CM * cm, height - 1.1 * cm, width - MARGIN_CM * cm, height - 1.1 * cm)
        
        # --- Running Footer ---
        canvas.line(MARGIN_CM * cm, 1.1 * cm, width - MARGIN_CM * cm, 1.1 * cm)
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.HexColor("#475569"))
        canvas.drawString(MARGIN_CM * cm, 0.7 * cm, f"Período: {period}   |   Fecha de generación: {generated}")
        canvas.drawRightString(width - MARGIN_CM * cm, 0.7 * cm, f"Página {doc.page}")
        
        canvas.restoreState()

    document.build(story, onFirstPage=draw_page, onLaterPages=draw_page)
    return output.getvalue()
