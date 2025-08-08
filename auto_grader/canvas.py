from canvasapi import Canvas
from django.conf import settings

from auto_grader.models import Assignment, User
from auto_grader.utils import clean_html_text


class CanvasGrader:
    def __init__(self, api_url, api_key):
        self.canvas = Canvas(api_url, api_key)
    
    def get_courses(self):
        """Get all courses available in Canvas"""
        try:
            courses = self.canvas.get_courses()
            return [(course.id, f"{course.name} (ID: {course.id})") for course in courses if hasattr(course, 'name')]
        except Exception as e:
            return []
    
    def get_assignments_for_course(self, course_id):
        """Get all assignments for a specific course"""
        try:
            course = self.canvas.get_course(course_id)
            assignments = course.get_assignments()
            return [(assignment.id, f"{assignment.name} (ID: {assignment.id})") for assignment in assignments if hasattr(assignment, 'name')]
        except Exception as e:
            return []

    def retrieve_all_new_submissions(self):
        users = User.objects.all()
        for user in users:
            for submission in self.retrieve_all_new_submissions_for_user(user):
                yield submission

    def send_grade(self, course_id, assignment_id, student_nid, grade, feedback):
        """
        Send numerical grade to Canvas based on rubric.
        
        Args:
            course_id: Canvas course ID
            assignment_id: Canvas assignment ID  
            student_nid: Canvas student numeric ID
            grade: Numerical grade value from rubric
            feedback: Feedback text to post as comment
        """
        canvas_course = self.canvas.get_course(course_id)
        canvas_assignment = canvas_course.get_assignment(assignment_id)
        canvas_student = canvas_course.get_user(student_nid)
        canvas_submission = canvas_assignment.get_submission(canvas_student.id)
        
        # Post the numerical grade directly
        canvas_submission.edit(submission={'posted_grade': int(grade)})
        
        # Add feedback comment if provided
        if feedback:
            canvas_submission.edit(comment={'text_comment': feedback})

    def retrieve_all_new_submissions_for_user(self, user):
        assignments = Assignment.objects.filter(user=user)
        for assignment in assignments:
            for submission in self.retrieve_all_new_submissions_for_assignment(assignment):
                yield submission

    def retrieve_all_new_submissions_for_assignment(self, assignment):
        canvas_course = self.canvas.get_course(assignment.course_id)
        canvas_assignment = canvas_course.get_assignment(assignment.assignment_id)
        submission_generator = self.retrieve_remaining_submissions(
            canvas_course,
            [assignment.assignment_id],
            assignment.last_retrieved
        )
        for submission in submission_generator:
            yield self.gradable_submission(canvas_course, canvas_assignment, submission)

    def retrieve_remaining_submissions(self, canvas_course, assignment_ids, time):
        """
        Retrieve submissions for a given assignment since specified time
        :param assignment_ids:
        :param course_id:
        :param time: only get submissions after this time
        :return:
        """
        submissions = canvas_course.get_multiple_submissions(
            student_ids='all',
            assignment_ids=assignment_ids,
            workflow_state='submitted',
            submitted_since=time
        )
        for submission in submissions:
            yield submission

    def gradable_submission(self, canvas_course, canvas_assignment, canvas_submission):
        student = canvas_course.get_user(canvas_submission.user_id)
        return GradableSubmission(canvas_assignment, canvas_submission, student)


class GradableSubmission:
    def __init__(self, assignment, submission, student):
        self.assignment = assignment
        self.assignment_id = assignment.id
        self.submission = submission
        self.student = student
        self.submission_body = clean_html_text(submission.body)
        self.submission_time = submission.submitted_at
        self.assignment_description = clean_html_text(assignment.description)
        self.student_name = student.name
        self.student_id = student.login_id
        self.student_uid = student.sis_user_id
        self.preview_url = submission.preview_url
        self.student_nid = submission.user_id
        try:
            self.similarity_score = list(submission.turnitin_data.values())[0]['similarity_score']
        except (KeyError, AttributeError):
            self.similarity_score = None
