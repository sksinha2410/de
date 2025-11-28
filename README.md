# Bill Data Extraction API

A Flask-based API that extracts line item details from bills/invoices (PDF or images) using GPT-4 Vision for OCR and data extraction.

## Features

- Extracts line items from multi-page bills (PDFs and images)
- Provides item details: name, amount, rate, and quantity
- Tracks LLM token usage
- Supports various document formats (PDF, PNG, JPG, etc.)
- Returns structured JSON response with pagewise line items

## Prerequisites

- Python 3.12+
- OpenAI API key with access to GPT-4 Vision
- Poppler (for PDF processing)

## Installation

### Local Setup

1. Clone the repository:
```bash
git clone https://github.com/sksinha2410/de.git
cd de
```

2. Create and activate virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Install Poppler (required for PDF processing):
   - **Ubuntu/Debian**: `sudo apt-get install poppler-utils`
   - **macOS**: `brew install poppler`
   - **Windows**: Download from [poppler releases](https://github.com/oschwartz10612/poppler-windows/releases)

5. Configure environment variables:
```bash
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```

6. Run the application:
```bash
python app.py
```

### Docker Setup

1. Build the Docker image:
```bash
docker build -t bill-extraction-api .
```

2. Run the container:
```bash
docker run -p 5000:5000 -e OPENAI_API_KEY=your_api_key bill-extraction-api
```

## API Endpoints

### POST /extract-bill-data

Extract line items from a bill document.

**Request:**
```json
{
    "document": "https://example.com/path/to/bill.pdf"
}
```

**Response:**
```json
{
    "is_success": true,
    "token_usage": {
        "total_tokens": 1234,
        "input_tokens": 1000,
        "output_tokens": 234
    },
    "data": {
        "pagewise_line_items": [
            {
                "page_no": "1",
                "page_type": "Bill Detail",
                "bill_items": [
                    {
                        "item_name": "Consultation Fee",
                        "item_amount": 500.00,
                        "item_rate": 500.00,
                        "item_quantity": 1.0
                    }
                ]
            }
        ],
        "total_item_count": 1
    }
}
```

**Page Types:**
- `Bill Detail`: Pages containing detailed line items
- `Final Bill`: Summary pages with final totals
- `Pharmacy`: Pages containing pharmacy/medicine items

### GET /health

Health check endpoint.

**Response:**
```json
{
    "status": "healthy"
}
```

## Approach

### Solution Architecture

1. **Document Download**: The API accepts a document URL, downloads the file, and determines whether it's a PDF or image.

2. **PDF Processing**: For PDFs, we use `pdf2image` library to convert each page to an image for processing.

3. **GPT-4 Vision Analysis**: Each page image is sent to OpenAI's GPT-4 Vision model with a carefully crafted prompt that:
   - Extracts all line items with their details
   - Identifies the page type (Bill Detail, Final Bill, Pharmacy)
   - Avoids double counting by not including subtotals/totals as line items

4. **Token Tracking**: All API calls track token usage (input, output, total) for cost monitoring.

5. **Response Aggregation**: Results from all pages are aggregated into the final response with total item count.

### Key Design Decisions

- **GPT-4 Vision (gpt-4o)**: Chosen for its superior OCR and document understanding capabilities
- **High Detail Mode**: Images are processed in "high" detail mode for better accuracy
- **Low Temperature (0.1)**: Used to ensure consistent, deterministic extractions
- **Structured Prompting**: The prompt explicitly instructs the model on what to extract and what to avoid

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | Your OpenAI API key | Required |
| `PORT` | Server port | 5000 |
| `DEBUG` | Enable debug mode | False |

## Testing

You can test the API using curl:

```bash
curl -X POST http://localhost:5000/extract-bill-data \
  -H "Content-Type: application/json" \
  -d '{"document": "https://your-document-url.com/bill.pdf"}'
```

Or using the health endpoint:

```bash
curl http://localhost:5000/health
```

## Deployment

### Production Deployment

For production, the application uses Gunicorn as the WSGI server:

```bash
gunicorn --bind 0.0.0.0:5000 --workers 2 --timeout 120 app:app
```

### Cloud Deployment Options

- **Heroku**: Use the included `Procfile` configuration
- **Docker**: Use the included `Dockerfile`
- **AWS/GCP/Azure**: Deploy as a containerized application

## Limitations

- Requires valid OpenAI API key with GPT-4 Vision access
- Processing time depends on document size and number of pages
- API costs depend on token usage (tracked in response)

## License

MIT License