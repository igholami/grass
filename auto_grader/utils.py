from django.conf import settings
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
import asyncio

class RubricGradeButton:
    def __init__(self, grade_number, short_description):
        self.grade_number = grade_number
        self.short_description = short_description

async def send_grading_message(
    chat_id,
    student_name,
    student_id,
    course_id,
    assignment_id,
    student_nid,
    similarity_score,
    grade,
    feedback,
    submission_id,
    rubric_grades: list[RubricGradeButton],
    canvas_url: str,
):
    """
    Send a grading message with inline keyboard buttons.
    
    Args:
        chat_id: Telegram chat ID to send message to
        student_name: Student's full name
        student_id: Student's ID (e.g. university ID)
        course_id: Canvas course ID
        assignment_id: Canvas assignment ID
        student_nid: Canvas student numeric ID
        similarity_score: Similarity score as float (0.0-1.0)
        grade: AI-generated grade
        feedback: AI-generated feedback text
        submission_id: Submission ID for callback data
        rubric_grades: List of RubricGrade objects containing grade options
        canvas_url: Canvas instance URL for generating preview URLs
    
    Returns:
        bool: True if the message sent successfully, False otherwise
    """
    try:
        bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
        
        # Create SpeedGrader URL using provided canvas_url
        preview_url = f"{canvas_url.rstrip('/')}/courses/{course_id}/gradebook/speed_grader?assignment_id={assignment_id}&student_id={student_nid}"
        
        # Create message text using the standard template
        message_text = f"""<strong>{student_name}</strong> ({student_id})
<a href="{preview_url}">{preview_url}</a>

<strong>Similarity Score:</strong> {similarity_score}
<strong>Grade:</strong> {grade}
<strong>Feedback:</strong> {feedback}"""

        grade_buttons = []
        
        buttons_row = []
        for rg in rubric_grades:
            button_text = f"{rg.grade_number}: {rg.short_description[:10]}{'...' if len(rg.short_description) > 10 else ''}"
            buttons_row.append(
                InlineKeyboardButton(
                    text=button_text,
                    callback_data=f'grade_{submission_id}_{rg.grade_number}'
                )
            )
            if len(buttons_row) == 2:
                grade_buttons.append(buttons_row)
                buttons_row = []
        if buttons_row:
            grade_buttons.append(buttons_row)

        action_buttons = [
            InlineKeyboardButton(text='🔄 Regenerate', callback_data=f'regen_{submission_id}'),
        ]
        grade_buttons.append(action_buttons)
        
        reply_markup = InlineKeyboardMarkup(grade_buttons)

        # Send the message
        await bot.send_message(
            chat_id=chat_id,
            text=message_text,
            parse_mode='HTML',
            reply_markup=reply_markup
        )
        return True
        
    except Exception as e:
        print(f"Error sending grading message: {str(e)}")
        return False


def send_grading_message_sync(
    chat_id,
    student_name, 
    student_id,
    course_id,
    assignment_id,
    student_nid,
    similarity_score,
    grade,
    feedback,
    submission_id,
    rubric_grades: list[RubricGradeButton],
    canvas_url: str,
):
    """
    Synchronous wrapper for send_grading_message.
    Use this in synchronous contexts like Django management commands.
    """
    return asyncio.run(send_grading_message(
        chat_id=chat_id,
        student_name=student_name,
        student_id=student_id, 
        course_id=course_id,
        assignment_id=assignment_id,
        student_nid=student_nid,
        similarity_score=similarity_score,
        grade=grade,
        feedback=feedback,
        submission_id=submission_id,
        rubric_grades=rubric_grades,
        canvas_url=canvas_url
    ))


def clean_html_text(text):
    """
    Clean HTML content by removing tags and formatting for plain text display.
    
    Args:
        text: HTML text content to clean
        
    Returns:
        str: Cleaned plain text
    """
    if not text:
        return ""
    
    # remove <link> and <script> tags
    import re
    text = re.sub(r'<link.*?>|<script.*?</script>', '', text)
    
    # remove <p> <span> tags
    text = text.replace("<p>", "\n").replace("</p>", "\n").replace("<span>", "").replace("</span>", "")
    # fix ol and ul tags
    text = text.replace("<ol>", "").replace("</ol>", "\n").replace("<ul>", "").replace("</ul>", "\n")
    # change li tags to * and
    text = text.replace("<li>", "\n- ").replace("</li>", "")
    
    # Clean up extra whitespace
    text = re.sub(r'\n\s*\n', '\n\n', text)  # Replace multiple newlines with double newline
    text = text.strip()  # Remove leading/trailing whitespace
    
    return text