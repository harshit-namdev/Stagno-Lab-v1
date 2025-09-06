from flask import Flask, render_template, request, jsonify, send_file
import os, secrets, hashlib
from PIL import Image
import time

app = Flask(__name__)
app.secret_key = 'stego-pro-2024-secure'

# Create directories
os.makedirs('temp', exist_ok=True)
os.makedirs('uploads', exist_ok=True)

def stego_encode(img_path, msg, pwd):
    """Enhanced LSB encoding with better error handling"""
    try:
        img = Image.open(img_path).convert('RGB')
        
        # Create signature with password hash
        signature = f"STEGO:{hashlib.md5(pwd.encode()).hexdigest()[:8]}:"
        data = f"{signature}{msg}:END"
        
        # Convert to binary
        binary = ''.join(format(ord(c), '08b') for c in data) + '1111111111111110'
        
        # Check if image can hold the data
        pixels = list(img.getdata())
        if len(binary) > len(pixels):
            raise ValueError("Image too small to hold the message")
        
        # Embed data in LSB
        new_pixels = []
        for i, pixel in enumerate(pixels):
            if i < len(binary):
                r, g, b = pixel
                # Modify only red channel LSB
                new_r = (r & 0xFE) | int(binary[i])
                new_pixels.append((new_r, g, b))
            else:
                new_pixels.append(pixel)
        
        # Create new image
        new_img = Image.new('RGB', img.size)
        new_img.putdata(new_pixels)
        
        # Save with unique filename
        output = f"temp/stego_{secrets.token_hex(6)}_{int(time.time())}.png"
        new_img.save(output, 'PNG', optimize=True)
        
        return output
        
    except Exception as e:
        raise Exception(f"Encoding failed: {str(e)}")

def stego_decode(img_path, pwd):
    """Enhanced LSB decoding with better validation"""
    try:
        img = Image.open(img_path).convert('RGB')
        pixels = list(img.getdata())
        
        # Extract binary data from LSB of red channel
        binary = ''.join(str(pixel[0] & 1) for pixel in pixels)
        
        # Convert binary to text
        data = ""
        for i in range(0, len(binary), 8):
            byte = binary[i:i+8]
            if len(byte) == 8:
                try:
                    char = chr(int(byte, 2))
                    data += char
                    if data.endswith(':END'):
                        break
                except ValueError:
                    continue
        
        # Validate signature and extract message
        expected_signature = f"STEGO:{hashlib.md5(pwd.encode()).hexdigest()[:8]}:"
        
        if data.startswith(expected_signature) and data.endswith(':END'):
            message = data[len(expected_signature):-4]
            return message
        else:
            return None
            
    except Exception as e:
        raise Exception(f"Decoding failed: {str(e)}")

@app.route('/')
def dashboard():
    """Render dashboard from templates folder"""
    return render_template('dashboard.html')

@app.route('/encode', methods=['POST'])
def encode():
    """Enhanced encode endpoint with better error handling"""
    try:
        # Validate request
        if 'image' not in request.files:
            return jsonify({'success': False, 'error': 'No image file provided'})
        
        file = request.files['image']
        message = request.form.get('message', '').strip()
        password = request.form.get('password', '').strip()
        
        # Validate inputs
        if not file or file.filename == '':
            return jsonify({'success': False, 'error': 'Please select an image file'})
        
        if not message:
            return jsonify({'success': False, 'error': 'Please enter a message to hide'})
        
        if len(password) < 4:
            return jsonify({'success': False, 'error': 'Password must be at least 4 characters long'})
        
        # Validate file type
        allowed_extensions = {'png', 'jpg', 'jpeg', 'bmp', 'gif'}
        file_ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
        
        if file_ext not in allowed_extensions:
            return jsonify({'success': False, 'error': 'Please upload a valid image file (PNG, JPG, BMP, GIF)'})
        
        # Save uploaded file
        upload_filename = f"cover_{secrets.token_hex(4)}_{int(time.time())}_{file.filename}"
        upload_path = os.path.join('uploads', upload_filename)
        file.save(upload_path)
        
        # Encode message
        try:
            output_path = stego_encode(upload_path, message, password)
            filename = os.path.basename(output_path)
            
            # Clean up uploaded file
            try:
                os.remove(upload_path)
            except:
                pass
            
            return jsonify({
                'success': True, 
                'filename': filename,
                'message': f'Message successfully hidden in {filename}'
            })
            
        except Exception as e:
            # Clean up uploaded file on error
            try:
                os.remove(upload_path)
            except:
                pass
            return jsonify({'success': False, 'error': str(e)})
        
    except Exception as e:
        return jsonify({'success': False, 'error': f'Server error: {str(e)}'})

@app.route('/decode', methods=['POST'])
def decode():
    """Enhanced decode endpoint with better error handling"""
    try:
        # Validate request
        if 'image' not in request.files:
            return jsonify({'success': False, 'error': 'No image file provided'})
        
        file = request.files['image']
        password = request.form.get('password', '').strip()
        
        # Validate inputs
        if not file or file.filename == '':
            return jsonify({'success': False, 'error': 'Please select a steganographic image'})
        
        if not password:
            return jsonify({'success': False, 'error': 'Please enter the decryption password'})
        
        # Save uploaded file
        upload_filename = f"stego_{secrets.token_hex(4)}_{int(time.time())}_{file.filename}"
        upload_path = os.path.join('uploads', upload_filename)
        file.save(upload_path)
        
        # Decode message
        try:
            message = stego_decode(upload_path, password)
            
            # Clean up uploaded file
            try:
                os.remove(upload_path)
            except:
                pass
            
            if message:
                return jsonify({
                    'success': True, 
                    'message': message,
                    'info': f'Successfully extracted {len(message)} character message'
                })
            else:
                return jsonify({
                    'success': False, 
                    'error': 'Wrong password or no hidden message found in this image'
                })
                
        except Exception as e:
            # Clean up uploaded file on error
            try:
                os.remove(upload_path)
            except:
                pass
            return jsonify({'success': False, 'error': str(e)})
        
    except Exception as e:
        return jsonify({'success': False, 'error': f'Server error: {str(e)}'})

@app.route('/download/<filename>')
def download(filename):
    """Enhanced download with security checks"""
    try:
        # Security: only allow files from temp directory
        file_path = os.path.join('temp', filename)
        
        if not os.path.exists(file_path):
            return jsonify({'error': 'File not found'}), 404
        
        # Security: check if file is in temp directory
        if not os.path.abspath(file_path).startswith(os.path.abspath('temp')):
            return jsonify({'error': 'Access denied'}), 403
        
        return send_file(file_path, as_attachment=True, download_name=filename)
        
    except Exception as e:
        return jsonify({'error': f'Download failed: {str(e)}'}), 500

@app.errorhandler(413)
def too_large(e):
    return jsonify({'success': False, 'error': 'File too large. Maximum size is 16MB.'}), 413

@app.errorhandler(500)
def server_error(e):
    return jsonify({'success': False, 'error': 'Internal server error. Please try again.'}), 500

if __name__ == '__main__':
    print("Starting Steganography Pro Dashboard...")
    print("Templates: Loaded from templates/ folder")
    print("Security: Enhanced validation enabled")
    print("Access: http://localhost:5000")
    print("Features: Landscape optimized, improved curves, fast upload")
    
    # Configure Flask for better file upload handling
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
    
    app.run(debug=True, host='0.0.0.0', port=5000, threaded=True)
