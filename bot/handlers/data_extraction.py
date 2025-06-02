from openai import OpenAI
import json

client = OpenAI(
  api_key=""
)

import os
import sys
import base64
import openai
import tempfile
import pymupdf

def encode_image(image_path):
    """
    Encodes an image file to a base64 string.
    """
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def extract_text_from_openai_api(images):
    """
    Sends the base64-encoded image to the OpenAI API and retrieves the extracted text.
    """
    # encode every image
    base64_images = [encode_image(image_path) for image_path in images]

    # dictionary with all the content
    content_list = []
    content_list.append({
        "type": "text",
        "text": """Extract the document information into a Python dictionary format with these exact keys:
        {
            'driver_name': 'full name from passport including surname, name and patronymic',
            'passport_series': 'passport series number',
            'passport_number': 'passport number',
            'passport_authority': 'from authority field from passport',
            'passport_date_issued': 'date of issue in DD/MM/YYYY format',
            'number_plates': 'vehicle license plate number from vehicle license separated by a /'
        }
        Only extract information that is clearly visible and readable. Return ONLY the dictionary, no additional text."""
    })
    
    for i in range(len(base64_images)):
        content_list.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{base64_images[i]}"
            }
        })

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
            # Remove markdown code block formatting if present
            response_text = response_text.replace("```python", "").replace("```", "").strip()
            return eval(response_text)
        except Exception as e:
            print(f"Error parsing dictionary response: {response.choices[0].message.content}")
            return {"error": "Failed to parse response as dictionary"}
    except Exception as e:
        print(f"\nError extracting text from image {images}: {e}")
        return {"error": str(e)}

def convert_pdf_to_images(pdf_path, dpi=300):
    """Convert each page of a PDF to an image"""
    images = []
    pdf_document = pymupdf.open(pdf_path)
    
    for page_num in range(len(pdf_document)):
        page = pdf_document.load_page(page_num)
        
        pix = page.get_pixmap(matrix=pymupdf.Matrix(dpi/72, dpi/72))
        
        # Create a unique filename for each page
        image_path = f"/content/temp_{pdf_path.split('/')[-1]}_{page_num}.png"
        pix.save(image_path)
        images.append(image_path)
    
    pdf_document.close()
    return images

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
        images = convert_pdf_to_images(file_path)
        return extract_text_from_openai_api(images)
    elif file_type == 'image':
        return extract_text_from_openai_api([file_path])
    else:
        print(f"Unsupported file type: {file_path}")
        return {"error": "Unsupported file type"}
