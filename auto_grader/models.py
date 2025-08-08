

from django.db import models
from datetime import datetime
from enum import Enum


# Create your models here.

class SubmissionStatus(models.TextChoices):
    NEW = 'new', 'New'
    GRADED = 'graded', 'Graded'
    VERIFICATION_SENT = 'verification_sent', 'Verification Sent'
    GRADE_POSTED = 'grade_posted', 'Grade Posted'

class User(models.Model):
    user_id = models.IntegerField()

    username = models.CharField(max_length=100, null=True, blank=True)
    first_name = models.CharField(max_length=100, null=True, blank=True)
    last_name = models.CharField(max_length=100, null=True, blank=True)

    def __str__(self):
        return self.username + " " + str(self.user_id)

class Platform(models.Model):
    name = models.CharField(max_length=100, unique=True)
    api_url = models.URLField()
    api_key = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return self.name

class Assignment(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    platform = models.ForeignKey(Platform, on_delete=models.SET_NULL, null=True, blank=True)
    course_id = models.IntegerField()
    assignment_id = models.IntegerField()
    last_retrieved = models.DateTimeField(default=datetime(2000, 1, 1))
    description = models.TextField(null=True, blank=True)
    rubric = models.TextField(null=True, blank=True)

    def __str__(self):
        return str(self.assignment_id)

class RubricGrade(models.Model):
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name='rubric_grades')
    grade_number = models.IntegerField()
    short_description = models.CharField(max_length=200)
    detailed_description = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['grade_number']
        unique_together = ['assignment', 'grade_number']
    
    def __str__(self):
        return f"{self.assignment} - {self.grade_number}: {self.short_description}"

class Submission(models.Model):
    assignment = models.ForeignKey(Assignment, on_delete=models.SET_NULL, null=True, blank=True)
    student_id = models.CharField(max_length=100, null=True, blank=True)
    student_name = models.CharField(max_length=100)
    student_uid = models.CharField(max_length=100, null=True, blank=True)
    student_nid = models.IntegerField(null=True, blank=True)
    submission_time = models.DateTimeField(default=datetime(2000, 1, 1))
    preview_url = models.URLField(null=True, blank=True)
    similarity_score = models.FloatField(null=True, blank=True)
    grade = models.CharField(max_length=100, null=True, blank=True)
    content = models.TextField()
    feedback = models.TextField(blank=True, default='')
    status = models.CharField(max_length=20, choices=SubmissionStatus.choices, default=SubmissionStatus.NEW)

    def __str__(self):
        return self.assignment.__str__() + " " + self.student_name
