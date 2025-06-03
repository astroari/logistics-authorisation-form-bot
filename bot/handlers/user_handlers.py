from aiogram.filters import Command
from aiogram.filters.callback_data import CallbackData
from aiogram import Router, types, F

from bot.config import BotConfig
from bot.handlers.data_extraction import process_file
from bot.handlers.data_insertion import insert_data
from bot.logger import setup_logger

from aiogram.fsm.state import State, StatesGroup

class DocumentFlow(StatesGroup):
    waiting_files = State()
    waiting_company = State()
    waiting_factory = State()

from aiogram.fsm.context import FSMContext

import tempfile
import os

# Set up logger
logger = setup_logger(__name__)

user_router = Router()

@user_router.message(Command('start'))
async def cmd_start(msg: types.Message, config: BotConfig) -> None:
    """Process the /start command."""
    logger.info(f"User {msg.from_user.id} started the bot")
    await msg.answer(config.welcome_message)

@user_router.message(Command('admin_info'))
async def cmd_admin_info(msg: types.Message, config: BotConfig) -> None:
    is_admin = msg.from_user.id in config.admin_ids
    logger.info(f"User {msg.from_user.id} checked admin status: {is_admin}")
    if is_admin:
        await msg.answer("You are an admin.")
    else:
        await msg.answer("You are not an admin.")

@user_router.message(Command('new_form'))
async def cmd_new_form(msg: types.Message, state: FSMContext) -> None:
    """Process the /new_form command."""
    logger.info(f"User {msg.from_user.id} started a new form")
    await msg.answer("Отправьте документы водителя. После отправки нажмите /done.")
    await state.set_state(DocumentFlow.waiting_files)

@user_router.message(DocumentFlow.waiting_files, F.content_type.in_(['document', 'photo']))
async def handle_files(msg: types.Message, state: FSMContext) -> None:
    """Handle files sent by the user."""
    try:
        logger.info(f"User {msg.from_user.id} sent a file")
        # Create a temporary directory to store the file
        with tempfile.TemporaryDirectory() as temp_dir:
            if msg.document:
                file = msg.document
                file_path = os.path.join(temp_dir, file.file_name)
                logger.info(f"Processing document: {file.file_name}")
            else:  # photo
                file = msg.photo[-1]  # Get the highest quality photo
                file_path = os.path.join(temp_dir, f"photo_{file.file_id}.jpg")
                logger.info(f"Processing photo: {file.file_id}")
            
            # Download the file
            await msg.bot.download(file, destination=file_path)
            
            # Process the file and extract data
            extracted_data = process_file(file_path)
            logger.info(f"Extracted data from file: {extracted_data}")
            
            # Get current data and merge with new data
            current_data = await state.get_data()
            files_data = current_data.get('files_data', {})
            
            # Merge the new data with existing data
            for key, value in extracted_data.items():
                if value:  # Only update if the new value is not empty
                    files_data[key] = value
            
            await state.update_data(files_data=files_data)
            logger.info(f"Updated files_data in state: {files_data}")
            
            # Acknowledge receipt
            await msg.answer("✅ Документы получены и обработаны. Вы можете отправить больше документов или нажать /done когда закончите.")
            
    except Exception as e:
        logger.error(f"Error processing document: {str(e)}", exc_info=True)
        await msg.answer(f"❌ Ошибка обработки документа: {str(e)}")

