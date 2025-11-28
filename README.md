# Bill Data Extraction

A Python-based solution for extracting and summarizing line item details from bills/invoices.

## Features

- **Line Item Extraction**: Extract individual line items with description, quantity, unit price, and amount
- **Sub-total Support**: Handle sub-totals where they exist in bills
- **Final Total Calculation**: Calculate final totals by summing line items without double-counting
- **Multi-page Bill Support**: Process bills with multiple pages
- **Total Verification**: Verify stated totals against computed totals and identify discrepancies

## Installation

```bash
pip install -r requirements.txt
```

## Usage

### Basic Usage

```python
from src.extractor import BillExtractor
from src.summarizer import BillSummarizer

# Create extractor and summarizer
extractor = BillExtractor()
summarizer = BillSummarizer()

# Extract bill from JSON file
bill = extractor.extract_from_json_file('data/sample_bills/invoice_001.json')

# Generate summary
summary = summarizer.summarize(bill)

# Get individual line item amounts
for item in summary.line_item_details:
    print(f"{item['description']}: ${item['amount']}")

# Get sub-totals (where they exist)
for subtotal in summary.sub_totals:
    print(f"{subtotal['label']}: ${subtotal['amount']}")

# Get final total (without double-counting)
print(f"Final Total: ${summary.computed_total}")
```

### Extract from Dictionary

```python
bill_data = {
    'bill_id': 'INV-001',
    'vendor_name': 'Vendor Name',
    'date': '2024-01-15',
    'line_items': [
        {'description': 'Item 1', 'quantity': 2, 'unit_price': 10.00, 'amount': 20.00},
        {'description': 'Item 2', 'quantity': 1, 'unit_price': 30.00, 'amount': 30.00},
    ],
    'final_total': 50.00
}

bill = extractor.extract_from_dict(bill_data)
```

### Process Multiple Bills

```python
bills = [
    extractor.extract_from_json_file('invoice_001.json'),
    extractor.extract_from_json_file('invoice_002.json'),
]

result = summarizer.summarize_multiple(bills)
print(f"Combined Total: ${result['combined_total']}")
```

### Formatted Summary

```python
formatted = summarizer.get_formatted_summary(bill)
print(formatted)
```

## Data Models

### LineItem
- `description`: Description of the item/service
- `quantity`: Number of units
- `unit_price`: Price per unit
- `amount`: Total amount for this line item
- `category`: Optional category for grouping

### SubTotal
- `label`: Description of what the sub-total represents
- `amount`: The sub-total amount
- `line_item_refs`: References to included line items

### Bill
- `bill_id`: Unique identifier
- `vendor_name`: Name of vendor/merchant
- `date`: Date of the bill
- `line_items`: List of line items
- `sub_totals`: List of sub-totals
- `final_total`: Stated final total
- `currency`: Currency code (default: USD)
- `page_count`: Number of pages

## Running Tests

```bash
pytest tests/ -v
```

## Project Structure

```
├── src/
│   ├── __init__.py
│   ├── models.py      # Data models (LineItem, SubTotal, Bill)
│   ├── extractor.py   # Bill extraction logic
│   └── summarizer.py  # Summarization and total calculation
├── tests/
│   ├── __init__.py
│   ├── test_models.py
│   ├── test_extractor.py
│   └── test_summarizer.py
├── data/
│   └── sample_bills/  # Sample bill data
├── requirements.txt
└── README.md
```