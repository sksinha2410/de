"""Tests for bill data extraction."""

import json
import os
import tempfile
from decimal import Decimal

import pytest

from src.extractor import BillExtractor
from src.models import Bill


class TestBillExtractor:
    """Tests for BillExtractor class."""
    
    @pytest.fixture
    def extractor(self):
        """Create a BillExtractor instance."""
        return BillExtractor()
    
    @pytest.fixture
    def sample_bill_data(self):
        """Sample bill data for testing."""
        return {
            'bill_id': 'INV-001',
            'vendor_name': 'Test Vendor',
            'date': '2024-01-15',
            'line_items': [
                {
                    'description': 'Widget A',
                    'quantity': 2,
                    'unit_price': 10.00,
                    'amount': 20.00
                },
                {
                    'description': 'Widget B',
                    'quantity': 3,
                    'unit_price': 15.00,
                    'amount': 45.00
                }
            ],
            'sub_totals': [
                {
                    'label': 'Products Total',
                    'amount': 65.00,
                    'line_item_refs': [0, 1]
                }
            ],
            'final_total': 65.00,
            'currency': 'USD',
            'page_count': 1
        }
    
    def test_extract_from_dict(self, extractor, sample_bill_data):
        """Test extracting bill from dictionary."""
        bill = extractor.extract_from_dict(sample_bill_data)
        
        assert bill.bill_id == 'INV-001'
        assert bill.vendor_name == 'Test Vendor'
        assert bill.date == '2024-01-15'
        assert len(bill.line_items) == 2
        assert len(bill.sub_totals) == 1
        assert bill.final_total == Decimal('65')
        assert bill.currency == 'USD'
        assert bill.page_count == 1
    
    def test_extract_line_items(self, extractor, sample_bill_data):
        """Test line items are correctly extracted."""
        bill = extractor.extract_from_dict(sample_bill_data)
        
        assert bill.line_items[0].description == 'Widget A'
        assert bill.line_items[0].quantity == Decimal('2')
        assert bill.line_items[0].unit_price == Decimal('10')
        assert bill.line_items[0].amount == Decimal('20')
        
        assert bill.line_items[1].description == 'Widget B'
        assert bill.line_items[1].quantity == Decimal('3')
        assert bill.line_items[1].unit_price == Decimal('15')
        assert bill.line_items[1].amount == Decimal('45')
    
    def test_extract_sub_totals(self, extractor, sample_bill_data):
        """Test sub-totals are correctly extracted."""
        bill = extractor.extract_from_dict(sample_bill_data)
        
        assert bill.sub_totals[0].label == 'Products Total'
        assert bill.sub_totals[0].amount == Decimal('65')
        assert bill.sub_totals[0].line_item_refs == [0, 1]
    
    def test_extract_from_json(self, extractor, sample_bill_data):
        """Test extracting bill from JSON string."""
        json_str = json.dumps(sample_bill_data)
        bill = extractor.extract_from_json(json_str)
        
        assert bill.bill_id == 'INV-001'
        assert len(bill.line_items) == 2
    
    def test_extract_from_json_file(self, extractor, sample_bill_data):
        """Test extracting bill from JSON file."""
        with tempfile.NamedTemporaryFile(
            mode='w', 
            suffix='.json', 
            delete=False
        ) as f:
            json.dump(sample_bill_data, f)
            temp_path = f.name
        
        try:
            bill = extractor.extract_from_json_file(temp_path)
            assert bill.bill_id == 'INV-001'
        finally:
            os.unlink(temp_path)
    
    def test_missing_bill_id_raises_error(self, extractor):
        """Test that missing bill_id raises ValueError."""
        data = {
            'vendor_name': 'Vendor',
            'date': '2024-01-15'
        }
        
        with pytest.raises(ValueError, match="bill_id is required"):
            extractor.extract_from_dict(data)
    
    def test_missing_vendor_name_raises_error(self, extractor):
        """Test that missing vendor_name raises ValueError."""
        data = {
            'bill_id': 'INV-001',
            'date': '2024-01-15'
        }
        
        with pytest.raises(ValueError, match="vendor_name is required"):
            extractor.extract_from_dict(data)
    
    def test_missing_date_raises_error(self, extractor):
        """Test that missing date raises ValueError."""
        data = {
            'bill_id': 'INV-001',
            'vendor_name': 'Vendor'
        }
        
        with pytest.raises(ValueError, match="date is required"):
            extractor.extract_from_dict(data)
    
    def test_invalid_json_raises_error(self, extractor):
        """Test that invalid JSON raises ValueError."""
        with pytest.raises(ValueError, match="Invalid JSON"):
            extractor.extract_from_json("not valid json")
    
    def test_parse_amount_with_currency_symbol(self, extractor):
        """Test parsing amounts with currency symbols."""
        assert extractor._parse_amount("$100.00") == Decimal('100.00')
        assert extractor._parse_amount("€50.00") == Decimal('50.00')
        assert extractor._parse_amount("£75.50") == Decimal('75.50')
    
    def test_parse_amount_with_commas(self, extractor):
        """Test parsing amounts with thousand separators."""
        assert extractor._parse_amount("1,000.00") == Decimal('1000.00')
        assert extractor._parse_amount("$1,234,567.89") == Decimal('1234567.89')
    
    def test_parse_amount_decimal(self, extractor):
        """Test parsing Decimal values."""
        assert extractor._parse_amount(Decimal('42.50')) == Decimal('42.50')
    
    def test_parse_amount_int_and_float(self, extractor):
        """Test parsing int and float values."""
        assert extractor._parse_amount(100) == Decimal('100')
        assert extractor._parse_amount(99.99) == Decimal('99.99')
    
    def test_calculated_amount_when_not_provided(self, extractor):
        """Test amount is calculated from quantity * unit_price."""
        data = {
            'bill_id': 'INV-001',
            'vendor_name': 'Vendor',
            'date': '2024-01-15',
            'line_items': [
                {
                    'description': 'Item',
                    'quantity': 5,
                    'unit_price': 20.00
                    # amount not provided
                }
            ]
        }
        
        bill = extractor.extract_from_dict(data)
        
        assert bill.line_items[0].amount == Decimal('100')
    
    def test_multi_page_bill(self, extractor):
        """Test extracting multi-page bill."""
        data = {
            'bill_id': 'INV-001',
            'vendor_name': 'Vendor',
            'date': '2024-01-15',
            'page_count': 3,
            'line_items': []
        }
        
        bill = extractor.extract_from_dict(data)
        
        assert bill.page_count == 3
