import os
import io
import base64
import json
import logging
import re
import socket
import ipaddress
import requests
import re
from urllib.parse import urlparse
from PIL import Image
from flask import Flask, request, jsonify
from flask_cors import CORS
import google.generativeai as genai
from dotenv import load_dotenv
from pdf2image import convert_from_bytes

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Configuration
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
PDF_DPI = int(os.getenv("PDF_DPI", "100"))
# Allowed domains for document URLs (comma-separated, empty means allow all public URLs)
ALLOWED_DOMAINS = os.getenv("ALLOWED_DOMAINS", "").split(",") if os.getenv("ALLOWED_DOMAINS") else []

# Initialize Gemini client
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# Token tracking
class TokenTracker:
    def __init__(self):
        self.total_tokens = 0
        self.input_tokens = 0
        self.output_tokens = 0
    
    def add_usage(self, usage):
        if usage:
            prompt_tokens = getattr(usage, 'prompt_token_count', 0) or 0
            candidates_tokens = getattr(usage, 'candidates_token_count', 0) or 0
            total = getattr(usage, 'total_token_count', 0) or (prompt_tokens + candidates_tokens)
            self.input_tokens += prompt_tokens
            self.output_tokens += candidates_tokens
            self.total_tokens += total
    
    def get_usage(self):
        return {
            "total_tokens": self.total_tokens,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens
        }


def is_private_ip(hostname):
    """Check if hostname resolves to a private IP address."""
    try:
        # Resolve hostname to IP address
        ip = socket.gethostbyname(hostname)
        ip_obj = ipaddress.ip_address(ip)
        # Check if IP is private, loopback, or link-local
        return (
            ip_obj.is_private or
            ip_obj.is_loopback or
            ip_obj.is_link_local or
            ip_obj.is_reserved or
            ip_obj.is_multicast
        )
    except (socket.gaierror, ValueError):
        # If we can't resolve, reject for safety
        return True


def validate_url(url):
    """Validate URL scheme and hostname to prevent SSRF attacks."""
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ('http', 'https'):
            raise ValueError(f"Invalid URL scheme: {parsed.scheme}. Only http and https are allowed.")
        if not parsed.netloc:
            raise ValueError("Invalid URL: missing hostname")
        
        hostname = parsed.hostname
        if not hostname:
            raise ValueError("Invalid URL: missing hostname")
        
        # Check against allowed domains if configured
        if ALLOWED_DOMAINS and hostname not in ALLOWED_DOMAINS:
            # Check if it's a subdomain of an allowed domain
            is_allowed = any(
                hostname == domain or hostname.endswith('.' + domain)
                for domain in ALLOWED_DOMAINS
            )
            if not is_allowed:
                raise ValueError(f"Domain '{hostname}' is not in the allowed list")
        
        # Block private/internal IP addresses to prevent SSRF
        if is_private_ip(hostname):
            raise ValueError("Access to private/internal IP addresses is not allowed")
        
        return True
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"Invalid URL: {str(e)}")

def convert_google_drive_url(url: str) -> str:
    """
    Convert common Google Drive sharing URLs to the direct download 'uc?export=download&id=...' URL.
    Returns original url if it doesn't look like a Drive share link.
    """
    # Examples:
    # https://drive.google.com/file/d/<id>/view?usp=sharing
    # https://drive.google.com/open?id=<id>
    m = re.search(r'/file/d/([a-zA-Z0-9_-]+)', url)
    if m:
        file_id = m.group(1)
        return f'https://drive.google.com/uc?export=download&id={file_id}'
    m = re.search(r'drive.google.com.*?id=([a-zA-Z0-9_-]+)', url)
    if m:
        file_id = m.group(1)
        return f'https://drive.google.com/uc?export=download&id={file_id}'
    return url


def download_document(url):
    """Download document from URL and return content and type."""
    try:
        # Validate URL to prevent SSRF
        validate_url(url)
        
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        content = response.content
        content_type = response.headers.get('Content-Type', '')
        
        # Determine file type from content or URL
        # Check content length before accessing bytes
        is_pdf = (
            'pdf' in content_type.lower() or
            url.lower().endswith('.pdf') or
            (len(content) >= 4 and content[:4] == b'%PDF')
        )
        if is_pdf:
            return content, 'pdf'
        else:
            # Assume image
            return content, 'image'
    except ValueError:
        raise
    except Exception as e:
        raise Exception(f"Failed to download document: {str(e)}")


def convert_pdf_to_images(pdf_bytes):
    """Convert PDF bytes to list of PIL images."""
    try:
        images = convert_from_bytes(pdf_bytes, dpi=PDF_DPI)
        return images
    except Exception as e:
        raise Exception(f"Failed to convert PDF to images: {str(e)}")


def image_to_base64(image):
    """Convert PIL image to base64 string."""
    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')


def extract_line_items_from_image(image_base64, page_no, token_tracker):
    """Use Gemini Vision to extract line items from a single page image."""
    
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
        # Initialize the Gemini model
        model = genai.GenerativeModel(GEMINI_MODEL)
        
        # Decode base64 image
        image_bytes = base64.b64decode(image_base64)
        
        # Create the image part for Gemini
        image_part = {
            "mime_type": "image/png",
            "data": image_bytes
        }
        
        # Generate content with image
        response = model.generate_content(
            [prompt, image_part],
            generation_config=genai.GenerationConfig(
                temperature=0.1,
                max_output_tokens=4096
            )
        )
        
        # Track token usage
        if hasattr(response, 'usage_metadata'):
            token_tracker.add_usage(response.usage_metadata)
        
        # Parse response
        content = response.text.strip()
        
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
        # Log the error and raw response for debugging
        logger.warning(f"Failed to parse JSON response for page {page_no}: {str(e)}")
        logger.debug(f"Raw response content: {content if 'content' in dir() else 'unavailable'}")
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
    port = int(os.getenv('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=os.getenv('DEBUG', 'False').lower() == 'true')
