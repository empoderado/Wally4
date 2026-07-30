from __future__ import annotations


REPORT_CODES = {
    "dashboard": {
        "report": ("R-DASH-01", "Kpis Ventas"),
        "branch_chart": ("G-DASH-01", "Grafico principal configurable por sucursal"),
        "time_chart": ("G-DASH-02", "Venta por hora"),
        "branch_table": ("T-DASH-01", "Resumen por sucursal"),
    },
    "asesores": {
        "report": ("R-ASE-01", "Reporte diario y acumulado por asesores"),
        "detail_table": ("T-ASE-01", "Detalle por sucursal, asesor, presupuesto y cumplimiento"),
    },
    "gerencia": {
        "report": ("R-GER-01", "Kpis gerenciales"),
        "year_table": ("T-GER-01", "Comparativo de ventas por fecha en los ultimos 4 anios"),
        "line_performance": ("T-GER-05", "Analisis de desempeno comercial por linea"),
        "subline_performance": ("T-GER-07", "Analisis de desempeno comercial por linea y sublinea"),
        "range_year_table": ("T-GER-04", "Comparativo 4 anios rango fecha"),
        "today_comparison_table": ("T-GER-06", "Comparativo dia actual vs anios anteriores"),
        "year_chart": ("G-GER-01", "Comparativo anual de venta neta y unidades"),
        "hour_table": ("T-GER-02", "Tendencia de facturacion por hora contra historicos"),
        "day_table": ("T-GER-03", "Tendencia de facturacion por dia contra historicos"),
    },
    "ventas": {
        "report": ("R-VEN-01", "Reporte de ventas"),
        "main_chart": ("G-VEN-01", "Grafico configurable de ventas"),
        "detail_table": ("T-VEN-01", "Detalle de ventas"),
    },
    "existencias": {
        "report": ("R-EXI-01", "Reporte de existencias"),
        "main_chart": ("G-EXI-01", "Grafico configurable de existencias"),
        "line_chart": ("G-EXI-02", "Existencia por linea de producto"),
        "jeans_subline_chart": ("G-EXI-03", "Existencia linea Jeans por sublinea"),
        "detail_table": ("T-EXI-01", "Detalle de existencias"),
        "shipment_table": ("T-EXI-02", "Rotacion por Embarque (20)"),
        "rotacion_derivada": ("T-EXI-03", "Rotacion Derivada por Referencia"),
    },
    "entradas": {
        "report": ("R-ENT-01", "Reporte de entradas de inventario"),
        "main_chart": ("G-ENT-01", "Grafico configurable de entradas"),
        "detail_table": ("T-ENT-01", "Detalle de entradas"),
    },
    "embarques": {
        "report": ("R-EMB-01", "Reporte de embarques y coleccion"),
        "embarque_chart": ("G-EMB-01", "Venta neta por embarque"),
        "coleccion_chart": ("G-EMB-02", "Venta neta por coleccion"),
        "detail_table": ("T-EMB-01", "Detalle de embarques y coleccion"),
    },
    "crm": {
        "report": ("R-CRM-01", "Reporte CRM de clientes sin compra"),
        "candidates_table": ("T-CRM-01", "Clientes sugeridos por Wally"),
        "assignments_table": ("T-CRM-02", "Asignaciones locales CRM"),
        "management_form": ("F-CRM-01", "Formulario de gestion CRM"),
        "history_table": ("T-CRM-03", "Historial de gestiones CRM"),
    },
    "metas": {
        "report": ("R-MET-01", "Reporte de metas y presupuesto"),
        "form": ("F-MET-01", "Formulario de meta por sucursal"),
        "compliance_table": ("T-MET-01", "Cumplimiento por sucursal"),
        "targets_table": ("T-MET-02", "Metas locales registradas"),
    },
    "presupuesto": {
        "report": ("R-PTO-01", "Modulo de presupuestos"),
        "import_branch": ("F-PTO-01", "Importar presupuesto por sucursal"),
        "import_seller": ("F-PTO-02", "Importar presupuesto por vendedor"),
        "import_line_branch": ("F-PTO-03", "Importar presupuesto por linea y sucursal"),
        "modify_seller": ("F-PTO-04", "Modificar presupuesto de Asesora"),
        "branch_summary": ("T-PTO-00", "Resumen de presupuesto por sucursal"),
        "branch_matrix": ("T-PTO-01", "Presupuesto de sucursales por dia"),
        "branch_units_matrix": ("T-PTO-02", "Presupuesto de sucursales por dia en unidades"),
        "seller_table": ("T-PTO-03", "Presupuesto y cumplimiento por vendedor"),
    },
    "traslados": {
        "report": ("R-TRA-01", "Motor de cruces y traslados FIFO-XLS"),
        "config_table": ("T-TRA-00", "Prioridad configurable de tiendas para traslados"),
        "fifo_xl": ("T-TRA-01", "Salida FIFO-XLS de sugerencias de traslado"),
    },
    "auditoria": {
        "report": ("R-AUD-01", "Resumen de auditoria de documentos"),
        "detail_table": ("T-AUD-01", "Detalle de alertas de auditoria"),
        "users_table": ("T-AUD-02", "Usuarios con modificaciones"),
    },
    "colaboradores": {
        "report": ("R-COL-01", "Modulo de turnos de colaboradores"),
        "detail_table": ("T-COL-01", "Detalle de turnos de colaboradores"),
    },
}


def get_code(module: str, item: str) -> tuple[str, str]:
    return REPORT_CODES[module][item]
