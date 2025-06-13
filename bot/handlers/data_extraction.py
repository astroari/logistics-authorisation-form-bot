from openai import OpenAI
import os
import base64
import tempfile
import pymupdf
import shutil
from contextlib import contextmanager
from PIL import Image
import exifread
import pytesseract
from typing import Tuple, Optional
from dotenv import load_dotenv

load_dotenv()
OPENAI_API = os.getenv('OPENAI_API')

client = OpenAI(
  api_key=OPENAI_API
)

import base64
import tempfile
import pymupdf
import shutil
from contextlib import contextmanager

def encode_image(image_path):
    """
    Encodes an image file to a base64 string.
    """
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def get_exif_orientation(image_path: str) -> Optional[int]:
    """
    Get image orientation from EXIF data.
    Returns rotation angle in degrees (0, 90, 180, or 270) or None if no EXIF data.
    """
    try:
        with open(image_path, 'rb') as f:
            tags = exifread.process_file(f)
            
        if 'Image Orientation' in tags:
            orientation = tags['Image Orientation'].values[0]
            # Convert EXIF orientation to degrees
            orientation_map = {
                1: 0,    # Normal
                3: 180,  # Rotated 180
                6: 90,   # Rotated 90 clockwise
                8: 270   # Rotated 270 clockwise
            }
            return orientation_map.get(orientation, 0)
    except Exception as e:
        print(f"[DEBUG] EXIF read error: {e}")
    return None

def detect_text_orientation(image_path: str) -> Tuple[int, float]:
    """
    Detect document orientation using OCR.
    Returns (rotation_angle, confidence_score)
    """
    try:
        # Try different orientations
        orientations = {
            0: 0.0,   # Current orientation
            90: 0.0,  # Rotated right
            180: 0.0, # Upside down
            270: 0.0  # Rotated left
        }
        
        # Keywords to look for in passports
        passport_keywords = ['PASSPORT', 'PASSPORT NO', 'SURNAME', 'GIVEN NAMES', 'REPUBLIC OF UZBEKISTAN']
        # Keywords to look for in licenses
        license_keywords = ['DAVLAT RAQAM BELGISI', 'RAQAM BELGISI']
        
        # Try each orientation
        for angle in orientations.keys():
            # Rotate image
            img = Image.open(image_path)
            if angle != 0:
                img = img.rotate(angle, expand=True)
            
            # Perform OCR
            text = pytesseract.image_to_string(img).upper()
            
            # Check for passport keywords
            passport_matches = sum(1 for keyword in passport_keywords if keyword in text)
            if passport_matches > 0:
                orientations[angle] = passport_matches / len(passport_keywords)
            
            # Check for license keywords
            license_matches = sum(1 for keyword in license_keywords if keyword in text)
            if license_matches > 0:
                orientations[angle] = max(orientations[angle], license_matches / len(license_keywords))
        
        # Get the best orientation
        best_angle = max(orientations.items(), key=lambda x: x[1])
        print(f"[DEBUG] OCR orientation scores: {orientations}")
        return best_angle
        
    except Exception as e:
        print(f"[DEBUG] OCR error: {e}")
        return 0, 0.0

def detect_document_orientation(image_path: str) -> Tuple[int, float]:
    """
    Detect document orientation using EXIF data and OCR.
    Returns (rotation_angle, confidence_score)
    """
    print(f"\n[DEBUG] Starting orientation detection for: {image_path}")
    
    # First try EXIF data
    exif_angle = get_exif_orientation(image_path)
    if exif_angle is not None:
        print(f"[DEBUG] Found EXIF orientation: {exif_angle}°")
        return exif_angle, 1.0
    
    # If no EXIF data, try OCR
    print("[DEBUG] No EXIF data, trying OCR detection...")
    return detect_text_orientation(image_path)

def rotate_image(image_path: str, angle: int) -> str:
    """
    Rotates an image by the specified angle and returns the path to the rotated image.
    """
    print(f"[DEBUG] Rotating image {image_path} by {angle}°")
    
    try:
        img = Image.open(image_path)
        if angle != 0:
            img = img.rotate(angle, expand=True)
        
        # Save the rotated image
        rotated_path = image_path.replace('.', '_rotated.')
        img.save(rotated_path)
        print(f"[DEBUG] Saved rotated image to: {rotated_path}")
        
        return rotated_path
    except Exception as e:
        print(f"[DEBUG] Rotation error: {e}")
        return image_path

