"""Tests for bill summarization."""

from decimal import Decimal

import pytest

from src.models import Bill, LineItem, SubTotal
from src.summarizer import BillSummarizer, BillSummary


class TestBillSummarizer:
    """Tests for BillSummarizer class."""
    
    @pytest.fixture
    def summarizer(self):
        """Create a BillSummarizer instance."""
        return BillSummarizer()
    
    @pytest.fixture
    def sample_bill(self):
        """Create a sample bill for testing."""
        items = [
            LineItem("Widget A", Decimal('2'), Decimal('10'), Decimal('20')),
            LineItem("Widget B", Decimal('3'), Decimal('15'), Decimal('45')),
            LineItem("Service Fee", Decimal('1'), Decimal('5'), Decimal('5')),
        ]
        sub_totals = [
            SubTotal("Products", Decimal('65'), [0, 1]),
        ]
        return Bill(
            bill_id="INV-001",
            vendor_name="Test Vendor",
            date="2024-01-15",
            line_items=items,
            sub_totals=sub_totals,
            final_total=Decimal('70')
        )
    
    def test_summarize_basic(self, summarizer, sample_bill):
        """Test basic summarization."""
        summary = summarizer.summarize(sample_bill)
        
        assert summary.bill_id == "INV-001"
        assert summary.vendor_name == "Test Vendor"
        assert summary.date == "2024-01-15"
    
    def test_summarize_line_items(self, summarizer, sample_bill):
        """Test line item details extraction."""
        summary = summarizer.summarize(sample_bill)
        
        assert len(summary.line_item_details) == 3
        
        assert summary.line_item_details[0]['description'] == "Widget A"
        assert summary.line_item_details[0]['amount'] == "20"
        
        assert summary.line_item_details[1]['description'] == "Widget B"
        assert summary.line_item_details[1]['amount'] == "45"
        
        assert summary.line_item_details[2]['description'] == "Service Fee"
        assert summary.line_item_details[2]['amount'] == "5"
    
    def test_summarize_sub_totals(self, summarizer, sample_bill):
        """Test sub-total extraction."""
        summary = summarizer.summarize(sample_bill)
        
        assert len(summary.sub_totals) == 1
        assert summary.sub_totals[0]['label'] == "Products"
        assert summary.sub_totals[0]['amount'] == "65"
    
    def test_computed_total(self, summarizer, sample_bill):
        """Test computed total is sum of line items."""
        summary = summarizer.summarize(sample_bill)
        
        # 20 + 45 + 5 = 70
        assert summary.computed_total == Decimal('70')
    
    def test_total_without_double_counting(self, summarizer):
        """Test that total is calculated without double-counting sub-totals."""
        # Create a bill where sub-total could cause double-counting
        items = [
            LineItem("Item 1", Decimal('1'), Decimal('50'), Decimal('50')),
            LineItem("Item 2", Decimal('1'), Decimal('30'), Decimal('30')),
        ]
        sub_totals = [
            SubTotal("Sub-total", Decimal('80'), [0, 1]),
        ]
        
        bill = Bill(
            bill_id="INV-002",
            vendor_name="Vendor",
            date="2024-01-15",
            line_items=items,
            sub_totals=sub_totals,
            final_total=Decimal('80')
        )
        
        # The total should be 80, NOT 160 (which would happen if
        # sub-total was incorrectly added to line items)
        total = summarizer.calculate_total_without_double_counting(bill)
        assert total == Decimal('80')
    
    def test_total_match_true(self, summarizer, sample_bill):
        """Test total_match is True when totals match."""
        summary = summarizer.summarize(sample_bill)
        
        assert summary.total_match is True
        assert summary.discrepancy == Decimal('0')
    
    def test_total_match_false(self, summarizer):
        """Test total_match is False when totals don't match."""
        items = [
            LineItem("Item", Decimal('1'), Decimal('100'), Decimal('100')),
        ]
        
        bill = Bill(
            bill_id="INV-003",
            vendor_name="Vendor",
            date="2024-01-15",
            line_items=items,
            final_total=Decimal('110')  # Wrong total
        )
        
        summary = summarizer.summarize(bill)
        
        assert summary.total_match is False
        assert summary.discrepancy == Decimal('10')
    
    def test_summarize_multiple_bills(self, summarizer):
        """Test summarizing multiple bills."""
        bill1 = Bill(
            bill_id="INV-001",
            vendor_name="Vendor A",
            date="2024-01-15",
            line_items=[
                LineItem("Item A", Decimal('1'), Decimal('100'), Decimal('100')),
            ]
        )
        
        bill2 = Bill(
            bill_id="INV-002",
            vendor_name="Vendor B",
            date="2024-01-16",
            line_items=[
                LineItem("Item B", Decimal('2'), Decimal('50'), Decimal('100')),
                LineItem("Item C", Decimal('1'), Decimal('25'), Decimal('25')),
            ]
        )
        
        result = summarizer.summarize_multiple([bill1, bill2])
        
        assert result['bill_count'] == 2
        assert result['total_line_items'] == 3
        assert result['combined_total'] == '225'  # 100 + 100 + 25
        assert len(result['individual_summaries']) == 2
    
    def test_formatted_summary(self, summarizer, sample_bill):
        """Test formatted text summary generation."""
        formatted = summarizer.get_formatted_summary(sample_bill)
        
        assert "Bill Summary: INV-001" in formatted
        assert "Vendor: Test Vendor" in formatted
        assert "Widget A" in formatted
        assert "Widget B" in formatted
        assert "Service Fee" in formatted
        assert "Sub-totals:" in formatted
        assert "Products" in formatted
        assert "Computed Total: $70" in formatted
    
    def test_summary_to_dict(self, summarizer, sample_bill):
        """Test converting summary to dictionary."""
        summary = summarizer.summarize(sample_bill)
        result = summary.to_dict()
        
        assert result['bill_id'] == "INV-001"
        assert result['computed_total'] == "70"
        assert result['total_match'] is True
        assert 'line_item_details' in result
        assert 'sub_totals' in result


class TestBillSummary:
    """Tests for BillSummary dataclass."""
    
    def test_create_summary(self):
        """Test creating a BillSummary."""
        summary = BillSummary(
            bill_id="INV-001",
            vendor_name="Vendor",
            date="2024-01-15",
            computed_total=Decimal('100')
        )
        
        assert summary.bill_id == "INV-001"
        assert summary.computed_total == Decimal('100')
        assert summary.total_match is True
    
    def test_summary_defaults(self):
        """Test BillSummary default values."""
        summary = BillSummary(
            bill_id="INV-001",
            vendor_name="Vendor",
            date="2024-01-15"
        )
        
        assert summary.line_item_details == []
        assert summary.sub_totals == []
        assert summary.computed_total == Decimal('0')
        assert summary.stated_total is None
