from django.conf import settings
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, filters

from auto_grader.canvas import CanvasGrader
from auto_grader.models import User, Submission, Assignment, SubmissionStatus, Platform


async def start(update: Update, context):
    user, _ = await User.objects.aget_or_create(
        user_id=update.message.from_user.id,
    )
    user.first_name = update.message.from_user.first_name
    user.last_name = update.message.from_user.last_name
    user.username = update.message.from_user.username
    await user.asave()

    await update.message.reply_text(
        f'Hello {update.message.from_user.first_name}!\nYour user ID is <code>{update.message.from_user.id}</code>.',
        parse_mode='HTML',
    )


async def get_grade_callback(update: Update, context):
    try:
        query = update.callback_query
        _, submission_id, grade = query.data.split('_')
        submission = await Submission.objects.aget(id=submission_id)
        assignment = await Assignment.objects.aget(id=submission.assignment_id)
        
        # Update submission grade
        submission.grade = grade
        
        # Send grade to platform
        platform = await Platform.objects.aget(id=assignment.platform_id)
        if platform and platform.name == 'Canvas':
            canvas_grader = CanvasGrader(platform.api_url, platform.api_key)
            canvas_grader.send_grade(
                course_id=assignment.course_id,
                assignment_id=assignment.assignment_id,
                student_nid=submission.student_nid,
                grade=grade,
                feedback=submission.feedback,
            )
        
        # Update status to grade_posted after successful posting
        submission.status = SubmissionStatus.GRADE_POSTED
        await submission.asave()
        
        await query.answer(
            text=f'You selected {grade} for {submission.student_name}. Grade posted successfully.',
        )
        await query.edit_message_text(
            query.message.text_html_urled + f'\n\n✅ <b>Grade {grade} posted for {submission.student_name}</b>',
            parse_mode='HTML',
            reply_markup=None
        )
        
    except Exception as e:
        # Print full stack trace for debugging
        import traceback
        print(f"Error in get_grade_callback for submission {submission_id}:")
        traceback.print_exc()


async def regenerate_callback(update: Update, context):
    query = update.callback_query
    _, submission_id = query.data.split('_')
    
    # Reset submission status to 'new' for re-grading
    submission = await Submission.objects.aget(id=submission_id)
    submission.status = SubmissionStatus.NEW
    submission.grade = None
    submission.feedback = ""
    await submission.asave()
    
    await query.answer(text='Regenerating feedback...')
    await query.edit_message_text(
        query.message.text_html_urled + f'\n\n🔄 <b>Feedback regeneration requested for submission {submission_id}. Status reset to NEW for re-grading.</b>',
        parse_mode='HTML',
        reply_markup=None
    )


def run_bot():
    application = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler('start', start, filters=filters.ChatType.PRIVATE))
    application.add_handler(CallbackQueryHandler(get_grade_callback, pattern=r'^grade_'))
    application.add_handler(CallbackQueryHandler(regenerate_callback, pattern=r'^regen_'))

    application.run_polling(allowed_updates=Update.ALL_TYPES)
