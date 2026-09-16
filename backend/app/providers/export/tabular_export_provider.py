"""`ExportProvider` fuer XLSX und CSV (Abschnitt 1.1, 11).

PDF-Export ist laut Abschnitt 1.1 optional und im MVP nicht implementiert.
"""
from __future__ import annotations

import csv
import os
from datetime import datetime

from openpyxl import Workbook

from app.providers.base import ExportProvider, ExportRequest, ExportResult


class UnsupportedExportFormatError(ValueError):
    pass


class TabularExportProvider(ExportProvider):
    def __init__(self, storage_path: str) -> None:
        self._storage_path = storage_path
        os.makedirs(self._storage_path, exist_ok=True)

    def export(self, request: ExportRequest) -> ExportResult:
        if request.file_format == "xlsx":
            storage_reference = self._export_xlsx(request)
        elif request.file_format == "csv":
            storage_reference = self._export_csv(request)
        else:
            raise UnsupportedExportFormatError(
                f"Exportformat '{request.file_format}' wird nicht unterstuetzt (nur xlsx, csv)."
            )
        return ExportResult(storage_reference=storage_reference, file_format=request.file_format, row_count=len(request.rows))

    def _target_path(self, export_id: str, extension: str) -> str:
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        filename = f"{timestamp}_{export_id}.{extension}"
        return os.path.join(self._storage_path, filename)

    def _export_xlsx(self, request: ExportRequest) -> str:
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Pruefergebnisse"

        columns = self._collect_columns(request.rows)
        sheet.append(columns)
        for row in request.rows:
            sheet.append([self._stringify(row.get(column)) for column in columns])

        path = self._target_path(request.export_id, "xlsx")
        workbook.save(path)
        return path

    def _export_csv(self, request: ExportRequest) -> str:
        columns = self._collect_columns(request.rows)
        path = self._target_path(request.export_id, "csv")
        with open(path, "w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns, delimiter=";")
            writer.writeheader()
            for row in request.rows:
                writer.writerow({column: self._stringify(row.get(column)) for column in columns})
        return path

    @staticmethod
    def _collect_columns(rows: list[dict]) -> list[str]:
        columns: list[str] = []
        for row in rows:
            for key in row:
                if key not in columns:
                    columns.append(key)
        return columns

    @staticmethod
    def _stringify(value) -> str:
        if value is None:
            return ""
        return str(value)
