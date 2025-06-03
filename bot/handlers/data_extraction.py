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
from bot.logger import setup_logger

# Set up logger
logger = setup_logger(__name__)

load_dotenv()
OPENAI_API = os.getenv('OPENAI_API')

client = OpenAI(
  api_key=OPENAI_API
)

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
        logger.warning(f"EXIF read error: {e}")
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
        logger.debug(f"OCR orientation scores: {orientations}")
        return best_angle
        
    except Exception as e:
        logger.error(f"OCR error: {e}", exc_info=True)
        return 0, 0.0

def detect_document_orientation(image_path: str) -> Tuple[int, float]:
    """
    Detect document orientation using EXIF data and OCR.
    Returns (rotation_angle, confidence_score)
    """
    logger.info(f"Starting orientation detection for: {image_path}")
    
    # First try EXIF data
    exif_angle = get_exif_orientation(image_path)
    if exif_angle is not None:
        logger.info(f"Found EXIF orientation: {exif_angle}°")
        return exif_angle, 1.0
    
    # If no EXIF data, try OCR
    logger.info("No EXIF data, trying OCR detection...")
    return detect_text_orientation(image_path)

def rotate_image(image_path: str, angle: int) -> str:
    """
    Rotates an image by the specified angle and returns the path to the rotated image.
    """
    logger.info(f"Rotating image {image_path} by {angle}°")
    
    try:
        img = Image.open(image_path)
        if angle != 0:
            img = img.rotate(angle, expand=True)
        
        # Save the rotated image
        rotated_path = image_path.replace('.', '_rotated.')
        img.save(rotated_path)
        logger.info(f"Saved rotated image to: {rotated_path}")
        
        return rotated_path
    except Exception as e:
        logger.error(f"Rotation error: {e}", exc_info=True)
        return image_path

def extract_text_from_openai_api(images):
    """
    Sends the base64-encoded image to the OpenAI API and retrieves the extracted text.
    """
    logger.info("Starting image processing for OpenAI API")
    
    # Process each image for correct orientation
    processed_images = []
    for i, image_path in enumerate(images):
        logger.info(f"Processing image {i+1}/{len(images)}: {image_path}")
        
        # Detect orientation
        rotation_angle, confidence = detect_document_orientation(image_path)
        logger.info(f"Detected orientation - Angle: {rotation_angle}°, Confidence: {confidence:.2f}")
        
        # If we're confident about the orientation and it's not 0 degrees
        if confidence > 0.5 and rotation_angle != 0:
            # Rotate the image
            rotated_path = rotate_image(image_path, rotation_angle)
            processed_images.append(rotated_path)
            logger.info(f"Using rotated image: {rotated_path}")
        else:
            processed_images.append(image_path)
            logger.info("Using original image (no rotation needed)")
    
    # encode every image
    logger.info("Encoding images for API")
    base64_images = [encode_image(image_path) for image_path in processed_images]

    # dictionary with all the content
    content_list = []
    for base64_image in base64_images:
        content_list.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{base64_image}"
            }
        })

    try:
        response = client.chat.completions.create(
            model="gpt-4-vision-preview",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": """Extract the following information from the document:
1. Full name (ФИО)
2. Passport series and number (Серия и номер паспорта)
3. Passport issuing authority (Кем выдан)
4. Passport issue date (Дата выдачи)
5. Vehicle registration number (Номерные знаки)

Format the response as a JSON object with the following keys:
- driver_name
- passport_series
- passport_number
- passport_authority
- passport_date_issued
- number_plates

If any field is not found, leave it as an empty string."""
                        },
                        *content_list
                    ]
                }
            ],
            max_tokens=500
        )
        
        logger.info("Successfully received response from OpenAI API")
        return response.choices[0].message.content
        
    except Exception as e:
        logger.error(f"Error calling OpenAI API: {e}", exc_info=True)
        return {"error": str(e)}

@contextmanager
def temporary_directory():
    """Context manager for creating and cleaning up a temporary directory"""
    temp_dir = tempfile.mkdtemp()
    try:
        yield temp_dir
    finally:
        shutil.rmtree(temp_dir)

def process_file(file_path: str) -> dict:
    """
    Process a file (PDF or image) and extract text using OCR.
    Returns a dictionary with extracted data.
    """
    logger.info(f"Processing file: {file_path}")
    
    try:
        file_type = get_file_type(file_path)
        logger.info(f"Detected file type: {file_type}")
        
        if file_type == 'pdf':
            # Convert PDF to images
            doc = pymupdf.open(file_path)
            images = []
            
            for page in doc:
                pix = page.get_pixmap()
                img_path = f"{file_path}_page_{page.number}.png"
                pix.save(img_path)
                images.append(img_path)
                
            logger.info(f"Converted PDF to {len(images)} images")
            
        elif file_type == 'image':
            images = [file_path]
        else:
            logger.error(f"Unsupported file type: {file_type}")
            return {"error": f"Unsupported file type: {file_type}"}
        
        # Extract text from images
        extracted_text = extract_text_from_openai_api(images)
        logger.info("Successfully extracted text from images")
        
        return extracted_text
        
    except Exception as e:
        logger.error(f"Error processing file: {e}", exc_info=True)
        return {"error": str(e)}

def get_file_type(file_path):
    """Determine if file is PDF or image based on extension"""
    _, ext = os.path.splitext(file_path.lower())
    
    if ext == '.pdf':
        return 'pdf'
    elif ext in ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.gif', '.webp']:
        return 'image'
    else:
        return 'unknown'
