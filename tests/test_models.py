"""Tests for bill data models."""

from decimal import Decimal

import pytest

from src.models import Bill, LineItem, SubTotal


class TestLineItem:
    """Tests for LineItem model."""
    
    def test_create_line_item(self):
        """Test creating a basic line item."""
        item = LineItem(
            description="Widget A",
            quantity=Decimal('2'),
            unit_price=Decimal('10.00'),
            amount=Decimal('20.00')
        )
        
        assert item.description == "Widget A"
        assert item.quantity == Decimal('2')
        assert item.unit_price == Decimal('10.00')
        assert item.amount == Decimal('20.00')
        assert item.category is None
    
    def test_line_item_with_category(self):
        """Test line item with category."""
        item = LineItem(
            description="Consulting",
            quantity=Decimal('5'),
            unit_price=Decimal('100.00'),
            amount=Decimal('500.00'),
            category="Services"
        )
        
        assert item.category == "Services"
    
    def test_line_item_numeric_conversion(self):
        """Test that numeric values are converted to Decimal."""
        item = LineItem(
            description="Item",
            quantity=3,  # int
            unit_price=25.50,  # float
            amount="76.50"  # string
        )
        
        assert isinstance(item.quantity, Decimal)
        assert isinstance(item.unit_price, Decimal)
        assert isinstance(item.amount, Decimal)


class TestSubTotal:
    """Tests for SubTotal model."""
    
    def test_create_subtotal(self):
        """Test creating a sub-total."""
        subtotal = SubTotal(
            label="Products Total",
            amount=Decimal('150.00'),
            line_item_refs=[0, 1, 2]
        )
        
        assert subtotal.label == "Products Total"
        assert subtotal.amount == Decimal('150.00')
        assert subtotal.line_item_refs == [0, 1, 2]
    
    def test_subtotal_default_refs(self):
        """Test sub-total with default empty refs."""
        subtotal = SubTotal(
            label="Tax",
            amount=Decimal('12.00')
        )
        
        assert subtotal.line_item_refs == []


class TestBill:
    """Tests for Bill model."""
    
    def test_create_bill(self):
        """Test creating a basic bill."""
        bill = Bill(
            bill_id="INV-001",
            vendor_name="Test Vendor",
            date="2024-01-15"
        )
        
        assert bill.bill_id == "INV-001"
        assert bill.vendor_name == "Test Vendor"
        assert bill.date == "2024-01-15"
        assert bill.line_items == []
        assert bill.sub_totals == []
        assert bill.final_total is None
        assert bill.currency == "USD"
        assert bill.page_count == 1
    
    def test_bill_with_line_items(self):
        """Test bill with line items."""
        items = [
            LineItem("Item 1", Decimal('1'), Decimal('10'), Decimal('10')),
            LineItem("Item 2", Decimal('2'), Decimal('20'), Decimal('40')),
        ]
        
        bill = Bill(
            bill_id="INV-002",
            vendor_name="Vendor",
            date="2024-01-15",
            line_items=items
        )
        
        assert len(bill.line_items) == 2
    
    def test_calculate_line_items_total(self):
        """Test calculating total from line items."""
        items = [
            LineItem("Item 1", Decimal('1'), Decimal('10'), Decimal('10')),
            LineItem("Item 2", Decimal('2'), Decimal('20'), Decimal('40')),
            LineItem("Item 3", Decimal('3'), Decimal('15'), Decimal('45')),
        ]
        
        bill = Bill(
            bill_id="INV-003",
            vendor_name="Vendor",
            date="2024-01-15",
            line_items=items
        )
        
        # 10 + 40 + 45 = 95
        assert bill.calculate_line_items_total() == Decimal('95')
    
    def test_get_computed_final_total(self):
        """Test computed final total equals line items sum."""
        items = [
            LineItem("A", Decimal('1'), Decimal('100'), Decimal('100')),
            LineItem("B", Decimal('2'), Decimal('50'), Decimal('100')),
        ]
        
        bill = Bill(
            bill_id="INV-004",
            vendor_name="Vendor",
            date="2024-01-15",
            line_items=items
        )
        
        assert bill.get_computed_final_total() == Decimal('200')
    
    def test_verify_total_matches(self):
        """Test verify_total when totals match."""
        items = [
            LineItem("Item", Decimal('2'), Decimal('25'), Decimal('50')),
        ]
        
        bill = Bill(
            bill_id="INV-005",
            vendor_name="Vendor",
            date="2024-01-15",
            line_items=items,
            final_total=Decimal('50')
        )
        
        assert bill.verify_total() is True
    
    def test_verify_total_mismatch(self):
        """Test verify_total when totals don't match."""
        items = [
            LineItem("Item", Decimal('2'), Decimal('25'), Decimal('50')),
        ]
        
        bill = Bill(
            bill_id="INV-006",
            vendor_name="Vendor",
            date="2024-01-15",
            line_items=items,
            final_total=Decimal('60')  # Wrong!
        )
        
        assert bill.verify_total() is False
    
    def test_get_discrepancy(self):
        """Test calculating discrepancy between totals."""
        items = [
            LineItem("Item", Decimal('2'), Decimal('25'), Decimal('50')),
        ]
        
        bill = Bill(
            bill_id="INV-007",
            vendor_name="Vendor",
            date="2024-01-15",
            line_items=items,
            final_total=Decimal('55')
        )
        
        # 55 - 50 = 5
        assert bill.get_discrepancy() == Decimal('5')
    
    def test_empty_bill_total(self):
        """Test total for bill with no line items."""
        bill = Bill(
            bill_id="INV-008",
            vendor_name="Vendor",
            date="2024-01-15"
        )
        
        assert bill.calculate_line_items_total() == Decimal('0')
        assert bill.get_computed_final_total() == Decimal('0')
