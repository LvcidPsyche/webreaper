"""Vault — Data Management & Export.

Export crawl results to CSV, JSON, JSONL, Excel, SQLite.
Supports data versioning and webhook delivery.
"""

import asyncio
import csv
import io
import json
import logging
import sqlite3
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger("webreaper.vault")


class Vault:
    """Data export and management engine."""

    SUPPORTED_FORMATS = ["csv", "json", "jsonl", "xlsx", "sqlite"]

    async def export(
        self,
        data: list[dict],
        format: str,
        output_path: Optional[str] = None,
        filename: str = "export",
    ) -> str:
        """Export data to specified format. Returns output file path."""
        if format not in self.SUPPORTED_FORMATS:
            raise ValueError(f"Unsupported format: {format}. Use: {self.SUPPORTED_FORMATS}")

        if not output_path:
            output_path = f"./output/{filename}.{format}"

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        if format == "csv":
            return self._export_csv(data, output_path)
        elif format == "json":
            return self._export_json(data, output_path)
        elif format == "jsonl":
            return self._export_jsonl(data, output_path)
        elif format == "xlsx":
            return self._export_xlsx(data, output_path)
        elif format == "sqlite":
            return self._export_sqlite(data, output_path)

        return output_path

    def _export_csv(self, data: list[dict], path: str) -> str:
        if not data:
            Path(path).write_text("")
            return path

        fieldnames = list(data[0].keys())
        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in data:
                # Flatten nested dicts/lists to strings
                flat = {k: json.dumps(v) if isinstance(v, (dict, list)) else v for k, v in row.items()}
                writer.writerow(flat)
        logger.info(f"Exported {len(data)} rows to CSV: {path}")
        return path

    def _export_json(self, data: list[dict], path: str) -> str:
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)
        logger.info(f"Exported {len(data)} items to JSON: {path}")
        return path

    def _export_jsonl(self, data: list[dict], path: str) -> str:
        with open(path, "w") as f:
            for item in data:
                f.write(json.dumps(item, default=str) + "\n")
        logger.info(f"Exported {len(data)} items to JSONL: {path}")
        return path

    def _export_xlsx(self, data: list[dict], path: str) -> str:
        try:
            from openpyxl import Workbook
        except ImportError:
            raise ImportError("openpyxl required for Excel export: pip install openpyxl")

        wb = Workbook()
        ws = wb.active
        ws.title = "WebReaper Export"

        if not data:
            wb.save(path)
            return path

        headers = list(data[0].keys())
        ws.append(headers)

        for row in data:
            values = []
            for h in headers:
                v = row.get(h, "")
                if isinstance(v, (dict, list)):
                    v = json.dumps(v, default=str)
                values.append(v)
            ws.append(values)

        wb.save(path)
        logger.info(f"Exported {len(data)} rows to Excel: {path}")
        return path

    def _export_sqlite(self, data: list[dict], path: str) -> str:
        if not data:
            return path

        conn = sqlite3.connect(path)
        cursor = conn.cursor()

        # Create table from first row's keys
        columns = list(data[0].keys())
        col_defs = ", ".join(f'"{c}" TEXT' for c in columns)
        cursor.execute(f'CREATE TABLE IF NOT EXISTS export_data ({col_defs})')

        placeholders = ", ".join("?" * len(columns))
        for row in data:
            values = []
            for c in columns:
                v = row.get(c, "")
                if isinstance(v, (dict, list)):
                    v = json.dumps(v, default=str)
                values.append(str(v) if v is not None else "")
            cursor.execute(f"INSERT INTO export_data VALUES ({placeholders})", values)

        conn.commit()
        conn.close()
        logger.info(f"Exported {len(data)} rows to SQLite: {path}")
        return path

    async def webhook_deliver(self, url: str, data: list[dict], format: str = "json"):
        """POST export data to a webhook URL."""
        async with httpx.AsyncClient(timeout=30) as client:
            if format == "json":
                resp = await client.post(url, json=data)
            elif format == "jsonl":
                body = "\n".join(json.dumps(item, default=str) for item in data)
                resp = await client.post(
                    url,
                    content=body,
                    headers={"Content-Type": "application/x-ndjson"},
                )
            elif format == "csv":
                if not data:
                    return
                output = io.StringIO()
                writer = csv.DictWriter(output, fieldnames=list(data[0].keys()))
                writer.writeheader()
                writer.writerows(data)
                resp = await client.post(
                    url,
                    content=output.getvalue(),
                    headers={"Content-Type": "text/csv"},
                )
            else:
                resp = await client.post(url, json=data)

            resp.raise_for_status()
            logger.info(f"Delivered {len(data)} items to webhook: {url}")