def extract_text_from_openai_api(images):
    """
    Sends the base64-encoded image to the OpenAI API and retrieves the extracted text.
    """
    print("\n[DEBUG] Starting image processing for OpenAI API")
    
    # Process each image for correct orientation
    processed_images = []
    for i, image_path in enumerate(images):
        print(f"\n[DEBUG] Processing image {i+1}/{len(images)}: {image_path}")
        
        # Detect orientation
        rotation_angle, confidence = detect_document_orientation(image_path)
        print(f"[DEBUG] Detected orientation - Angle: {rotation_angle}°, Confidence: {confidence:.2f}")
        
        # If we're confident about the orientation and it's not 0 degrees
        if confidence > 0.5 and rotation_angle != 0:
            # Rotate the image
            rotated_path = rotate_image(image_path, rotation_angle)
            processed_images.append(rotated_path)
            print(f"[DEBUG] Using rotated image: {rotated_path}")
        else:
            processed_images.append(image_path)
            print(f"[DEBUG] Using original image (no rotation needed)")
    
    # encode every image
    print("\n[DEBUG] Encoding images for API")
    base64_images = [encode_image(image_path) for image_path in processed_images]
    print(f'[DEBUG] number of images in base64_images: {len(base64_images)}')

    # dictionary with all the content
    content_list = []
    content_list.append({
        "type": "text",
        "text": """Extract the document information into a Python dictionary format (check all the documents). Based on the document type, extract only the relevant fields:

        For passport documents, extract these fields:
        {
            'driver_name': 'full name from passport including surname, name and patronymic',
            'passport_number': 'passport number',
            'passport_authority': 'from authority field from passport, usually starts with MIA',
            'passport_date_issued': 'date of issue in DD/MM/YYYY format'
        }

        For vehicle license documents, extract only the vehicle licence plate / DAVLAT RAQAM BELGISI, found at line 1.:
        {
            'number_plates': 'vehicle license plate'
        }

        Only extract information that is clearly visible and readable. Return ONLY the python dictionaries as a list, no additional text."""
    })
    
    for i in range(len(base64_images)):
        content_list.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{base64_images[i]}"
            }
        })
    print(f'[DEBUG] number of messages in content_list: {len(content_list)}')
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": content_list
                }
            ]
        )
        # Clean the response and convert to dictionary
        try:
            response_text = response.choices[0].message.content
            print(f'[DEBUG] printing response_text_1: {response_text} ')
            # Remove markdown code block formatting if present
            response_text = response_text.replace("```python", "").replace("```", "").replace("```json", "").strip()
            response_text = eval(response_text)
            print(f'[DEBUG] printing response_text_2: {response_text} ')
            
            # Convert single dictionary to list if needed
            if isinstance(response_text, dict):
                response_text = [response_text]
            
            # Combine both dictionaries
            number_plates = [i['number_plates'] for i in response_text if 'number_plates' in i and i['number_plates']]
            keys = ['driver_name', 'passport_series', 'passport_number', 'passport_authority', 'passport_date_issued', 'number_plates']
            default_value = 'not extracted'
            response_dict = dict.fromkeys(keys, default_value)
            for i in response_text:
                response_dict.update(i)
            response_dict['number_plates'] = '/'.join(list(set(number_plates)))

            print(f'[DEBUG] printing response_text_3: {response_dict} ')
            return response_dict
        except Exception as e:
            print(f"Error parsing dictionary response: {response.choices[0].message.content}")
            return {"error": "Failed to parse response as dictionary"}
    except Exception as e:
        print(f"\nError extracting text from image {images}: {e}")
        return {"error": str(e)}

@contextmanager
def temporary_directory():
    """Context manager for creating and cleaning up a temporary directory"""
    temp_dir = tempfile.mkdtemp()
    try:
        yield temp_dir
    finally:
        shutil.rmtree(temp_dir)

def convert_pdf_to_images(pdf_path, dpi=300):
    """
    Convert each page of a PDF to an image and process it through the OpenAI API.
    
    Args:
        pdf_path (str): Path to the PDF file
        dpi (int): Resolution for the output images (default: 300)
    
    Returns:
        dict: Dictionary containing extracted information or error message
    """
    try:
        pdf_document = pymupdf.open(pdf_path)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            images = []
            for page_num in range(len(pdf_document)):
                page = pdf_document.load_page(page_num)
        
                pix = page.get_pixmap(matrix=pymupdf.Matrix(dpi/72, dpi/72))
                
                # Create a unique filename for each page in the temporary directory
                image_path = os.path.join(temp_dir, f"page_{page_num}.png")
                pix.save(image_path)
                images.append(image_path)
            
            # Process all images through the OpenAI API
            return extract_text_from_openai_api(images)
            
    except Exception as e:
        print(f"Error processing PDF: {e}")
        return {"error": str(e)}
    finally:
        if 'pdf_document' in locals():
            pdf_document.close()

def get_file_type(file_path):
    """Determine if file is PDF or image based on extension"""
    _, ext = os.path.splitext(file_path.lower())
    
    if ext == '.pdf':
        return 'pdf'
    elif ext in ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.gif', '.webp']:
        return 'image'
    else:
        return 'unknown'

def process_file(file_path):
    file_type = get_file_type(file_path)
    
    if file_type == 'pdf':
        return convert_pdf_to_images(file_path)
    elif file_type == 'image':
        return extract_text_from_openai_api([file_path])
    else:
        print(f"Unsupported file type: {file_path}")
        return {"error": "Unsupported file type"}
