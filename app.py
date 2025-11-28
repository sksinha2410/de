import os
import io
import base64
import json
import re
import tempfile
import requests
from PIL import Image
from flask import Flask, request, jsonify
from flask_cors import CORS
from openai import OpenAI
from dotenv import load_dotenv
from pdf2image import convert_from_bytes

load_dotenv()

app = Flask(__name__)
CORS(app)

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Token tracking
class TokenTracker:
    def __init__(self):
        self.total_tokens = 0
        self.input_tokens = 0
        self.output_tokens = 0
    
    def add_usage(self, usage):
        if usage:
            self.total_tokens += usage.total_tokens
            self.input_tokens += usage.prompt_tokens
            self.output_tokens += usage.completion_tokens
    
    def get_usage(self):
        return {
            "total_tokens": self.total_tokens,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens
        }


def download_document(url):
    """Download document from URL and return content and type."""
    try:
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        content = response.content
        content_type = response.headers.get('Content-Type', '')
        
        # Determine file type from content or URL
        if 'pdf' in content_type.lower() or url.lower().endswith('.pdf') or content[:4] == b'%PDF':
            return content, 'pdf'
        else:
            # Assume image
            return content, 'image'
    except Exception as e:
        raise Exception(f"Failed to download document: {str(e)}")


def convert_pdf_to_images(pdf_bytes):
    """Convert PDF bytes to list of PIL images."""
    try:
        images = convert_from_bytes(pdf_bytes, dpi=150)
        return images
    except Exception as e:
        raise Exception(f"Failed to convert PDF to images: {str(e)}")


def image_to_base64(image):
    """Convert PIL image to base64 string."""
    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')


def extract_line_items_from_image(image_base64, page_no, token_tracker):
    """Use GPT-4 Vision to extract line items from a single page image."""
    
    prompt = """Analyze this bill/invoice page and extract ALL line items with their details.

For each line item, extract:
1. item_name: The exact name/description of the item as written in the bill
2. item_amount: The net/total amount for this item (after any discounts) as a float
3. item_rate: The unit rate/price per item as a float (if available, otherwise use the amount)
4. item_quantity: The quantity of the item as a float (if available, otherwise use 1)

Also determine the page_type which can be one of:
- "Bill Detail": If this page contains detailed line items of the bill
- "Final Bill": If this page shows the final summary/total of the bill
- "Pharmacy": If this page contains pharmacy/medicine items

IMPORTANT RULES:
1. Extract EVERY line item visible on the page - do not miss any
2. Do NOT include subtotals, totals, taxes, or summary rows as line items
3. Do NOT double count items that appear in both detail and summary
4. Extract amounts exactly as shown (post-discount if discounts are applied)
5. If a column is not visible for an item, make reasonable inferences or use defaults

Return ONLY a valid JSON object in this exact format (no markdown, no explanation):
{
    "page_type": "Bill Detail | Final Bill | Pharmacy",
    "bill_items": [
        {
            "item_name": "string",
            "item_amount": float,
            "item_rate": float,
            "item_quantity": float
        }
    ]
}

If no line items are found on this page, return:
{
    "page_type": "Bill Detail",
    "bill_items": []
}"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_base64}",
                                "detail": "high"
                            }
                        }
                    ]
                }
            ],
            max_tokens=4096,
            temperature=0.1
        )
        
        # Track token usage
        token_tracker.add_usage(response.usage)
        
        # Parse response
        content = response.choices[0].message.content.strip()
        
        # Remove markdown code blocks if present
        if content.startswith('```'):
            content = re.sub(r'^```json?\s*', '', content)
            content = re.sub(r'\s*```$', '', content)
        
        result = json.loads(content)
        
        # Ensure proper structure
        page_type = result.get('page_type', 'Bill Detail')
        bill_items = result.get('bill_items', [])
        
        # Validate and clean bill items
        cleaned_items = []
        for item in bill_items:
            cleaned_item = {
                "item_name": str(item.get('item_name', '')),
                "item_amount": float(item.get('item_amount', 0)),
                "item_rate": float(item.get('item_rate', item.get('item_amount', 0))),
                "item_quantity": float(item.get('item_quantity', 1))
            }
            if cleaned_item['item_name']:  # Only include items with names
                cleaned_items.append(cleaned_item)
        
        return {
            "page_no": str(page_no),
            "page_type": page_type,
            "bill_items": cleaned_items
        }
        
    except json.JSONDecodeError as e:
        # Return empty result if parsing fails
        return {
            "page_no": str(page_no),
            "page_type": "Bill Detail",
            "bill_items": []
        }
    except Exception as e:
        raise Exception(f"Failed to extract line items from page {page_no}: {str(e)}")


def process_document(content, doc_type, token_tracker):
    """Process document and extract line items from all pages."""
    pagewise_line_items = []
    
    if doc_type == 'pdf':
        # Convert PDF to images
        images = convert_pdf_to_images(content)
        
        for i, image in enumerate(images, start=1):
            image_base64 = image_to_base64(image)
            page_result = extract_line_items_from_image(image_base64, i, token_tracker)
            pagewise_line_items.append(page_result)
    else:
        # Single image
        image = Image.open(io.BytesIO(content))
        # Convert to RGB if necessary
        if image.mode in ('RGBA', 'P'):
            image = image.convert('RGB')
        image_base64 = image_to_base64(image)
        page_result = extract_line_items_from_image(image_base64, 1, token_tracker)
        pagewise_line_items.append(page_result)
    
    return pagewise_line_items


@app.route('/extract-bill-data', methods=['POST'])
def extract_bill_data():
    """API endpoint to extract bill data from document."""
    try:
        # Get request data
        data = request.get_json()
        
        if not data or 'document' not in data:
            return jsonify({
                "is_success": False,
                "error": "Missing 'document' field in request body"
            }), 400
        
        document_url = data['document']
        
        # Initialize token tracker
        token_tracker = TokenTracker()
        
        # Download document
        content, doc_type = download_document(document_url)
        
        # Process document and extract line items
        pagewise_line_items = process_document(content, doc_type, token_tracker)
        
        # Calculate total item count
        total_item_count = sum(len(page['bill_items']) for page in pagewise_line_items)
        
        # Build response
        response = {
            "is_success": True,
            "token_usage": token_tracker.get_usage(),
            "data": {
                "pagewise_line_items": pagewise_line_items,
                "total_item_count": total_item_count
            }
        }
        
        return jsonify(response), 200
        
    except Exception as e:
        return jsonify({
            "is_success": False,
            "error": str(e),
            "token_usage": {
                "total_tokens": 0,
                "input_tokens": 0,
                "output_tokens": 0
            }
        }), 500


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({"status": "healthy"}), 200


if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=os.getenv('DEBUG', 'False').lower() == 'true')
