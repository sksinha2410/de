"""Bill summarization module.

This module provides functionality to summarize bill data,
calculating totals without double-counting.
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

from .models import Bill, LineItem


@dataclass
class BillSummary:
    """Summary of extracted bill data.
    
    Attributes:
        bill_id: Unique identifier for the bill
        vendor_name: Name of the vendor
        date: Date of the bill
        line_item_details: List of line item summaries
        sub_totals: List of sub-total labels and amounts
        computed_total: Total calculated from line items
        stated_total: Total as stated in the bill (if any)
        total_match: Whether computed and stated totals match
        discrepancy: Difference between stated and computed total
    """
    bill_id: str
    vendor_name: str
    date: str
    line_item_details: list[dict] = field(default_factory=list)
    sub_totals: list[dict] = field(default_factory=list)
    computed_total: Decimal = Decimal('0')
    stated_total: Optional[Decimal] = None
    total_match: bool = True
    discrepancy: Decimal = Decimal('0')
    
    def to_dict(self) -> dict:
        """Convert summary to dictionary format.
        
        Returns:
            Dictionary representation of the summary.
        """
        return {
            'bill_id': self.bill_id,
            'vendor_name': self.vendor_name,
            'date': self.date,
            'line_item_details': self.line_item_details,
            'sub_totals': self.sub_totals,
            'computed_total': str(self.computed_total),
            'stated_total': str(self.stated_total) if self.stated_total else None,
            'total_match': self.total_match,
            'discrepancy': str(self.discrepancy)
        }


class BillSummarizer:
    """Summarizes bill data and calculates totals.
    
    This class provides methods to summarize bills, extract
    line item details, and calculate totals without double-counting.
    """
    
    def summarize(self, bill: Bill) -> BillSummary:
        """Generate a summary of a bill.
        
        Extracts line item details and calculates the final total
        by summing individual line items (avoiding double-counting).
        
        Args:
            bill: The Bill object to summarize.
        
        Returns:
            A BillSummary object with all extracted details.
        """
        line_item_details = self._extract_line_item_details(bill.line_items)
        sub_total_details = self._extract_sub_total_details(bill)
        computed_total = bill.get_computed_final_total()
        
        return BillSummary(
            bill_id=bill.bill_id,
            vendor_name=bill.vendor_name,
            date=bill.date,
            line_item_details=line_item_details,
            sub_totals=sub_total_details,
            computed_total=computed_total,
            stated_total=bill.final_total,
            total_match=bill.verify_total(),
            discrepancy=bill.get_discrepancy()
        )
    
    def summarize_multiple(self, bills: list[Bill]) -> dict:
        """Summarize multiple bills and calculate combined totals.
        
        Args:
            bills: List of Bill objects to summarize.
        
        Returns:
            Dictionary with individual summaries and combined totals.
        """
        summaries = [self.summarize(bill) for bill in bills]
        
        combined_total = sum(
            (s.computed_total for s in summaries),
            Decimal('0')
        )
        
        total_line_items = sum(
            len(s.line_item_details) for s in summaries
        )
        
        return {
            'bill_count': len(bills),
            'total_line_items': total_line_items,
            'combined_total': str(combined_total),
            'individual_summaries': [s.to_dict() for s in summaries]
        }
    
    def _extract_line_item_details(
        self, 
        line_items: list[LineItem]
    ) -> list[dict]:
        """Extract details from line items.
        
        Args:
            line_items: List of LineItem objects.
        
        Returns:
            List of dictionaries with line item details.
        """
        details = []
        for i, item in enumerate(line_items):
            details.append({
                'index': i + 1,
                'description': item.description,
                'quantity': str(item.quantity),
                'unit_price': str(item.unit_price),
                'amount': str(item.amount),
                'category': item.category
            })
        return details
    
    def _extract_sub_total_details(self, bill: Bill) -> list[dict]:
        """Extract sub-total details from a bill.
        
        Args:
            bill: The Bill object.
        
        Returns:
            List of dictionaries with sub-total details.
        """
        details = []
        for st in bill.sub_totals:
            details.append({
                'label': st.label,
                'amount': str(st.amount),
                'line_item_count': len(st.line_item_refs)
            })
        return details
    
    def calculate_total_without_double_counting(self, bill: Bill) -> Decimal:
        """Calculate final total from line items without double-counting.
        
        This method ensures that only individual line items are summed,
        avoiding the inclusion of sub-totals which would cause
        double-counting.
        
        Args:
            bill: The Bill object.
        
        Returns:
            The total amount calculated from line items only.
        """
        return bill.calculate_line_items_total()
    
    def get_formatted_summary(self, bill: Bill) -> str:
        """Generate a formatted text summary of the bill.
        
        Args:
            bill: The Bill object to summarize.
        
        Returns:
            Formatted string representation of the bill summary.
        """
        summary = self.summarize(bill)
        
        lines = [
            f"Bill Summary: {summary.bill_id}",
            f"{'=' * 50}",
            f"Vendor: {summary.vendor_name}",
            f"Date: {summary.date}",
            f"",
            "Line Items:",
            "-" * 50
        ]
        
        for item in summary.line_item_details:
            lines.append(
                f"  {item['index']}. {item['description']}: "
                f"{item['quantity']} x ${item['unit_price']} = "
                f"${item['amount']}"
            )
        
        lines.append("")
        
        if summary.sub_totals:
            lines.append("Sub-totals:")
            lines.append("-" * 50)
            for st in summary.sub_totals:
                lines.append(f"  {st['label']}: ${st['amount']}")
            lines.append("")
        
        lines.append("-" * 50)
        lines.append(f"Computed Total: ${summary.computed_total}")
        
        if summary.stated_total is not None:
            lines.append(f"Stated Total: ${summary.stated_total}")
            if not summary.total_match:
                lines.append(
                    f"⚠️  Discrepancy: ${summary.discrepancy}"
                )
        
        return "\n".join(lines)
