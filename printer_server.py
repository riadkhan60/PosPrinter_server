from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import win32print
import win32api
import tempfile
import time
import base64
from PIL import Image
from io import BytesIO

import webbrowser
import subprocess
import sys


def start_cloudflare_tunnel():
    cloudflared_path = r"C:\Program Files\Cloudflare\bin\cloudflared.exe"
    tunnel_name = "print-server-locale"

    try:
        subprocess.Popen(
            [cloudflared_path, "tunnel", "run", tunnel_name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        print("Cloudflare Tunnel started.")
    except Exception as e:
        print(f"Failed to start Cloudflare Tunnel: {e}")


app = Flask(__name__)
CORS(app)

API_KEY = "your-secret-api-key"  # Store securely in production
PRINTER_NAME = "POSPrinter POS80"  # Your printer name


def validate_api_key(request):
    """Validate the API key in the request"""
    api_key = request.headers.get("X-API-KEY")
    return api_key == API_KEY


def list_printers():
    """List all available printers in Windows"""
    printers = win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL, None, 2)
    print("\nAvailable Printers:")
    for printer in printers:
        print(f" - {printer['pPrinterName']}")
    return [p["pPrinterName"] for p in printers]


def generate_esc_pos_commands(content, print_type="customer"):
    """Generate ESC/POS commands for receipt or kitchen order"""
    ESC = bytes([0x1B])  # Escape
    GS = bytes([0x1D])  # Group Separator
    SMALL_FONT = ESC + b"M" + b"\x01"  # Font B (small)
    NORMAL_FONT = ESC + b"M" + b"\x00"  # Font A (normal)

    INIT = ESC + b"@"  # Initialize printer
    CENTER = ESC + b"a" + bytes([0x01])  # Center align
    LEFT = ESC + b"a" + bytes([0x00])  # Left align
    RIGHT = ESC + b"a" + bytes([0x02])  # Right align
    BOLD_ON = ESC + b"E" + bytes([0x01])  # Bold on
    BOLD_OFF = ESC + b"E" + bytes([0x00])  # Bold off
    DOUBLE_HW = ESC + b"!" + bytes([0x30])  # Double height & width
    DOUBLE_OFF = ESC + b"!" + bytes([0x00])  # Normal size
    QUAD_SIZE = (
        ESC + b"!" + bytes([0x38])
    )  # Quadruple size (double width + double height + emphasized)
    CUT = GS + b"V" + bytes([0x41]) + bytes([0x03])  # Cut paper with feed

    commands = bytearray()
    commands.extend(INIT)

    if print_type == "kitchen":
        # Kitchen print: compact, big font for items and table, only time/date, table, items
        for line in content:
            if line.get("type") == "header":
                commands.extend(CENTER)
                commands.extend(BOLD_ON)
                commands.extend(f"{line.get('text')}\n".encode())
                commands.extend(BOLD_OFF)
                commands.extend(LEFT)
            elif line.get("type") == "text":
                # Make table line big
                if "table" in line.get("text", "").lower():
                    commands.extend(QUAD_SIZE)
                    commands.extend(f"{line.get('text')}\n".encode())
                    commands.extend(DOUBLE_OFF)
                else:
                    commands.extend(f"{line.get('text')}\n".encode())
            elif line.get("type") == "item" or (
                line.get("name") and line.get("quantity")
            ):
                # Use quadruple size for items
                commands.extend(QUAD_SIZE)
                name = line.get("name", line.get("text", ""))
                qty = line.get("quantity", 1)
                commands.extend(f"{name} {qty}\n".encode())
                commands.extend(DOUBLE_OFF)
        # Minimal feed and cut
        commands.extend(b"\n" + CUT)
        return commands

    # Default: customer print (existing logic)
    for idx, line in enumerate(content):
        if line.get("type") == "image":
            image_data = line.get("data", "")
            if image_data:
                try:
                    img_commands = process_image(image_data)
                    if img_commands:
                        commands.extend(CENTER)
                        commands.extend(img_commands)
                        commands.extend(LEFT)
                        commands.extend(b"\n")
                except Exception as e:
                    print(f"Error processing image: {e}")
        elif line.get("type") == "header":
            commands.extend(CENTER)
            commands.extend(BOLD_ON)
            commands.extend(f"{line.get('text')}\n".encode())
            commands.extend(BOLD_OFF)
            commands.extend(LEFT)
        elif line.get("type") == "address":
            commands.extend(SMALL_FONT)
            commands.extend(LEFT)
            commands.extend(f"{line.get('text')}\n".encode())
            commands.extend(NORMAL_FONT)
        elif line.get("type") == "phone":
            commands.extend(SMALL_FONT)
            commands.extend(LEFT)
            commands.extend(f"{line.get('text')}\n".encode())
            commands.extend(NORMAL_FONT)
            commands.extend(b"\n")
        elif line.get("type") == "table-header":
            columns = line.get("columns", [])
            # Improved column widths with better spacing
            col_widths = [5, 22, 5, 5, 8]  # No, Name, Qty, Rate, Total

            # Create header with proper spacing
            header_parts = []
            for i, (col, w) in enumerate(zip(columns, col_widths)):
                if i == 0:  # No column
                    header_parts.append(str(col)[:w].ljust(w))
                elif i == 1:  # Name column (left aligned)
                    header_parts.append(str(col)[:w].ljust(w))
                else:  # Qty, Rate, Total (right aligned)
                    header_parts.append(str(col)[:w].rjust(w))

            header = "".join(header_parts)
            commands.extend(LEFT)  # Use left alignment instead of center
            commands.extend(header.encode() + b"\n")

            # Create separator line with proper width
            separator = "-" * sum(col_widths)
            commands.extend(separator.encode() + b"\n")
        elif line.get("type") == "table-row":
            columns = line.get("columns", [])
            # Match the improved column widths from the header
            col_widths = [5, 22, 5, 5, 8]

            # Format each column in the row with proper alignment
            row_parts = []
            for i, (col, w) in enumerate(zip(columns, col_widths)):
                col_str = str(col)
                # Convert numeric values to integers if possible
                if (
                    i != 1 and col_str.replace(".", "", 1).isdigit()
                ):  # Skip the name column
                    try:
                        col_str = str(int(float(col)))
                    except:
                        pass

                if i == 0:  # No column (left aligned)
                    row_parts.append(col_str[:w].ljust(w))
                elif i == 1:  # Name column (left aligned)
                    row_parts.append(col_str[:w].ljust(w))
                else:  # Qty, Rate, Total (right aligned)
                    row_parts.append(col_str[:w].rjust(w))

            row = "".join(row_parts)
            commands.extend(LEFT)  # Use left alignment instead of center
            commands.extend(row.encode() + b"\n")
            # If next line is not a table-row, print separator
            next_line = content[idx + 1] if idx + 1 < len(content) else None
            if not (next_line and next_line.get("type") == "table-row"):
                separator = "-" * sum(col_widths)
                commands.extend(separator.encode() + b"\n")
        elif line.get("type") == "discount":
            label = line.get("label", "Discount")
            amount = line.get("amount", "")
            try:
                amount_str = (
                    f"-{int(float(amount.replace('-', '')))}"
                    if "-" in amount
                    else str(int(float(amount)))
                )
            except:
                amount_str = amount

            # Align with the column layout
            total_width = sum([5, 22, 5, 5, 8])  # Sum of all column widths
            discount_line = f"{label:<{total_width-8}}{amount_str:>8}\n"
            commands.extend(discount_line.encode())
        elif line.get("type") == "subtotal":
            label = line.get("label", "Sub-total")
            amount = line.get("amount", "")
            try:
                amount_str = "Tk." + str(int(float(amount)))
            except:
                amount_str = amount

            # Align with the column layout
            total_width = sum([5, 22, 5, 5, 8])  # Sum of all column widths
            subtotal_line = f"{label:<{total_width-8}}{amount_str:>8}\n"
            commands.extend(subtotal_line.encode())
            commands.extend(b"\n")
        elif line.get("type") == "item":
            name = line.get("name", "")
            quantity = int(float(line.get("quantity", 1)))
            price = int(float(line.get("price", 0)))
            total = quantity * price

            # Format with better spacing to mimic the table structure
            no_col_width = 5
            name_col_width = 22
            qty_col_width = 5
            rate_col_width = 5
            total_col_width = 8

            # Left align the item name/number, right align the numeric values
            item_text = f"{name:<{name_col_width+no_col_width}}x{quantity:>{qty_col_width}}  {price:>{rate_col_width}}  {total:>{total_col_width}}\n"
            commands.extend(item_text.encode())
        elif line.get("type") == "total":
            commands.extend(("-" * 45).encode() + b"\n")  # Consistent separator width
            commands.extend(RIGHT)
            amount = int(float(line.get("amount", 0)))
            commands.extend(f"TOTAL: tk.{amount}\n".encode())
            commands.extend(("-" * 45).encode() + b"\n")  # Consistent separator width
            commands.extend(LEFT)
        elif line.get("type") == "text":
            align = line.get("align", "left")
            if align == "left":
                commands.extend(LEFT)
            elif align == "center":
                commands.extend(CENTER)
            elif align == "right":
                commands.extend(RIGHT)
            commands.extend(f"{line.get('text')}\n".encode())
            commands.extend(LEFT)  # Reset to left after
        elif line.get("text"):
            commands.extend(f"{line.get('text')}\n".encode())
    commands.extend(CENTER)
    commands.extend("\nThank you for your purchase!\n\n".encode())
    commands.extend(CUT)
    return commands


def process_image(base64_data):
    """
    Process base64 image and convert to ESC/POS printer format
    For thermal printers, we need to convert images to monochrome bitmap
    """
    try:
        # Commands for bitmap printing
        GS = bytes([0x1D])

        # Parse the base64 data
        if "base64," in base64_data:
            # Handle data URLs like "data:image/png;base64,..."
            base64_data = base64_data.split("base64,")[1]

        # Decode base64 data
        image_data = base64.b64decode(base64_data)

        # Open the image using PIL
        img = Image.open(BytesIO(image_data))

        # If image has alpha channel, paste it on white background
        if img.mode in ("RGBA", "LA"):
            background = Image.new("RGB", img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[-1])  # Use alpha channel as mask
            img = background

        # Resize image if too large - make logo smaller
        max_width = 312  # 1.7 times larger than the original 180
        if img.width > max_width:
            ratio = max_width / img.width
            new_height = int(img.height * ratio)
            img = img.resize((max_width, new_height), Image.LANCZOS)

        # Convert to black and white (1-bit)
        img = img.convert("1")

        # Get image dimensions
        width, height = img.size

        # Calculate bytes per line (width / 8, rounded up)
        bytes_per_line = (width + 7) // 8

        # ESC/POS GS v 0 command for printing bitmap
        # Format: GS v 0 m xL xH yL yH d1...dk
        # m=0: normal mode
        # xL, xH: width in bytes as lower and upper byte
        # yL, yH: height in pixels as lower and upper byte
        command = bytearray(
            GS
            + b"v0"
            + bytes(
                [
                    0,
                    bytes_per_line & 0xFF,
                    (bytes_per_line >> 8) & 0xFF,
                    height & 0xFF,
                    (height >> 8) & 0xFF,
                ]
            )
        )

        # Convert image to bitmap data
        pixels = list(img.getdata())

        # Process each row of the image
        for y in range(height):
            for x in range(0, width, 8):
                # Process 8 pixels at a time (1 byte)
                byte_val = 0

                # For each of the 8 bits in this byte
                for bit in range(8):
                    # Make sure we don't go past the width of the image
                    if x + bit < width:
                        # Get pixel value (0 for black, 1 for white in mode "1")
                        # For ESC/POS, we need to invert: 1 for black, 0 for white
                        pixel = pixels[y * width + x + bit]
                        if pixel == 0:  # Black pixel
                            byte_val |= 1 << (7 - bit)

                # Add the byte to the command
                command.append(byte_val)

        return command

    except Exception as e:
        print(f"Error processing image: {e}")
        return None


def print_to_windows_printer(printer_name, raw_data):
    """Send raw data to a Windows printer"""
    try:
        # Create a temporary file to hold the ESC/POS commands
        fd, path = tempfile.mkstemp(suffix=".prn")
        os.write(fd, raw_data)
        os.close(fd)

        # Get the default printer if none specified
        if not printer_name or printer_name.lower() == "default":
            printer_name = win32print.GetDefaultPrinter()

        print(f"Printing to: {printer_name}")

        # Open the printer
        hPrinter = win32print.OpenPrinter(printer_name)
        try:
            # Start a document
            hJob = win32print.StartDocPrinter(hPrinter, 1, ("Receipt", None, "RAW"))
            try:
                # Start a page
                win32print.StartPagePrinter(hPrinter)

                # Write the raw data directly to the printer
                win32print.WritePrinter(hPrinter, raw_data)

                # End the page
                win32print.EndPagePrinter(hPrinter)
            finally:
                # End the document
                win32print.EndDocPrinter(hPrinter)
        finally:
            # Close the printer
            win32print.ClosePrinter(hPrinter)

        # Remove the temporary file
        try:
            os.remove(path)
        except:
            pass

        return True, "Print job sent successfully"
    except Exception as e:
        print(f"Error printing: {e}")
        return False, str(e)


def print_receipt(content, print_type="customer"):
    """Print receipt to thermal printer"""
    try:
        commands = generate_esc_pos_commands(content, print_type)
        return print_to_windows_printer(PRINTER_NAME, commands)
    except Exception as e:
        print(f"Error printing receipt: {e}")
        return False, str(e)


@app.route("/print", methods=["POST"])
def handle_print():
    if not validate_api_key(request):
        return jsonify({"error": "Unauthorized"}), 401
    try:
        content = request.json.get("content")
        print_type = request.json.get("print_type", "customer")
        if not content:
            return jsonify({"error": "Print content is required"}), 400
        success, message = print_receipt(content, print_type)
        if success:
            return jsonify({"success": True, "message": "Print job sent successfully"})
        else:
            return jsonify({"error": message}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/", methods=["GET"])
def home():
    """Server homepage with basic information and test print option"""
    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Thermal Printer Server</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 0; padding: 20px; line-height: 1.6; }
            .container { max-width: 800px; margin: 0 auto; }
            h1 { color: #333; }
            button { background: #4CAF50; color: white; border: none; padding: 10px 15px; cursor: pointer; }
            button:hover { background: #45a049; }
            pre { background: #f4f4f4; padding: 15px; border-radius: 5px; overflow: auto; }
            .success { color: green; font-weight: bold; }
            .error { color: red; font-weight: bold; }
            #result { margin-top: 20px; padding: 10px; border-radius: 5px; display: none; }
            .dropzone { border: 2px dashed #ccc; border-radius: 5px; padding: 25px; text-align: center; margin: 20px 0; }
            .dropzone.highlight { border-color: #2196F3; background: #e3f2fd; }
            #imagePreview { max-width: 100%; max-height: 200px; margin-top: 10px; display: none; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Thermal Printer Server</h1>
            <p>Server is running and ready to process print requests.</p>
            
            <h2>Available Printers</h2>
            <pre id="printerList">Loading printers...</pre>
            
            <h2>Send Test Print</h2>
            <p>Current printer: <strong id="currentPrinter"></strong></p>
            <button onclick="sendTestPrint()">Print Test Receipt</button>

            <h2>Test Print with Logo</h2>
            <div class="dropzone" id="dropzone">
                <p>Drop logo image here or click to upload</p>
                <input type="file" id="fileInput" accept="image/*" style="display: none;">
                <img id="imagePreview" alt="Logo Preview">
            </div>
            <button id="printWithLogo" disabled>Print Receipt with Logo</button>
            
            <div id="result"></div>
            
            <h2>API Documentation</h2>
            <p>Send print requests to: <code>POST /print</code></p>
            <p>Required header: <code>X-API-KEY: your-secret-api-key</code></p>
            <p>Example request body:</p>
            <pre>{
  "content": [
    {"type": "image", "data": "base64_encoded_image_data..."},
    {"type": "header", "text": "TEST RECEIPT"},
    {"type": "item", "name": "Test Item", "quantity": 1, "price": 10.99},
    {"type": "total", "amount": 10.99}
  ]
}</pre>
        </div>

        <script>
            // Get printer list on page load
            fetch('/printers')
                .then(response => response.json())
                .then(data => {
                    document.getElementById('printerList').textContent = 
                        data.printers.join('\\n');
                });
                
            // Display current printer name
            document.getElementById('currentPrinter').textContent = 
                'POSPrinter POS80';
                
            // Function to send test print
            function sendTestPrint() {
                const resultDiv = document.getElementById('result');
                resultDiv.style.display = 'block';
                resultDiv.innerHTML = 'Sending test print...';
                resultDiv.className = '';
                
                fetch('/test-print', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-API-KEY': 'your-secret-api-key'
                    }
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        resultDiv.innerHTML = '✓ ' + data.message;
                        resultDiv.className = 'success';
                    } else {
                        resultDiv.innerHTML = '✗ ' + data.error;
                        resultDiv.className = 'error';
                    }
                })
                .catch(error => {
                    resultDiv.innerHTML = '✗ Error: ' + error;
                    resultDiv.className = 'error';
                });
            }

            // Setup drag and drop for logo upload
            const dropzone = document.getElementById('dropzone');
            const fileInput = document.getElementById('fileInput');
            const imagePreview = document.getElementById('imagePreview');
            const printWithLogoBtn = document.getElementById('printWithLogo');
            let logoBase64 = null;

            // Open file dialog when clicking on dropzone
            dropzone.addEventListener('click', () => {
                fileInput.click();
            });

            // Handle file selection
            fileInput.addEventListener('change', handleFileSelect);

            // Prevent default drag behaviors
            ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
                dropzone.addEventListener(eventName, preventDefaults, false);
            });

            // Highlight dropzone when dragging over it
            ['dragenter', 'dragover'].forEach(eventName => {
                dropzone.addEventListener(eventName, highlight, false);
            });

            ['dragleave', 'drop'].forEach(eventName => {
                dropzone.addEventListener(eventName, unhighlight, false);
            });

            // Handle dropped files
            dropzone.addEventListener('drop', handleDrop, false);

            // Print with logo button
            printWithLogoBtn.addEventListener('click', () => {
                if (logoBase64) {
                    const resultDiv = document.getElementById('result');
                    resultDiv.style.display = 'block';
                    resultDiv.innerHTML = 'Sending print with logo...';
                    resultDiv.className = '';
                    
                    fetch('/print', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-API-KEY': 'your-secret-api-key'
                        },
                        body: JSON.stringify({
                            content: [
                                {"type": "image", "data": logoBase64},
                                {"type": "header", "text": "RECEIPT WITH LOGO"},
                                {"type": "item", "name": "Test Item", "quantity": 1, "price": 12.99},
                                {"type": "total", "amount": 12.99},
                                {"type": "text", "text": "Logo printing is working!"}
                            ]
                        })
                    })
                    .then(response => response.json())
                    .then(data => {
                        if (data.success) {
                            resultDiv.innerHTML = '✓ ' + data.message;
                            resultDiv.className = 'success';
                        } else {
                            resultDiv.innerHTML = '✗ ' + data.error;
                            resultDiv.className = 'error';
                        }
                    })
                    .catch(error => {
                        resultDiv.innerHTML = '✗ Error: ' + error;
                        resultDiv.className = 'error';
                    });
                }
            });

            // Helper functions
            function preventDefaults(e) {
                e.preventDefault();
                e.stopPropagation();
            }

            function highlight() {
                dropzone.classList.add('highlight');
            }

            function unhighlight() {
                dropzone.classList.remove('highlight');
            }

            function handleDrop(e) {
                const dt = e.dataTransfer;
                const files = dt.files;
                if (files.length) {
                    handleFiles(files);
                }
            }

            function handleFileSelect(e) {
                const files = e.target.files;
                if (files.length) {
                    handleFiles(files);
                }
            }

            function handleFiles(files) {
                const file = files[0];
                if (file.type.startsWith('image/')) {
                    const reader = new FileReader();
                    reader.onload = function(e) {
                        // Display preview
                        imagePreview.src = e.target.result;
                        imagePreview.style.display = 'block';
                        
                        // Store base64 data for printing
                        logoBase64 = e.target.result.split(',')[1]; // Remove data:image/png;base64,
                        
                        // Enable print button
                        printWithLogoBtn.disabled = false;
                    };
                    reader.readAsDataURL(file);
                }
            }
        </script>
    </body>
    </html>
    """
    return html


@app.route("/printers", methods=["GET"])
def get_printers():
    """Endpoint to get available printers"""
    printers = list_printers()
    return jsonify({"printers": printers})


@app.route("/test-print", methods=["POST"])
def test_print():
    """Endpoint to send a test print from the web interface"""
    if not validate_api_key(request):
        return jsonify({"error": "Unauthorized"}), 401

    test_content = [
        {"type": "header", "text": "TEST RECEIPT"},
        {"type": "item", "name": "Test Item", "quantity": 1, "price": 9.99},
        {"type": "total", "amount": 9.99},
        {"type": "text", "text": "Printer server is working!"},
    ]

    success, message = print_receipt(test_content)

    if success:
        return jsonify({"success": True, "message": "Test print sent successfully!"})
    else:
        return jsonify({"success": False, "error": message}), 500


def send_test_print():
    """Send a test print to confirm printer is working"""
    print("\nSending test print to verify printer setup...")
    test_content = [
        {"type": "header", "text": "TEST RECEIPT"},
        {"type": "item", "name": "Test Item", "quantity": 1, "price": 9.99},
        {"type": "total", "amount": 9.99},
        {"type": "text", "text": "Printer server is working!"},
    ]

    success, message = print_receipt(test_content)
    if success:
        print("✓ Test print successful! Printer is ready.")
    else:
        print(f"✗ Test print failed: {message}")
        print("Check printer connection and configuration.")


def start_nextjs_project(nextjs_path, port=3000):
    """
    Start a built Next.js project using 'next start' and open it in the browser.
    :param nextjs_path: Path to the Next.js project directory (where package.json is).
    :param port: Port to run the Next.js server on (default 3000).
    """
    try:
        if sys.platform == "win32":
            command = f'cmd /c "cd /d {nextjs_path} && npx next start -p {port}"'
            subprocess.Popen(
                command, shell=True, creationflags=subprocess.CREATE_NEW_CONSOLE
            )
        else:
            command = f"cd {nextjs_path} && npx next start -p {port}"
            subprocess.Popen(command, shell=True)
        print(f"Next.js project started at http://localhost:{port}")

        # Wait a few seconds for the server to start, then open in browser
        time.sleep(20)
        webbrowser.open(f"http://localhost:{port}")

    except Exception as e:
        print(f"Failed to start Next.js project: {e}")


def start_node_script(node_script_path):
    """
    Start a Node.js script (e.g., index.js) in the given directory.
    """
    try:
        if sys.platform == "win32":
            command = f'cmd /c "cd /d {node_script_path} && node index.js"'
            subprocess.Popen(
                command, shell=True, creationflags=subprocess.CREATE_NEW_CONSOLE
            )
        else:
            command = f"cd {node_script_path} && node index.js"
            subprocess.Popen(command, shell=True)
        print(f"Node.js script started in {node_script_path}")
    except Exception as e:
        print(f"Failed to start Node.js script: {e}")


if __name__ == "__main__":
    print("Starting Windows printer server...")
    # start_cloudflare_tunnel()

    # List available printers
    available_printers = list_printers()

    # Check if our target printer is available
    if PRINTER_NAME not in available_printers:
        print(f"WARNING: Printer '{PRINTER_NAME}' not found in available printers")
        print("Please check the printer name and update the PRINTER_NAME variable")
        print("Available printer names are shown above")
    else:
        # Send test print if printer is available
        time.sleep(5)

    # Install requirements if you don't have them:
    # pip install pillow flask flask-cors pywin32
    start_nextjs_project(r"E:\chikenhut\chikenhutapp", port=3000)
    start_node_script(r"E:\chikenhut\sendReport")
    start_node_script(r"E:\chikenhut\dbbackup")

    print(f"Server running on http://localhost:5000")
    app.run(host="0.0.0.0", port=5000)
