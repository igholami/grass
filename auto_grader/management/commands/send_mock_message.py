from django.core.management.base import BaseCommand
from django.conf import settings
from auto_grader.models import User
from auto_grader.utils import send_grading_message_sync


class Command(BaseCommand):
    help = 'Send a mock message with the same format as real grading messages'

    def add_arguments(self, parser):
        parser.add_argument('--chat-id', type=int, help='Telegram chat ID to send message to (defaults to first user in database)')
        parser.add_argument('--student-name', type=str, default='John Doe', help='Student name')
        parser.add_argument('--student-id', type=str, default='12345', help='Student ID')
        parser.add_argument('--course-id', type=str, default='123456', help='Canvas course ID')
        parser.add_argument('--assignment-id', type=str, default='789012', help='Canvas assignment ID') 
        parser.add_argument('--student-nid', type=str, default='54321', help='Canvas student numeric ID')
        parser.add_argument('--similarity-score', type=float, default=0.85, help='Similarity score (0.0-1.0)')
        parser.add_argument('--grade', type=str, default='M', choices=['E', 'M', 'R', 'N'], help='AI-generated grade (E/M/R/N)')
        parser.add_argument('--feedback', type=str, default='Your solution demonstrates good understanding but could benefit from better variable naming.', help='AI-generated feedback')
        parser.add_argument('--submission-id', type=int, default=999, help='Mock submission ID for callbacks')

    def handle(self, *args, **options):
        # Get chat_id - use provided one or default to first user in database
        chat_id = options['chat_id']
        if chat_id is None:
            try:
                first_user = User.objects.first()
                if first_user:
                    chat_id = first_user.user_id
                    self.stdout.write(
                        self.style.SUCCESS(f'Using default chat ID from database: {chat_id} ({first_user.first_name} {first_user.last_name})')
                    )
                else:
                    # Fallback to a test chat ID if no users in database
                    chat_id = 123456789  # Default test chat ID
                    self.stdout.write(
                        self.style.WARNING(f'No users found in database. Using fallback test chat ID: {chat_id}')
                    )
                    self.stdout.write(
                        self.style.WARNING('Note: This may fail if the chat ID doesn\'t exist. Consider adding --chat-id parameter.')
                    )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Error getting default chat ID: {str(e)}')
                )
                return

        student_name = options['student_name']
        student_id = options['student_id']
        course_id = options['course_id']
        assignment_id = options['assignment_id']
        student_nid = options['student_nid']
        similarity_score = options['similarity_score']
        grade = options['grade']
        feedback = options['feedback']
        submission_id = options['submission_id']

        try:
            success = send_grading_message_sync(
                chat_id=chat_id,
                student_name=student_name,
                student_id=student_id,
                course_id=course_id,
                assignment_id=assignment_id,
                student_nid=student_nid,
                similarity_score=similarity_score,
                grade=grade,
                feedback=feedback,
                submission_id=submission_id
            )
            
            if success:
                self.stdout.write(
                    self.style.SUCCESS(f'Mock grading message sent successfully to chat ID: {chat_id}')
                )
                self.stdout.write(
                    self.style.SUCCESS(f'Student: {student_name} ({student_id})')
                )
                self.stdout.write(
                    self.style.SUCCESS(f'Grade: {grade} | Similarity: {similarity_score}')
                )
            else:
                self.stdout.write(
                    self.style.ERROR('Failed to send message - check logs for details')
                )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Failed to send message: {str(e)}')
            )