@user_router.message(DocumentFlow.waiting_files, Command('done'))
async def cmd_done(msg: types.Message, state: FSMContext) -> None:
    """Process the /done command."""
    logger.info(f"User {msg.from_user.id} finished uploading files")
    data = await state.get_data()
    files_data = data.get('files_data', {})
    
    if not files_data:
        logger.warning(f"User {msg.from_user.id} tried to finish without uploading any files")
        await msg.answer("Не было обработано ни одного документа. Пожалуйста, загрузите документы.")
        return
        
    # Format the extracted data
    response = "📄 Извлеченные данные:\n"
    fields = {
        'driver_name': 'ФИО',
        'passport_series': 'Серия паспорта',
        'passport_number': 'Номер паспорта',
        'passport_authority': 'Место выдачи',
        'passport_date_issued': 'Дата выдачи',
        'number_plates': 'Номерные знаки'
    }
    
    for field_key, field_name in fields.items():
        value = files_data.get(field_key, '')
        response += f"- {field_name}: {value}\n"
    
    await msg.answer(response)
    await msg.answer(
        "Выберите компанию, которая выдала документы:", 
        reply_markup=get_company_keyboard()
    )
    await state.set_state(DocumentFlow.waiting_company)

class DocumentCallback(CallbackData, prefix="doc"):
    action: str  # "company", "confirm", "edit"
    value: str   # company name, or other value
    step: int = 1

# Create keyboard for company selection
def get_company_keyboard():
    return types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(
            text="🚛 Kedr", 
            callback_data=DocumentCallback(action="company", value="kedr").pack()
        )],
        [types.InlineKeyboardButton(
            text="🏭 Chinwood", 
            callback_data=DocumentCallback(action="company", value="chinwood").pack()
        )],
        [types.InlineKeyboardButton(
            text="🔧 Palisandr", 
            callback_data=DocumentCallback(action="company", value="palisandr").pack()
        )]
    ])

# Handle company selection
@user_router.callback_query(DocumentCallback.filter(F.action == "company"))
async def company_chosen(callback: types.CallbackQuery, callback_data: DocumentCallback, state: FSMContext):
    # Check if we're in the right state
    current_state = await state.get_state()
    if current_state != DocumentFlow.waiting_company:
        logger.warning(f"User {callback.from_user.id} tried to select company in wrong state: {current_state}")
        await callback.answer("Пожалуйста, начните новую форму с /new_form")
        return
    
    company = callback_data.value
    logger.info(f"User {callback.from_user.id} selected company: {company}")
    
    await state.update_data(company=company)
    await callback.message.edit_text(f"Выбрана компания: {company}\n\nТеперь введите название завода:")
    await state.set_state(DocumentFlow.waiting_factory)
    
    # Important: acknowledge the callback
    await callback.answer()

@user_router.message(DocumentFlow.waiting_factory, F.text)
async def factory_chosen(msg: types.Message, state: FSMContext):
    """Handle factory name input."""
    factory_name = msg.text
    logger.info(f"User {msg.from_user.id} entered factory name: {factory_name}")
    
    if not factory_name:
        logger.warning(f"User {msg.from_user.id} tried to submit empty factory name")
        await msg.answer("Название завода не может быть пустым. Пожалуйста, попробуйте снова.")
        return
    
    await state.update_data(factory=factory_name)
    
    data = await state.get_data()
    company = data.get('company')
    factory = data.get('factory')
    files_data = data.get('files_data', {})
    
    try:
        # Create a temporary directory for our output files
        with tempfile.TemporaryDirectory() as temp_dir:
            # Add the factory name to the extracted data
            files_data['vendor_name'] = factory
            logger.info(f"Processing form for company: {company}, factory: {factory}")
            
            filled_form_path = insert_data(company, files_data, temp_dir)
            logger.info(f"Created filled form at: {filled_form_path}")
            
            # Send the filled form to the user
            with open(filled_form_path, 'rb') as file:
                await msg.answer_document(
                    document=types.FSInputFile(filled_form_path),
                    caption=f"Filled form for {factory}"
                )
        
        logger.info(f"Successfully processed and sent form for user {msg.from_user.id}")
        await msg.answer("✅ Форма была обработана и отправлена!")
        
    except Exception as e:
        logger.error(f"Error processing form: {str(e)}", exc_info=True)
        await msg.answer(f"❌ Ошибка обработки формы: {str(e)}")
    
    # Reset the state
    await state.clear()
    logger.info(f"Reset state for user {msg.from_user.id}")



