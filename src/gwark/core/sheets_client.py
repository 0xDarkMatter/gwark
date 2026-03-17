"""Google Sheets client using gspread.

High-level wrapper around gspread for elegant spreadsheet operations.
Uses Gwark's OAuth system for authentication.

Example:
    >>> from gwark.core.sheets_client import SheetsClient
    >>> client = SheetsClient.from_gwark_auth()
    >>> sheets = client.list_spreadsheets()
    >>> data = client.read_range("1abc...", "Sheet1!A1:D10")
"""

import re
from typing import Any, List, Optional, Dict, Union, Tuple

import gspread
from gspread import Spreadsheet, Worksheet
from gspread.utils import ExportFormat

from gwark.core.async_utils import AsyncFetcher, run_async

# Optional pandas support - deferred import
try:
    import pandas as pd
    from gspread_dataframe import set_with_dataframe, get_as_dataframe
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False
    pd = None


class SheetsClient:
    """High-level client for Google Sheets operations using gspread.

    Provides a clean, Pythonic interface for spreadsheet operations.
    Supports both simple operations and batch operations for efficiency.

    Attributes:
        client: The underlying gspread.Client instance
    """

    def __init__(self, client: gspread.Client):
        """Initialize with an authenticated gspread client.

        Args:
            client: Authenticated gspread.Client instance
        """
        self.client = client

    @classmethod
    def from_gwark_auth(cls) -> "SheetsClient":
        """Create client using Gwark's OAuth system.

        This is the recommended way to create a SheetsClient.
        Uses existing OAuth tokens from .gwark/tokens/ or triggers
        OAuth flow if needed.

        Returns:
            SheetsClient: Authenticated client ready for use

        Example:
            >>> client = SheetsClient.from_gwark_auth()
            >>> sheets = client.list_spreadsheets()
        """
        from gmail_mcp.auth import get_sheets_client
        return cls(get_sheets_client())

    # =========================================================================
    # SPREADSHEET OPERATIONS
    # =========================================================================

    def list_spreadsheets(
        self,
        max_results: int = 50,
        query: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List all accessible spreadsheets.

        Args:
            max_results: Maximum number of results to return
            query: Optional search query to filter results

        Returns:
            List of dicts with id, name, createdTime, modifiedTime
        """
        # Use Drive API under the hood via gspread
        all_sheets = self.client.list_spreadsheet_files()

        # Apply query filter if provided
        if query:
            query_lower = query.lower()
            all_sheets = [
                s for s in all_sheets
                if query_lower in s.get("name", "").lower()
            ]

        # Limit results
        sheets = all_sheets[:max_results]

        return [
            {
                "id": s.get("id"),
                "name": s.get("name"),
                "createdTime": s.get("createdTime"),
                "modifiedTime": s.get("modifiedTime"),
            }
            for s in sheets
        ]

    def get_spreadsheet(self, sheet_id: str) -> Spreadsheet:
        """Get spreadsheet by ID or URL.

        Args:
            sheet_id: Spreadsheet ID or full Google Sheets URL

        Returns:
            gspread.Spreadsheet object
        """
        sheet_id = self._extract_id(sheet_id)
        return self.client.open_by_key(sheet_id)

    def get_spreadsheet_metadata(self, sheet_id: str) -> Dict[str, Any]:
        """Get spreadsheet metadata including sheet list.

        Args:
            sheet_id: Spreadsheet ID or URL

        Returns:
            Dict with id, title, locale, timeZone, sheets list
        """
        spreadsheet = self.get_spreadsheet(sheet_id)

        return {
            "id": spreadsheet.id,
            "title": spreadsheet.title,
            "locale": spreadsheet.locale,
            "timeZone": spreadsheet.timezone,
            "url": spreadsheet.url,
            "sheets": [
                {
                    "id": ws.id,
                    "title": ws.title,
                    "index": ws.index,
                    "rowCount": ws.row_count,
                    "colCount": ws.col_count,
                }
                for ws in spreadsheet.worksheets()
            ],
        }

    def create_spreadsheet(
        self,
        title: str,
        folder_id: Optional[str] = None,
    ) -> Spreadsheet:
        """Create a new spreadsheet.

        Args:
            title: Title for the new spreadsheet
            folder_id: Optional Drive folder ID to create in

        Returns:
            gspread.Spreadsheet: The newly created spreadsheet
        """
        spreadsheet = self.client.create(title)

        if folder_id:
            self.client.move(spreadsheet.id, folder_id)

        return spreadsheet

    # =========================================================================
    # READ OPERATIONS
    # =========================================================================

    def read_range(
        self,
        sheet_id: str,
        range: str = "Sheet1!A:Z",
        value_render_option: str = "FORMATTED_VALUE",
    ) -> List[List[Any]]:
        """Read data from a range.

        Args:
            sheet_id: Spreadsheet ID or URL
            range: A1 notation range (e.g., "Sheet1!A1:D10")
            value_render_option: How to render values:
                - FORMATTED_VALUE: As displayed in UI
                - UNFORMATTED_VALUE: Raw values
                - FORMULA: Show formulas

        Returns:
            List of lists representing rows and cells
        """
        spreadsheet = self.get_spreadsheet(sheet_id)
        worksheet = self._get_worksheet_from_range(spreadsheet, range)
        cell_range = self._extract_cell_range(range)

        return worksheet.get(
            cell_range,
            value_render_option=value_render_option
        )

    def read_all(
        self,
        sheet_id: str,
        sheet_name: str = "Sheet1",
    ) -> List[List[Any]]:
        """Read all data from a worksheet.

        Args:
            sheet_id: Spreadsheet ID or URL
            sheet_name: Name of the worksheet

        Returns:
            List of lists representing all data
        """
        spreadsheet = self.get_spreadsheet(sheet_id)
        worksheet = spreadsheet.worksheet(sheet_name)
        return worksheet.get_all_values()

    def read_as_records(
        self,
        sheet_id: str,
        sheet_name: str = "Sheet1",
        head: int = 1,
    ) -> List[Dict[str, Any]]:
        """Read worksheet as list of dicts (header row as keys).

        Args:
            sheet_id: Spreadsheet ID or URL
            sheet_name: Name of the worksheet
            head: Row number of header (1-indexed)

        Returns:
            List of dicts where keys are header values
        """
        spreadsheet = self.get_spreadsheet(sheet_id)
        worksheet = spreadsheet.worksheet(sheet_name)
        return worksheet.get_all_records(head=head)

    def read_as_dataframe(
        self,
        sheet_id: str,
        sheet_name: str = "Sheet1",
        evaluate_formulas: bool = True,
        **kwargs,
    ) -> "pd.DataFrame":
        """Read worksheet as pandas DataFrame.

        Requires pandas and gspread-dataframe to be installed.
        Install with: pip install gwark[sheets]

        Args:
            sheet_id: Spreadsheet ID or URL
            sheet_name: Name of the worksheet
            evaluate_formulas: Whether to evaluate formulas
            **kwargs: Additional arguments for get_as_dataframe

        Returns:
            pandas.DataFrame

        Raises:
            ImportError: If pandas/gspread-dataframe not installed
        """
        if not HAS_PANDAS:
            raise ImportError(
                "pandas and gspread-dataframe required for DataFrame support.\n"
                "Install with: pip install gwark[sheets]"
            )

        spreadsheet = self.get_spreadsheet(sheet_id)
        worksheet = spreadsheet.worksheet(sheet_name)

        return get_as_dataframe(
            worksheet,
            evaluate_formulas=evaluate_formulas,
            **kwargs
        )

    # =========================================================================
    # WRITE OPERATIONS
    # =========================================================================

    def write_range(
        self,
        sheet_id: str,
        data: List[List[Any]],
        range: str = "Sheet1!A1",
        value_input_option: str = "USER_ENTERED",
    ) -> Dict[str, Any]:
        """Write data to a range.

        Args:
            sheet_id: Spreadsheet ID or URL
            data: List of lists to write
            range: A1 notation for starting cell (e.g., "Sheet1!A1")
            value_input_option: How to interpret input:
                - USER_ENTERED: Parse as if typed by user (formulas work)
                - RAW: Store exactly as provided

        Returns:
            API response dict
        """
        spreadsheet = self.get_spreadsheet(sheet_id)
        worksheet = self._get_worksheet_from_range(spreadsheet, range)
        cell_range = self._extract_cell_range(range) or "A1"

        return worksheet.update(
            cell_range,
            data,
            value_input_option=value_input_option
        )

    def write_dataframe(
        self,
        sheet_id: str,
        df: "pd.DataFrame",
        sheet_name: str = "Sheet1",
        include_index: bool = False,
        include_column_header: bool = True,
        resize: bool = True,
        **kwargs,
    ) -> None:
        """Write pandas DataFrame to worksheet.

        Requires pandas and gspread-dataframe to be installed.

        Args:
            sheet_id: Spreadsheet ID or URL
            df: pandas DataFrame to write
            sheet_name: Name of the worksheet
            include_index: Include DataFrame index as column
            include_column_header: Include header row
            resize: Resize worksheet to fit DataFrame
            **kwargs: Additional arguments for set_with_dataframe
        """
        if not HAS_PANDAS:
            raise ImportError(
                "pandas and gspread-dataframe required for DataFrame support.\n"
                "Install with: pip install gwark[sheets]"
            )

        spreadsheet = self.get_spreadsheet(sheet_id)
        worksheet = spreadsheet.worksheet(sheet_name)

        set_with_dataframe(
            worksheet,
            df,
            include_index=include_index,
            include_column_header=include_column_header,
            resize=resize,
            **kwargs
        )

    def append_rows(
        self,
        sheet_id: str,
        rows: List[List[Any]],
        sheet_name: str = "Sheet1",
        value_input_option: str = "USER_ENTERED",
        insert_data_option: str = "INSERT_ROWS",
        table_range: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Append rows to a worksheet.

        Args:
            sheet_id: Spreadsheet ID or URL
            rows: List of rows to append
            sheet_name: Name of the worksheet
            value_input_option: USER_ENTERED or RAW
            insert_data_option: INSERT_ROWS or OVERWRITE
            table_range: Optional range to detect table boundaries

        Returns:
            API response dict
        """
        spreadsheet = self.get_spreadsheet(sheet_id)
        worksheet = spreadsheet.worksheet(sheet_name)

        return worksheet.append_rows(
            rows,
            value_input_option=value_input_option,
            insert_data_option=insert_data_option,
            table_range=table_range,
        )

    def clear_range(
        self,
        sheet_id: str,
        range: str,
    ) -> None:
        """Clear cells in a range.

        Args:
            sheet_id: Spreadsheet ID or URL
            range: A1 notation range to clear (e.g., "Sheet1!A1:D10")
        """
        spreadsheet = self.get_spreadsheet(sheet_id)
        worksheet = self._get_worksheet_from_range(spreadsheet, range)
        cell_range = self._extract_cell_range(range)

        worksheet.batch_clear([cell_range])

    # =========================================================================
    # BATCH OPERATIONS
    # =========================================================================

    def batch_get(
        self,
        sheet_id: str,
        ranges: List[str],
    ) -> Dict[str, List[List[Any]]]:
        """Get multiple ranges in a single API call.

        Args:
            sheet_id: Spreadsheet ID or URL
            ranges: List of A1 notation ranges

        Returns:
            Dict mapping range to data
        """
        spreadsheet = self.get_spreadsheet(sheet_id)
        result = spreadsheet.values_batch_get(ranges)

        # Parse response into dict
        value_ranges = result.get("valueRanges", [])
        return {
            vr.get("range"): vr.get("values", [])
            for vr in value_ranges
        }

    def batch_update(
        self,
        sheet_id: str,
        updates: List[Dict[str, Any]],
        value_input_option: str = "USER_ENTERED",
    ) -> Dict[str, Any]:
        """Update multiple ranges in a single API call.

        Args:
            sheet_id: Spreadsheet ID or URL
            updates: List of {"range": "A1:B2", "values": [[...]]}
            value_input_option: USER_ENTERED or RAW

        Returns:
            API response dict
        """
        spreadsheet = self.get_spreadsheet(sheet_id)

        return spreadsheet.values_batch_update(
            body={
                "valueInputOption": value_input_option,
                "data": updates,
            }
        )

    async def batch_read_async(
        self,
        sheet_id: str,
        ranges: List[str],
        max_concurrent: int = 5,
    ) -> Dict[str, List[List[Any]]]:
        """Read multiple ranges in parallel (async).

        Faster than batch_get for large range lists as it parallelizes
        the reads across multiple threads.

        Args:
            sheet_id: Spreadsheet ID or URL
            ranges: List of A1 notation ranges
            max_concurrent: Maximum concurrent reads

        Returns:
            Dict mapping range to data
        """
        fetcher = AsyncFetcher(max_concurrent=max_concurrent, rate_per_second=50)

        def read_single_range(range_str: str) -> Tuple[str, List[List[Any]]]:
            data = self.read_range(sheet_id, range_str)
            return (range_str, data)

        results = await fetcher.fetch_all(ranges, read_single_range)

        # Convert to dict, filtering errors
        output = {}
        for result in results:
            if isinstance(result, Exception):
                continue
            range_str, data = result
            output[range_str] = data

        return output

    def batch_read_parallel(
        self,
        sheet_id: str,
        ranges: List[str],
        max_concurrent: int = 5,
    ) -> Dict[str, List[List[Any]]]:
        """Read multiple ranges in parallel (sync wrapper).

        Args:
            sheet_id: Spreadsheet ID or URL
            ranges: List of A1 notation ranges
            max_concurrent: Maximum concurrent reads

        Returns:
            Dict mapping range to data
        """
        return run_async(self.batch_read_async(sheet_id, ranges, max_concurrent))

    # =========================================================================
    # PIVOT TABLE OPERATIONS
    # =========================================================================

    def create_pivot_table(
        self,
        sheet_id: str,
        source_range: str,
        target_cell: str,
        rows: List[str],
        columns: Optional[List[str]] = None,
        values: Optional[List[Dict[str, str]]] = None,
        apply_style: bool = True,
        column_widths: Optional[List[int]] = None,
        row_sort_orders: Optional[Dict[str, str]] = None,
        col_sort_orders: Optional[Dict[str, str]] = None,
        sort_by_value: Optional[int] = None,
        filters: Optional[Dict[str, List[str]]] = None,
        value_display: Optional[str] = None,
        value_layout: Optional[str] = None,
        show_totals: bool = True,
        date_groups: Optional[Dict[str, str]] = None,
        group_limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Create a pivot table using Sheets API batchUpdate.

        Args:
            sheet_id: Spreadsheet ID or URL
            source_range: Source data range (e.g., "Sheet1!A1:D100")
            target_cell: Target cell for pivot (e.g., "Sheet2!A1")
            rows: Column names to use as row groupings
            columns: Column names to use as column groupings (optional)
            values: List of value aggregations, each dict with:
                - "field": Column name
                - "function": Aggregation function (SUM, COUNT, AVERAGE, MAX, MIN,
                              COUNTUNIQUE, MEDIAN, STDEV)
            apply_style: Apply default pivot styling (default: True)
            column_widths: Optional column widths in pixels
            row_sort_orders: Per-field sort direction for rows (e.g., {"Category": "DESCENDING"})
            col_sort_orders: Per-field sort direction for columns
            sort_by_value: Index into values list to sort rows by (valueBucket)
            filters: Source data filters (e.g., {"Region": ["East", "West"]})
            value_display: Calculated display type (PERCENT_OF_ROW_TOTAL, etc.)
            value_layout: Multiple values layout (HORIZONTAL or VERTICAL)
            show_totals: Show subtotals on rows/columns (default: True)
            date_groups: Date grouping rules (e.g., {"Date": "YEAR_MONTH"})
            group_limit: Max rows/columns shown in pivot groups
        """
        spreadsheet = self.get_spreadsheet(sheet_id)

        # Parse source range to get sheet ID and grid coordinates
        source_sheet_id, source_grid = self._parse_range_to_grid(
            spreadsheet, source_range
        )
        target_sheet_id, target_grid = self._parse_range_to_grid(
            spreadsheet, target_cell
        )

        # Get source headers to map column names to offsets
        source_sheet_name = source_range.split("!")[0].strip("'")
        source_worksheet = spreadsheet.worksheet(source_sheet_name)
        headers = source_worksheet.row_values(source_grid["startRowIndex"] + 1)
        header_map = {name: idx for idx, name in enumerate(headers)}

        # Build row groups
        pivot_rows = []
        for i, r in enumerate(rows):
            sort_order = (row_sort_orders or {}).get(r, "ASCENDING")
            group: Dict[str, Any] = {
                "sourceColumnOffset": header_map.get(r, 0),
                "showTotals": show_totals,
                "sortOrder": sort_order,
            }
            if sort_by_value is not None and i == 0:
                group["valueBucket"] = {"valuesIndex": sort_by_value}
            if date_groups and r in date_groups:
                group["groupRule"] = {"dateTimeRule": {"type": date_groups[r]}}
            if group_limit is not None:
                group["groupLimit"] = {"countLimit": group_limit}
            pivot_rows.append(group)

        # Build pivot table spec
        pivot_spec: Dict[str, Any] = {
            "source": {
                "sheetId": source_sheet_id,
                "startRowIndex": source_grid["startRowIndex"],
                "endRowIndex": source_grid["endRowIndex"],
                "startColumnIndex": source_grid["startColumnIndex"],
                "endColumnIndex": source_grid["endColumnIndex"],
            },
            "rows": pivot_rows,
        }

        # Column groups
        if columns:
            pivot_cols = []
            for c in columns:
                sort_order = (col_sort_orders or {}).get(c, "ASCENDING")
                col_group: Dict[str, Any] = {
                    "sourceColumnOffset": header_map.get(c, 0),
                    "showTotals": show_totals,
                    "sortOrder": sort_order,
                }
                if date_groups and c in date_groups:
                    col_group["groupRule"] = {"dateTimeRule": {"type": date_groups[c]}}
                pivot_cols.append(col_group)
            pivot_spec["columns"] = pivot_cols

        # Value aggregations
        if values:
            pivot_values = []
            for v in values:
                val_spec: Dict[str, Any] = {
                    "sourceColumnOffset": header_map.get(v["field"], 0),
                    "summarizeFunction": v.get("function", "SUM").upper(),
                }
                if value_display:
                    val_spec["calculatedDisplayType"] = value_display
                pivot_values.append(val_spec)
            pivot_spec["values"] = pivot_values

        # Value layout (horizontal/vertical for multiple values)
        if value_layout:
            pivot_spec["valueLayout"] = value_layout

        # Filter specs
        if filters:
            filter_specs = []
            for field_name, visible_vals in filters.items():
                offset = header_map.get(field_name, 0)
                filter_specs.append({
                    "filterCriteria": {"visibleValues": visible_vals},
                    "columnOffsetIndex": offset,
                })
            pivot_spec["filterSpecs"] = filter_specs

        # Construct batchUpdate request
        request = {
            "updateCells": {
                "rows": [
                    {
                        "values": [
                            {
                                "pivotTable": pivot_spec
                            }
                        ]
                    }
                ],
                "start": {
                    "sheetId": target_sheet_id,
                    "rowIndex": target_grid["startRowIndex"],
                    "columnIndex": target_grid["startColumnIndex"],
                },
                "fields": "pivotTable",
            }
        }

        result = spreadsheet.batch_update({"requests": [request]})

        # Apply default styling
        if apply_style:
            # Extract target sheet name
            if "!" in target_cell:
                target_sheet_name = target_cell.split("!")[0].strip("'")
            else:
                target_sheet_name = "Sheet1"

            # Calculate number of columns (rows + columns + values)
            num_cols = len(rows) + (len(columns) if columns else 0) + (len(values) if values else 1)

            self.format_pivot_table(
                sheet_id=sheet_id,
                sheet_name=target_sheet_name,
                num_columns=num_cols,
                column_widths=column_widths,
            )

        return result

    def set_column_widths(
        self,
        sheet_id: str,
        sheet_name: str,
        widths: List[int],
        start_column: int = 0,
    ) -> Dict[str, Any]:
        """Set column widths for a worksheet.

        Args:
            sheet_id: Spreadsheet ID or URL
            sheet_name: Name of the worksheet
            widths: List of pixel widths for each column
            start_column: Starting column index (0-based, default: 0)

        Returns:
            API response dict

        Example:
            >>> client.set_column_widths(
            ...     sheet_id="1abc...",
            ...     sheet_name="Pivot",
            ...     widths=[120, 150, 140, 200, 90]  # 700px total
            ... )
        """
        spreadsheet = self.get_spreadsheet(sheet_id)
        worksheet = spreadsheet.worksheet(sheet_name)
        ws_id = worksheet.id

        requests = []
        for i, width in enumerate(widths):
            col_index = start_column + i
            requests.append({
                "updateDimensionProperties": {
                    "range": {
                        "sheetId": ws_id,
                        "dimension": "COLUMNS",
                        "startIndex": col_index,
                        "endIndex": col_index + 1,
                    },
                    "properties": {
                        "pixelSize": width,
                    },
                    "fields": "pixelSize",
                }
            })

        return spreadsheet.batch_update({"requests": requests})

    def format_pivot_table(
        self,
        sheet_id: str,
        sheet_name: str,
        num_columns: int = 5,
        column_widths: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        """Apply default pivot table styling.

        Applies a clean, professional style:
        - Roboto font, 10pt, dark grey text (#424242)
        - Light blue header (#e3f2fd), bold
        - White data rows
        - Light gray subtotal rows (#f5f5f5), bold
        - Darker gray Grand Total (#e0e0e0), bold

        Args:
            sheet_id: Spreadsheet ID or URL
            sheet_name: Name of the worksheet with pivot table
            num_columns: Number of columns to format (default: 5)
            column_widths: Optional list of column widths in pixels

        Returns:
            API response dict

        Example:
            >>> client.format_pivot_table(
            ...     sheet_id="1abc...",
            ...     sheet_name="Pivot",
            ...     column_widths=[130, 160, 150, 420, 100]
            ... )
        """
        spreadsheet = self.get_spreadsheet(sheet_id)
        worksheet = spreadsheet.worksheet(sheet_name)
        ws_id = worksheet.id

        # Colors
        dark_grey = {'red': 0.26, 'green': 0.26, 'blue': 0.26}  # #424242
        light_blue = {'red': 0.89, 'green': 0.95, 'blue': 0.99}  # #e3f2fd
        white = {'red': 1, 'green': 1, 'blue': 1}
        light_gray = {'red': 0.96, 'green': 0.96, 'blue': 0.96}  # #f5f5f5
        medium_gray = {'red': 0.88, 'green': 0.88, 'blue': 0.88}  # #e0e0e0

        # Read data to find total rows
        data = self.read_range(sheet_id, f"'{sheet_name}'!A1:Z100")
        total_rows = []
        grand_total_row = None
        for i, row in enumerate(data):
            row_text = ' '.join(str(cell) for cell in row)
            if 'Grand Total' in row_text:
                grand_total_row = i
            elif 'Total' in row_text:
                total_rows.append(i)

        last_row = len(data)

        requests = [
            # Header row - light blue, bold
            {
                'repeatCell': {
                    'range': {
                        'sheetId': ws_id,
                        'startRowIndex': 0,
                        'endRowIndex': 1,
                        'startColumnIndex': 0,
                        'endColumnIndex': num_columns,
                    },
                    'cell': {
                        'userEnteredFormat': {
                            'backgroundColor': light_blue,
                            'textFormat': {
                                'foregroundColor': dark_grey,
                                'fontFamily': 'Roboto',
                                'fontSize': 10,
                                'bold': True,
                            },
                        }
                    },
                    'fields': 'userEnteredFormat(backgroundColor,textFormat)',
                }
            },
            # Data rows - white background, dark grey text
            {
                'repeatCell': {
                    'range': {
                        'sheetId': ws_id,
                        'startRowIndex': 1,
                        'endRowIndex': last_row,
                        'startColumnIndex': 0,
                        'endColumnIndex': num_columns,
                    },
                    'cell': {
                        'userEnteredFormat': {
                            'backgroundColor': white,
                            'textFormat': {
                                'foregroundColor': dark_grey,
                                'fontFamily': 'Roboto',
                                'fontSize': 10,
                            },
                        }
                    },
                    'fields': 'userEnteredFormat(backgroundColor,textFormat)',
                }
            },
        ]

        # Subtotal rows - light gray, bold
        for row_idx in total_rows:
            requests.append({
                'repeatCell': {
                    'range': {
                        'sheetId': ws_id,
                        'startRowIndex': row_idx,
                        'endRowIndex': row_idx + 1,
                        'startColumnIndex': 0,
                        'endColumnIndex': num_columns,
                    },
                    'cell': {
                        'userEnteredFormat': {
                            'backgroundColor': light_gray,
                            'textFormat': {
                                'foregroundColor': dark_grey,
                                'fontFamily': 'Roboto',
                                'fontSize': 10,
                                'bold': True,
                            },
                        }
                    },
                    'fields': 'userEnteredFormat(backgroundColor,textFormat)',
                }
            })

        # Grand Total row - medium gray, bold
        if grand_total_row is not None:
            requests.append({
                'repeatCell': {
                    'range': {
                        'sheetId': ws_id,
                        'startRowIndex': grand_total_row,
                        'endRowIndex': grand_total_row + 1,
                        'startColumnIndex': 0,
                        'endColumnIndex': num_columns,
                    },
                    'cell': {
                        'userEnteredFormat': {
                            'backgroundColor': medium_gray,
                            'textFormat': {
                                'foregroundColor': dark_grey,
                                'fontFamily': 'Roboto',
                                'fontSize': 10,
                                'bold': True,
                            },
                        }
                    },
                    'fields': 'userEnteredFormat(backgroundColor,textFormat)',
                }
            })

        result = spreadsheet.batch_update({'requests': requests})

        # Apply column widths if provided
        if column_widths:
            self.set_column_widths(sheet_id, sheet_name, column_widths)

        return result

    def auto_resize_columns(
        self,
        sheet_id: str,
        sheet_name: str,
        start_column: int = 0,
        end_column: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Auto-resize columns to fit content.

        Args:
            sheet_id: Spreadsheet ID or URL
            sheet_name: Name of the worksheet
            start_column: Starting column index (0-based)
            end_column: Ending column index (exclusive), None for all

        Returns:
            API response dict
        """
        spreadsheet = self.get_spreadsheet(sheet_id)
        worksheet = spreadsheet.worksheet(sheet_name)
        ws_id = worksheet.id

        if end_column is None:
            end_column = worksheet.col_count

        request = {
            "autoResizeDimensions": {
                "dimensions": {
                    "sheetId": ws_id,
                    "dimension": "COLUMNS",
                    "startIndex": start_column,
                    "endIndex": end_column,
                }
            }
        }

        return spreadsheet.batch_update({"requests": [request]})

    def _parse_range_to_grid(
        self,
        spreadsheet: Spreadsheet,
        range_str: str,
    ) -> Tuple[int, Dict[str, int]]:
        """Parse A1 notation to sheet ID and grid coordinates.

        Args:
            spreadsheet: gspread.Spreadsheet object
            range_str: A1 notation like "Sheet1!A1:D100"

        Returns:
            Tuple of (sheet_id, grid_dict) where grid_dict has:
            - startRowIndex
            - endRowIndex
            - startColumnIndex
            - endColumnIndex
        """
        # Split sheet name and cell range
        if "!" in range_str:
            sheet_name, cell_range = range_str.split("!", 1)
            sheet_name = sheet_name.strip("'")
        else:
            sheet_name = "Sheet1"
            cell_range = range_str

        worksheet = spreadsheet.worksheet(sheet_name)
        sheet_id = worksheet.id

        # Parse cell range (e.g., "A1:D100" or "A1")
        grid = self._parse_cell_range(cell_range, worksheet.row_count, worksheet.col_count)

        return sheet_id, grid

    def _parse_cell_range(
        self,
        cell_range: str,
        max_rows: int = 1000,
        max_cols: int = 26,
    ) -> Dict[str, int]:
        """Parse cell range to grid coordinates.

        Args:
            cell_range: Range like "A1:D100" or "A1" or "A:D"
            max_rows: Maximum row count for open-ended ranges
            max_cols: Maximum column count for open-ended ranges

        Returns:
            Dict with startRowIndex, endRowIndex, startColumnIndex, endColumnIndex
        """
        # Pattern for A1 notation
        pattern = r"^([A-Z]+)(\d*):?([A-Z]*)(\d*)$"
        match = re.match(pattern, cell_range.upper())

        if not match:
            # Default to A1
            return {
                "startRowIndex": 0,
                "endRowIndex": max_rows,
                "startColumnIndex": 0,
                "endColumnIndex": max_cols,
            }

        start_col_letter, start_row, end_col_letter, end_row = match.groups()

        # Convert column letters to indices
        start_col_idx = self._col_to_index(start_col_letter)
        end_col_idx = self._col_to_index(end_col_letter) if end_col_letter else start_col_idx

        # Convert row numbers to indices (0-based)
        start_row_idx = int(start_row) - 1 if start_row else 0
        end_row_idx = int(end_row) if end_row else max_rows

        return {
            "startRowIndex": start_row_idx,
            "endRowIndex": end_row_idx,
            "startColumnIndex": start_col_idx,
            "endColumnIndex": end_col_idx + 1,  # API uses exclusive end
        }

    @staticmethod
    def _col_to_index(col_letter: str) -> int:
        """Convert column letter(s) to 0-based index.

        Args:
            col_letter: Column letter(s) like "A", "Z", "AA"

        Returns:
            0-based column index
        """
        result = 0
        for char in col_letter:
            result = result * 26 + (ord(char.upper()) - ord('A') + 1)
        return result - 1

    # =========================================================================
    # EXPORT OPERATIONS
    # =========================================================================

    def export_csv(
        self,
        sheet_id: str,
        sheet_name: str = "Sheet1",
    ) -> str:
        """Export worksheet as CSV string.

        Args:
            sheet_id: Spreadsheet ID or URL
            sheet_name: Name of the worksheet to export

        Returns:
            CSV string
        """
        spreadsheet = self.get_spreadsheet(sheet_id)
        worksheet = spreadsheet.worksheet(sheet_name)

        # Get all values and convert to CSV
        data = worksheet.get_all_values()

        import csv
        import io

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerows(data)

        return output.getvalue()

    def export_json(
        self,
        sheet_id: str,
        sheet_name: str = "Sheet1",
        as_records: bool = True,
    ) -> Union[List[Dict], List[List]]:
        """Export worksheet as JSON-serializable data.

        Args:
            sheet_id: Spreadsheet ID or URL
            sheet_name: Name of the worksheet
            as_records: If True, return list of dicts (header as keys)
                       If False, return list of lists

        Returns:
            JSON-serializable data structure
        """
        if as_records:
            return self.read_as_records(sheet_id, sheet_name)
        else:
            return self.read_all(sheet_id, sheet_name)

    # =========================================================================
    # WORKSHEET OPERATIONS
    # =========================================================================

    def list_worksheets(self, sheet_id: str) -> List[Dict[str, Any]]:
        """List all worksheets in a spreadsheet.

        Args:
            sheet_id: Spreadsheet ID or URL

        Returns:
            List of worksheet info dicts
        """
        spreadsheet = self.get_spreadsheet(sheet_id)

        return [
            {
                "id": ws.id,
                "title": ws.title,
                "index": ws.index,
                "rowCount": ws.row_count,
                "colCount": ws.col_count,
            }
            for ws in spreadsheet.worksheets()
        ]

    def add_worksheet(
        self,
        sheet_id: str,
        title: str,
        rows: int = 1000,
        cols: int = 26,
    ) -> Worksheet:
        """Add a new worksheet to a spreadsheet.

        Args:
            sheet_id: Spreadsheet ID or URL
            title: Title for the new worksheet
            rows: Number of rows
            cols: Number of columns

        Returns:
            The newly created worksheet
        """
        spreadsheet = self.get_spreadsheet(sheet_id)
        return spreadsheet.add_worksheet(title=title, rows=rows, cols=cols)

    def delete_worksheet(
        self,
        sheet_id: str,
        sheet_name: str,
    ) -> None:
        """Delete a worksheet from a spreadsheet.

        Args:
            sheet_id: Spreadsheet ID or URL
            sheet_name: Name of the worksheet to delete
        """
        spreadsheet = self.get_spreadsheet(sheet_id)
        worksheet = spreadsheet.worksheet(sheet_name)
        spreadsheet.del_worksheet(worksheet)

    # =========================================================================
    # HELPERS
    # =========================================================================

    @staticmethod
    def _extract_id(sheet_id_or_url: str) -> str:
        """Extract spreadsheet ID from URL or return as-is.

        Args:
            sheet_id_or_url: Either a spreadsheet ID or full Google Sheets URL

        Returns:
            The spreadsheet ID

        Examples:
            >>> SheetsClient._extract_id("1abc123")
            '1abc123'
            >>> SheetsClient._extract_id("https://docs.google.com/spreadsheets/d/1abc123/edit")
            '1abc123'
        """
        # Match Google Sheets URL pattern
        match = re.search(r'/spreadsheets/d/([a-zA-Z0-9_-]+)', sheet_id_or_url)
        return match.group(1) if match else sheet_id_or_url

    @staticmethod
    def _get_worksheet_from_range(
        spreadsheet: Spreadsheet,
        range: str,
    ) -> Worksheet:
        """Extract worksheet from range notation.

        Args:
            spreadsheet: gspread.Spreadsheet object
            range: A1 notation like "Sheet1!A1:B10"

        Returns:
            The worksheet object
        """
        if "!" in range:
            sheet_name = range.split("!")[0]
            # Handle quoted sheet names like "'Sheet Name'!A1:B10"
            sheet_name = sheet_name.strip("'")
            return spreadsheet.worksheet(sheet_name)
        return spreadsheet.sheet1

    @staticmethod
    def _extract_cell_range(range: str) -> str:
        """Extract cell range from A1 notation.

        Args:
            range: A1 notation like "Sheet1!A1:B10"

        Returns:
            Just the cell range (e.g., "A1:B10")
        """
        if "!" in range:
            return range.split("!")[1]
        return range

    @staticmethod
    def _col_letter(index: int) -> str:
        """Convert column index to letter (0 -> A, 25 -> Z, 26 -> AA).

        Args:
            index: 0-based column index

        Returns:
            Column letter(s)
        """
        result = ""
        while index >= 0:
            result = chr(index % 26 + ord('A')) + result
            index = index // 26 - 1
        return result
