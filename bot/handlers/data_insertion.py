from openpyxl import load_workbook
from openpyxl.drawing.image import Image
from datetime import date, timedelta
import os


def insert_data(organisation_name, extracted_data, temp_dir):
    # Validate input data
    if not isinstance(extracted_data, dict):
        raise ValueError(f"Expected dictionary for extracted_data, got {type(extracted_data)}")
    
    if 'error' in extracted_data:
        raise ValueError(f"Error in extracted data: {extracted_data['error']}")
    
    # Use the permanent forms directory for the template
    template_path = f'forms/{organisation_name}_form.xlsx'
    if not os.path.exists(template_path):
        raise FileNotFoundError(f"Template file not found: {template_path}")
    
    # Use the temporary directory for the output file
    output_path = os.path.join(temp_dir, f'{organisation_name}_form_filled.xlsx')
    
    try:
        template = load_workbook(template_path)
        template_ws = template.active

        # Get current date and next month's date
        today = date.today()
        next_month = today + timedelta(days=30)  # TODO: change to next month

        # Fill in the template with extracted data
        template_ws['F10'] = today.strftime('%d/%m/%Y')
        template_ws['F11'] = next_month.strftime('%d/%m/%Y')

        # Map of cell positions to data keys
        cell_mapping = {
            'L20': 'driver_name',
            'E22': 'passport_series',
            'J22': 'passport_number',
            'E23': 'passport_authority',
            'E24': 'passport_date_issued',
            'E25': 'number_plates',
            'E28': 'vendor_name'  # TODO: make an if clause for palisandr bc it's E27 or fix the template
        }

        # Add logo to the template
        logo_path = f'forms/{organisation_name}_logo.png'
        logo = Image(logo_path)
        logo.width = 100
        logo.height = 100
        template_ws.add_image(logo, 'C44')

        # Fill in each cell with corresponding data
        for cell, key in cell_mapping.items():
            value = extracted_data.get(key)
            if value is None:
                print(f"Warning: Missing data for key '{key}'")
            template_ws[cell] = value

        template.save(output_path)
        return output_path
        
    except Exception as e:
        print(f"Error in insert_data: {str(e)}")
        raise



