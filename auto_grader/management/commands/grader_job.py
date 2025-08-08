import asyncio
import time
from datetime import timedelta

from django.conf import settings
from django.core.management import BaseCommand
from telegram import Bot, InlineKeyboardMarkup, InlineKeyboardButton

from auto_grader.canvas import CanvasGrader
from auto_grader.gpt import ChatGPTAutomation
from auto_grader.models import User, Assignment, Submission, Platform, RubricGrade, SubmissionStatus
from auto_grader.utils import send_grading_message_sync, RubricGradeButton

grade_template = """Grade the following solution for the given problem using the rubric provided.

Problem: {problem}

Rubric: {rubric}

Solution: {solution}

Instructions:
- You must assign one of the EXACT grade options listed in the rubric above
- Use only the grade identifiers/numbers specified in the rubric (e.g., if rubric shows "1: E - Excellent", use "1")
- For higher grades: provide minimal or no feedback
- For lower grades: provide brief technical feedback (1-2 sentences max) on how to improve
- Use simple, formal language
- Focus only on technical aspects

OUTPUT FORMAT (single line):
<GRADE_FROM_RUBRIC>: <FEEDBACK>

Important: The GRADE must exactly match one of the grade numbers/identifiers from the rubric provided above.
"""


class Command(BaseCommand):
    help = 'Run the grader job'

    def process_submission(self, submission, gpt):
        """Process a single submission"""
        print("Processing submission for student: {} - assignment: {}".format(submission.student_name, submission.assignment_id))
        try:
            assignment = Assignment.objects.get(assignment_id=submission.assignment_id)
            
            # Update assignment description if not set
            if not assignment.description:
                assignment.description = submission.assignment_description
                assignment.save()
            
            # Check if submission already exists
            existing_submission = Submission.objects.filter(
                assignment=assignment,
                student_id=submission.student_id,
                submission_time=submission.submission_time
            ).first()
            
            if existing_submission:
                print(f"Submission already exists with status: {existing_submission.status}")
                return
            
            # Create new submission with 'new' status
            s = Submission.objects.create(
                assignment=assignment,
                student_id=submission.student_id,
                student_name=submission.student_name,
                student_uid=submission.student_uid,
                student_nid=submission.student_nid,
                submission_time=submission.submission_time,
                preview_url=submission.preview_url,
                similarity_score=submission.similarity_score,
                content=submission.submission_body,
                feedback="",
                status=SubmissionStatus.NEW
            )
            print(f"Created new submission with ID: {s.id}")
            
        except Assignment.DoesNotExist:
            print(f"Assignment {submission.assignment_id} not found in database")
        except Exception as e:
            print(f"Error processing submission: {e}")

    def process_ungraded_submissions(self, gpt):
        """Process all submissions that are new status"""
        ungraded_submissions = Submission.objects.filter(status=SubmissionStatus.NEW)
        print(f"Found {ungraded_submissions.count()} ungraded submissions to process")
        
        for s in ungraded_submissions:
            try:
                print(f"Grading submission ID: {s.id} for student: {s.student_name}")
                assignment = s.assignment

                # Build rubric text from structured rubric if available
                rubric_text = assignment.rubric or ""
                rubric_grades = RubricGrade.objects.filter(assignment=assignment).order_by('grade_number')
                if rubric_grades.exists():
                    rubric_parts = [f"{rg.grade_number}: {rg.short_description}" for rg in rubric_grades]
                    rubric_text = "\n".join(rubric_parts)
                
                # Grade the submission
                gpt.send_prompt_to_chatgpt(
                    grade_template.format(
                        problem=assignment.description,
                        solution=s.content,
                        rubric=rubric_text
                    )
                )
                response = gpt.return_last_response()
                gpt.open_chatgpt()
                
                # Parse response
                if ":" in response:
                    grade, feedback = response.split(":", 1)
                    s.grade = grade.strip()
                    s.feedback = feedback.strip()
                    s.status = SubmissionStatus.GRADED
                else:
                    s.status = SubmissionStatus.NEW  # Reset to 'new' for retry
                
                s.save()
                print(f"Graded submission ID: {s.id} with grade: {s.grade}")
                
            except Exception as e:
                print(f"Error grading submission ID {s.id}: {e}")
                # In case of error, reset status to 'new' for retry
                s.status = SubmissionStatus.NEW
                s.save()

    def send_grading_notifications(self):
        """Phase 3: Send notifications for graded submissions"""
        graded_submissions = Submission.objects.filter(status=SubmissionStatus.GRADED)
        print(f"Found {graded_submissions.count()} graded submissions to notify")
        
        for s in graded_submissions:
            try:
                assignment = s.assignment
                print(f"Sending notification for submission ID: {s.id}")
                
                # Send notification if user exists
                if assignment.user:
                    # Get rubric grades for the assignment
                    rubric_grades = [
                        RubricGradeButton(
                            grade_number=button.grade_number,
                            short_description=button.short_description,
                        )
                        for button in RubricGrade.objects.filter(assignment=assignment).order_by('grade_number')
                    ]
                    
                    send_grading_message_sync(
                        chat_id=assignment.user.user_id,
                        student_name=s.student_name,
                        student_id=s.student_id,
                        course_id=assignment.course_id,
                        assignment_id=assignment.assignment_id,
                        student_nid=s.student_nid,
                        similarity_score=s.similarity_score,
                        grade=s.grade,
                        feedback=s.feedback,
                        submission_id=s.id,
                        rubric_grades=rubric_grades,
                        canvas_url=assignment.platform.api_url
                    )
                    # Change status to 'verification_sent' after telegram message is sent
                    s.status = SubmissionStatus.VERIFICATION_SENT
                    s.save()
                    print(f"Notification sent for submission ID: {s.id}")
                else:
                    print(f"No user found for assignment {assignment.assignment_id}, skipping notification")
                    
            except Exception as e:
                print(f"Error sending notification for submission ID {s.id}: {e}")
                # Keep status as 'graded' for retry in next cycle

    def process_platform_submissions(self, platform, gpt):
        """Process submissions for a specific platform"""
        print(f"Processing submissions for platform: {platform.name}")
        if platform.name == 'Canvas':
            try:
                canvas_grader = CanvasGrader(platform.api_url, platform.api_key)
                for submission in canvas_grader.retrieve_all_new_submissions():
                    self.process_submission(submission, gpt)
            except Exception as e:
                print(f"Error processing Canvas platform: {e}")
        # Add other platforms here as needed

    def update_assignment_timestamps(self):
        """Update last_retrieved timestamps for all assignments"""
        for assignment in Assignment.objects.all():
            submissions = Submission.objects.filter(assignment=assignment)
            if submissions.exists():
                latest_submission_time = max(sub.submission_time for sub in submissions)
                if latest_submission_time > assignment.last_retrieved:
                    assignment.last_retrieved = latest_submission_time + timedelta(seconds=1)
                    assignment.save()

    def handle(self, *args, **options):
        gpt = ChatGPTAutomation(settings.CHROME_PATH, settings.CHROME_DRIVER_PATH)
        gpt.open_chatgpt()
        
        while True:
            try:
                # Phase 1: Retrieve new submissions from platforms
                print("=== Phase 1: Retrieving new submissions ===")
                platforms = Platform.objects.all()
                for platform in platforms:
                    self.process_platform_submissions(platform, gpt)
                # Update timestamps
                self.update_assignment_timestamps()

                # Phase 2: Process all ungraded submissions
                print("=== Phase 2: Processing ungraded submissions ===")
                self.process_ungraded_submissions(gpt)
                
                # Phase 3: Send grading notifications
                print("=== Phase 3: Sending grading notifications ===")
                self.send_grading_notifications()
                

            except Exception as e:
                print(f"Error in grader job main loop: {e}")
            
            time.sleep(3600)


