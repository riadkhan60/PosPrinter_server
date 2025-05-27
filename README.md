# Thermal Printer Server

A comprehensive Windows-based thermal printer server built with Flask that provides REST API endpoints for printing receipts, kitchen orders, and handling image printing on ESC/POS compatible thermal printers.

## 🚀 Features

- **REST API** for remote printing via HTTP requests
- **ESC/POS Command Generation** for thermal printers
- **Image Printing Support** with base64 encoded images
- **Multiple Print Types**: Customer receipts and kitchen orders
- **Web Interface** for testing and printer management
- **Cloudflare Tunnel Integration** for remote access
- **Auto-start Integration** with Next.js and Node.js projects
- **Windows Printer Integration** using win32print
- **API Key Authentication** for secure access

## 📋 Table of Contents

- [Requirements](#requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [API Documentation](#api-documentation)
- [Web Interface](#web-interface)
- [Building Executable](#building-executable)
- [Cloudflare Tunnel Setup](#cloudflare-tunnel-setup)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)

## 🔧 Requirements

### System Requirements

- **Operating System**: Windows 10/11
- **Python**: 3.7 or higher
- **Thermal Printer**: ESC/POS compatible (e.g., POS80 series)

### Python Dependencies

```
Flask==3.1.1
Flask-CORS==5.0.1
Pillow==11.2.1
pywin32==310
```

### Optional Dependencies

- **Cloudflare Tunnel** (cloudflared) for remote access
- **PyInstaller** for creating standalone executable

## 📦 Installation

### 1. Clone the Repository

```bash
git clone <repository-url>
cd printerServerins
```

### 2. Create Virtual Environment

```bash
python -m venv venv
venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install flask flask-cors pillow pywin32
```

### 4. Install PyInstaller (Optional - for building executable)

```bash
pip install pyinstaller
```

## ⚙️ Configuration

### 1. Printer Configuration

Edit the `PRINTER_NAME` variable in `printer_server.py`:

```python
PRINTER_NAME = "POSPrinter POS80"  # Replace with your printer name
```

To find your printer name:

1. Run the server
2. Visit `http://localhost:5000`
3. Check the "Available Printers" section

### 2. API Key Configuration

Update the API key in `printer_server.py`:

```python
API_KEY = "your-secret-api-key"  # Change this to a secure key
```

### 3. External Project Paths (Optional)

If you want to auto-start other projects, update these paths:

```python
# Next.js project path
start_nextjs_project(r"E:\chikenhut\chikenhutapp", port=3000)

# Node.js script paths
start_node_script(r"E:\chikenhut\sendReport")
start_node_script(r"E:\chikenhut\dbbackup")
```

## 🚀 Usage

### Running the Server

#### Development Mode

```bash
python printer_server.py
```

#### Production Mode (Executable)

```bash
# Build executable first
pyinstaller --onefile --noconsole printer_server.py

# Run the executable
dist\printer_server.exe
```

The server will start on `http://localhost:5000`

### Basic Print Request

```python
import requests

url = "http://localhost:5000/print"
headers = {
    "Content-Type": "application/json",
    "X-API-KEY": "your-secret-api-key"
}

data = {
    "content": [
        {"type": "header", "text": "RECEIPT"},
        {"type": "item", "name": "Coffee", "quantity": 2, "price": 5.50},
        {"type": "total", "amount": 11.00}
    ]
}

response = requests.post(url, json=data, headers=headers)
print(response.json())
```

## 📚 API Documentation

### Base URL

```
http://localhost:5000
```

### Authentication

All API requests require the `X-API-KEY` header:

```
X-API-KEY: your-secret-api-key
```

### Endpoints

#### 1. Print Receipt/Order

**POST** `/print`

**Request Body:**

```json
{
  "content": [
    { "type": "header", "text": "RESTAURANT NAME" },
    { "type": "address", "text": "123 Main St, City" },
    { "type": "phone", "text": "Tel: (555) 123-4567" },
    {
      "type": "table-header",
      "columns": ["No", "Item", "Qty", "Rate", "Total"]
    },
    { "type": "table-row", "columns": ["1", "Coffee", "2", "5", "10"] },
    { "type": "subtotal", "label": "Sub-total", "amount": "10" },
    { "type": "total", "amount": "10" },
    { "type": "text", "text": "Thank you!", "align": "center" }
  ],
  "print_type": "customer"
}
```

**Print Types:**

- `"customer"` - Full receipt with formatting
- `"kitchen"` - Compact kitchen order (large fonts for items)

#### 2. Get Available Printers

**GET** `/printers`

**Response:**

```json
{
  "printers": ["POSPrinter POS80", "Microsoft Print to PDF", "..."]
}
```

#### 3. Test Print

**POST** `/test-print`

Sends a test receipt to verify printer functionality.

#### 4. Web Interface

**GET** `/`

Access the web-based testing interface.

### Content Types

#### Text Elements

```json
{"type": "text", "text": "Sample text", "align": "left|center|right"}
{"type": "header", "text": "HEADER TEXT"}
{"type": "address", "text": "Address line"}
{"type": "phone", "text": "Phone number"}
```

#### Table Elements

```json
{"type": "table-header", "columns": ["Col1", "Col2", "Col3"]},
{"type": "table-row", "columns": ["Data1", "Data2", "Data3"]}
```

#### Item Elements

```json
{ "type": "item", "name": "Product Name", "quantity": 2, "price": 15.99 }
```

#### Financial Elements

```json
{"type": "subtotal", "label": "Sub-total", "amount": "25.50"},
{"type": "discount", "label": "Discount", "amount": "-5.00"},
{"type": "total", "amount": "20.50"}
```

#### Image Elements

```json
{ "type": "image", "data": "base64_encoded_image_data" }
```

## 🌐 Web Interface

Access the web interface at `http://localhost:5000` for:

- **Printer Management**: View available printers
- **Test Printing**: Send test receipts
- **Logo Upload**: Test image printing with drag-and-drop
- **API Documentation**: Interactive examples

### Features:

- Drag-and-drop logo upload
- Real-time printer status
- Test print functionality
- API examples and documentation

## 🏗️ Building Executable

### Using PyInstaller

#### Simple Build

```bash
pyinstaller --onefile --noconsole printer_server.py
```

#### Using Spec File

```bash
pyinstaller printer_server.spec
```

The executable will be created in the `dist/` directory.

### Distribution

The built executable (`printer_server.exe`) can be distributed and run on any Windows machine without Python installation.

## 🌐 Cloudflare Tunnel Setup

### 1. Install Cloudflare Tunnel

Download and install cloudflared from [Cloudflare's website](https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/).

### 2. Create Tunnel

```bash
cloudflared tunnel create print-server-locale
```

### 3. Configure Tunnel

Create a configuration file and update the tunnel name in the code:

```python
tunnel_name = "print-server-locale"  # Your tunnel name
```

### 4. Run Tunnel

The tunnel will start automatically when the server runs, or manually:

```bash
cloudflared tunnel run print-server-locale
```

## 🔧 Troubleshooting

### Common Issues

#### 1. Printer Not Found

```
WARNING: Printer 'POSPrinter POS80' not found
```

**Solution:**

- Check printer connection
- Update `PRINTER_NAME` variable
- Use the web interface to see available printers

#### 2. Permission Denied

```
Error printing: Access is denied
```

**Solution:**

- Run as administrator
- Check printer permissions
- Ensure printer is not in use

#### 3. Image Not Printing

```
Error processing image: ...
```

**Solution:**

- Ensure image is valid base64
- Check image format (PNG, JPG supported)
- Verify image size (max width: 312px)

#### 4. API Key Error

```
{"error": "Unauthorized"}
```

**Solution:**

- Include `X-API-KEY` header
- Verify API key matches server configuration

### Debug Mode

Enable debug mode by modifying the Flask app:

```python
app.run(host="0.0.0.0", port=5000, debug=True)
```

### Logging

Add logging for troubleshooting:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 📁 Project Structure

```
printerServerins/
├── printer_server.py          # Main server application
├── printer_server.spec        # PyInstaller configuration
├── tunnel_open.py            # Cloudflare tunnel helper
├── README.md                 # This file
├── .gitignore               # Git ignore rules
├── venv/                    # Virtual environment
├── dist/                    # Built executables
└── build/                   # Build artifacts
```

## 🔒 Security Considerations

1. **Change Default API Key**: Always use a strong, unique API key
2. **Network Security**: Consider firewall rules for production
3. **HTTPS**: Use Cloudflare Tunnel or reverse proxy for HTTPS
4. **Input Validation**: The server validates print content
5. **Access Control**: Limit network access to trusted sources

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For support and questions:

1. Check the [Troubleshooting](#troubleshooting) section
2. Review the [API Documentation](#api-documentation)
3. Test with the [Web Interface](#web-interface)
4. Create an issue in the repository

## 📝 Changelog

### Version 1.0.0

- Initial release
- Basic printing functionality
- Web interface
- Image support
- Kitchen order printing
- Cloudflare tunnel integration

---

**Made with ❤️ for thermal printing automation**
