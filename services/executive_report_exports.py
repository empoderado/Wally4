from __future__ import annotations

import io
from datetime import date, datetime
from typing import Any

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
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
)


REPORT_TITLES = {
    "R-DASH-01": "KPIs Ventas",
    "T-DASH-01": "Resumen por sucursal",
    "T-GER-05": "Analisis de desempeno comercial por linea",
    "T-GER-04": "Comparativo 4 anios rango fecha",
    "T-GER-03": "Tendencia de facturacion por dia contra historicos",
    "T-EXI-02": "Rotacion por Embarque (15)",
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


def _pdf_text(value: Any) -> str:
    cleaned = _clean_value(value)
    if isinstance(cleaned, float):
        return f"{cleaned:,.2f}"
    return str(cleaned)


def _pdf_table(frame: pd.DataFrame, available_width: float) -> LongTable:
    data = frame.copy()
    headers = [Paragraph(str(column), ParagraphStyle("TableHeader", fontName="Helvetica-Bold", fontSize=6.2, leading=7.2, textColor=colors.white, alignment=TA_CENTER)) for column in data.columns]
    rows = [headers]
    cell_style = ParagraphStyle("TableCell", fontName="Helvetica", fontSize=5.8, leading=6.8)
    for values in data.itertuples(index=False, name=None):
        rows.append([Paragraph(_pdf_text(value), cell_style) for value in values])

    column_count = max(len(data.columns), 1)
    widths = [available_width / column_count] * column_count
    table = LongTable(rows, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#17365D")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5E1")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 2.5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2.5),
                ("TOPPADDING", (0, 0), (-1, -1), 2.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
            ]
        )
    )
    return table


def executive_report_to_pdf_bytes(
    sections: dict[str, pd.DataFrame],
    start_date: date,
    end_date: date,
) -> bytes:
    output = io.BytesIO()
    page_size = landscape(letter)
    period = f"{start_date:%d/%m/%Y} al {end_date:%d/%m/%Y}"
    generated = datetime.now().strftime("%d/%m/%Y %H:%M")
    document = SimpleDocTemplate(
        output,
        pagesize=page_size,
        leftMargin=MARGIN_CM * cm,
        rightMargin=MARGIN_CM * cm,
        topMargin=MARGIN_CM * cm,
        bottomMargin=MARGIN_CM * cm,
        title="Wally4 - Resumen Ejecutivo",
        author="Wally4",
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ExecutiveTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=15,
        leading=18,
        textColor=colors.HexColor("#17365D"),
        spaceAfter=3,
    )
    section_style = ParagraphStyle(
        "ExecutiveSection",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=13,
        textColor=colors.HexColor("#B91C1C"),
        spaceAfter=6,
    )
    meta_style = ParagraphStyle(
        "ExecutiveMeta",
        parent=styles["Normal"],
        fontSize=8.5,
        leading=10,
        textColor=colors.HexColor("#475569"),
    )

    story = [
        Paragraph("Wally4 - Resumen Ejecutivo", title_style),
        Paragraph(f"Periodo: {period} | Generado: {generated}", meta_style),
        Spacer(1, 8),
    ]
    for index, (code, frame) in enumerate(sections.items()):
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
            story.append(_pdf_table(frame, document.width))

    def draw_page(canvas, doc) -> None:
        canvas.saveState()
        width, _ = page_size
        canvas.setStrokeColor(colors.HexColor("#CBD5E1"))
        canvas.line(MARGIN_CM * cm, 1.05 * cm, width - MARGIN_CM * cm, 1.05 * cm)
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.HexColor("#475569"))
        canvas.drawString(MARGIN_CM * cm, 0.7 * cm, f"Generado: {generated}")
        canvas.drawRightString(width - MARGIN_CM * cm, 0.7 * cm, f"Pagina {doc.page}")
        canvas.restoreState()

    document.build(story, onFirstPage=draw_page, onLaterPages=draw_page)
    return output.getvalue()
