"""Data models for bill/invoice extraction.

This module defines the data structures used to represent
line items, sub-totals, and complete bills.
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional


@dataclass
class LineItem:
    """Represents a single line item in a bill.
    
    Attributes:
        description: Description of the item/service
        quantity: Number of units
        unit_price: Price per unit
        amount: Total amount for this line item (quantity * unit_price)
        category: Optional category for grouping (e.g., "Food", "Tax")
    """
    description: str
    quantity: Decimal
    unit_price: Decimal
    amount: Decimal
    category: Optional[str] = None
    
    def __post_init__(self):
        """Ensure all numeric fields are Decimal type."""
        self.quantity = Decimal(str(self.quantity))
        self.unit_price = Decimal(str(self.unit_price))
        self.amount = Decimal(str(self.amount))


@dataclass
class SubTotal:
    """Represents a sub-total in a bill.
    
    Sub-totals are intermediate sums, often used to group
    related line items (e.g., all food items, pre-tax total).
    
    Attributes:
        label: Description of what this sub-total represents
        amount: The sub-total amount
        line_item_refs: References to line items included in this sub-total
    """
    label: str
    amount: Decimal
    line_item_refs: list[int] = field(default_factory=list)
    
    def __post_init__(self):
        """Ensure amount is Decimal type."""
        self.amount = Decimal(str(self.amount))


@dataclass 
class Bill:
    """Represents a complete bill/invoice.
    
    Attributes:
        bill_id: Unique identifier for the bill
        vendor_name: Name of the vendor/merchant
        date: Date of the bill
        line_items: List of individual line items
        sub_totals: List of sub-totals (where they exist)
        final_total: The final total amount
        currency: Currency code (default: USD)
        page_count: Number of pages in the bill
    """
    bill_id: str
    vendor_name: str
    date: str
    line_items: list[LineItem] = field(default_factory=list)
    sub_totals: list[SubTotal] = field(default_factory=list)
    final_total: Optional[Decimal] = None
    currency: str = "USD"
    page_count: int = 1
    
    def __post_init__(self):
        """Ensure final_total is Decimal type if provided."""
        if self.final_total is not None:
            self.final_total = Decimal(str(self.final_total))
    
    def calculate_line_items_total(self) -> Decimal:
        """Calculate the sum of all line item amounts.
        
        Returns:
            Sum of all line item amounts without double-counting.
        """
        return sum((item.amount for item in self.line_items), Decimal('0'))
    
    def get_computed_final_total(self) -> Decimal:
        """Get the final total computed from line items.
        
        This method calculates the total from individual line items,
        avoiding double-counting that could occur if sub-totals
        were incorrectly added.
        
        Returns:
            The computed final total from line items.
        """
        return self.calculate_line_items_total()
    
    def verify_total(self) -> bool:
        """Verify if the stated final_total matches computed total.
        
        Returns:
            True if final_total matches computed total, False otherwise.
        """
        if self.final_total is None:
            return True
        return self.final_total == self.get_computed_final_total()
    
    def get_discrepancy(self) -> Decimal:
        """Calculate discrepancy between stated and computed total.
        
        Returns:
            Difference between stated final_total and computed total.
            Returns 0 if no final_total is stated.
        """
        if self.final_total is None:
            return Decimal('0')
        return self.final_total - self.get_computed_final_total()
