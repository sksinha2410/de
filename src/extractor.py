"""Bill data extraction module.

This module provides functionality to extract line items,
sub-totals, and final totals from bill data.
"""

import json
import re
from decimal import Decimal, InvalidOperation
from typing import Any

from .models import Bill, LineItem, SubTotal


class BillExtractor:
    """Extracts structured data from bills/invoices.
    
    This class provides methods to parse bill data from various
    formats and extract line items, sub-totals, and totals.
    """
    
    def extract_from_dict(self, data: dict[str, Any]) -> Bill:
        """Extract bill data from a dictionary representation.
        
        Args:
            data: Dictionary containing bill data with keys:
                - bill_id: Unique bill identifier
                - vendor_name: Name of vendor
                - date: Bill date
                - line_items: List of line item dicts
                - sub_totals: Optional list of sub-total dicts
                - final_total: Optional stated final total
                - currency: Optional currency code
                - page_count: Optional number of pages
        
        Returns:
            A Bill object with extracted data.
        
        Raises:
            ValueError: If required fields are missing or invalid.
        """
        if not data.get('bill_id'):
            raise ValueError("bill_id is required")
        if not data.get('vendor_name'):
            raise ValueError("vendor_name is required")
        if not data.get('date'):
            raise ValueError("date is required")
        
        line_items = self._extract_line_items(data.get('line_items', []))
        sub_totals = self._extract_sub_totals(data.get('sub_totals', []))
        
        final_total = None
        if 'final_total' in data and data['final_total'] is not None:
            final_total = self._parse_amount(data['final_total'])
        
        return Bill(
            bill_id=data['bill_id'],
            vendor_name=data['vendor_name'],
            date=data['date'],
            line_items=line_items,
            sub_totals=sub_totals,
            final_total=final_total,
            currency=data.get('currency', 'USD'),
            page_count=data.get('page_count', 1)
        )
    
    def extract_from_json(self, json_str: str) -> Bill:
        """Extract bill data from a JSON string.
        
        Args:
            json_str: JSON string containing bill data.
        
        Returns:
            A Bill object with extracted data.
        
        Raises:
            ValueError: If JSON is invalid or data is missing.
        """
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}") from e
        
        return self.extract_from_dict(data)
    
    def extract_from_json_file(self, file_path: str) -> Bill:
        """Extract bill data from a JSON file.
        
        Args:
            file_path: Path to the JSON file.
        
        Returns:
            A Bill object with extracted data.
        
        Raises:
            ValueError: If file cannot be read or contains invalid data.
            FileNotFoundError: If file does not exist.
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            return self.extract_from_json(f.read())
    
    def _extract_line_items(self, items_data: list[dict]) -> list[LineItem]:
        """Extract line items from a list of dictionaries.
        
        Args:
            items_data: List of dictionaries with line item data.
        
        Returns:
            List of LineItem objects.
        """
        line_items = []
        for item in items_data:
            description = item.get('description', '')
            quantity = self._parse_amount(item.get('quantity', 1))
            unit_price = self._parse_amount(item.get('unit_price', 0))
            
            # Use provided amount or calculate from quantity * unit_price
            if 'amount' in item:
                amount = self._parse_amount(item['amount'])
            else:
                amount = quantity * unit_price
            
            line_items.append(LineItem(
                description=description,
                quantity=quantity,
                unit_price=unit_price,
                amount=amount,
                category=item.get('category')
            ))
        
        return line_items
    
    def _extract_sub_totals(self, sub_totals_data: list[dict]) -> list[SubTotal]:
        """Extract sub-totals from a list of dictionaries.
        
        Args:
            sub_totals_data: List of dictionaries with sub-total data.
        
        Returns:
            List of SubTotal objects.
        """
        sub_totals = []
        for st in sub_totals_data:
            label = st.get('label', 'Sub-total')
            amount = self._parse_amount(st.get('amount', 0))
            line_item_refs = st.get('line_item_refs', [])
            
            sub_totals.append(SubTotal(
                label=label,
                amount=amount,
                line_item_refs=line_item_refs
            ))
        
        return sub_totals
    
    @staticmethod
    def _parse_amount(value: Any) -> Decimal:
        """Parse a value into a Decimal amount.
        
        Handles strings with currency symbols, commas, etc.
        
        Args:
            value: The value to parse (string, int, float, or Decimal).
        
        Returns:
            Decimal representation of the value.
        
        Raises:
            ValueError: If value cannot be parsed.
        """
        if isinstance(value, Decimal):
            return value
        
        if isinstance(value, (int, float)):
            return Decimal(str(value))
        
        if isinstance(value, str):
            # Remove currency symbols, commas, and whitespace
            cleaned = re.sub(r'[^\d.-]', '', value)
            if not cleaned:
                return Decimal('0')
            try:
                return Decimal(cleaned)
            except InvalidOperation:
                raise ValueError(f"Cannot parse amount: {value}")
        
        raise ValueError(f"Unsupported type for amount: {type(value)}")
