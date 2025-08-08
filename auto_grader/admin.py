from django.contrib import admin
from django.http import HttpResponse
from django.urls import path
from django.shortcuts import render
from django.utils.html import format_html
from django.db.models import Count
from django import forms
from .models import Assignment, Submission, User, Platform, RubricGrade, SubmissionStatus

class AssignmentAdminForm(forms.ModelForm):
    class Meta:
        model = Assignment
        fields = '__all__'
    
    class Media:
        js = ('admin/js/dynamic_course_selection.js',)

class RubricGradeInline(admin.TabularInline):
    model = RubricGrade
    extra = 1
    fields = ['grade_number', 'short_description', 'detailed_description']
    ordering = ['grade_number']

class RubricGradeAdmin(admin.ModelAdmin):
    list_display = ['assignment', 'grade_number', 'short_description', 'grade_preview', 'created_at']
    list_filter = ['assignment', 'grade_number', 'created_at']
    search_fields = ['short_description', 'detailed_description', 'assignment__assignment_id']
    ordering = ['assignment', 'grade_number']
    actions = ['duplicate_to_assignments']
    
    def grade_preview(self, obj):
        preview = obj.detailed_description[:50] if obj.detailed_description else 'No details'
        return format_html('<span title="{}">{}</span>', obj.detailed_description or '', preview)
    grade_preview.short_description = 'Details Preview'
    
    def duplicate_to_assignments(self, request, queryset):
        # This would allow copying rubric grades to other assignments
        self.message_user(request, f'Duplication feature for {queryset.count()} rubric grades - implement as needed.')
    duplicate_to_assignments.short_description = 'Duplicate to other assignments'

class AssignmentAdmin(admin.ModelAdmin):
    form = AssignmentAdminForm
    list_display = ['assignment_id', 'course_id', 'platform', 'user', 'last_retrieved', 'submission_stats', 'rubric_grade_count', 'has_rubric']
    list_filter = ['platform', 'user', 'last_retrieved']
    search_fields = ['assignment_id', 'course_id', 'description']
    readonly_fields = ['last_retrieved']
    inlines = [RubricGradeInline]
    actions = ['sync_submissions', 'reset_last_retrieved']
    
    def submission_stats(self, obj):
        total = obj.submission_set.count()
        new = obj.submission_set.filter(status=SubmissionStatus.NEW).count()
        graded = obj.submission_set.filter(status=SubmissionStatus.GRADED).count()
        posted = obj.submission_set.filter(status=SubmissionStatus.GRADE_POSTED).count()
        return format_html(
            'Total: {} | <span style="color: blue;">New: {}</span> | <span style="color: green;">Graded: {}</span> | <span style="color: purple;">Posted: {}</span>',
            total, new, graded, posted
        )
    submission_stats.short_description = 'Submission Stats'
    
    def rubric_grade_count(self, obj):
        count = obj.rubric_grades.count()
        if count > 0:
            return format_html('<span style="color: green; font-weight: bold;">{}</span>', count)
        return format_html('<span style="color: red;">0</span>')
    rubric_grade_count.short_description = 'Rubric Grades'
    
    def has_rubric(self, obj):
        return obj.rubric_grades.exists()
    has_rubric.boolean = True
    has_rubric.short_description = 'Has Rubric'
    
    def sync_submissions(self, request, queryset):
        # This would trigger a sync for selected assignments
        count = queryset.count()
        self.message_user(request, f'Sync requested for {count} assignments. Check logs for progress.')
    sync_submissions.short_description = 'Sync submissions from platform'
    
    def reset_last_retrieved(self, request, queryset):
        from datetime import datetime
        updated = queryset.update(last_retrieved=datetime(2000, 1, 1))
        self.message_user(request, f'{updated} assignments reset - will retrieve all submissions on next sync.')
    reset_last_retrieved.short_description = 'Reset last_retrieved timestamp'

class SubmissionAdmin(admin.ModelAdmin):
    list_display = ['student_name', 'assignment', 'grade', 'status', 'submission_time', 'similarity_score', 'status_display']
    list_filter = ['assignment', 'status', 'submission_time', 'grade']
    search_fields = ['student_name', 'student_id', 'student_uid', 'content']
    readonly_fields = ['submission_time']
    actions = ['reset_to_new', 'mark_as_graded']
    
    def status_display(self, obj):
        status_colors = {
            SubmissionStatus.NEW: 'blue',
            SubmissionStatus.GRADED: 'green', 
            SubmissionStatus.VERIFICATION_SENT: 'orange',
            SubmissionStatus.GRADE_POSTED: 'purple'
        }
        color = status_colors.get(obj.status, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.get_status_display()
        )
    status_display.short_description = 'Status'
    
    def reset_to_new(self, request, queryset):
        updated = queryset.update(status=SubmissionStatus.NEW, grade=None, feedback='')
        self.message_user(request, f'{updated} submissions reset to NEW status for re-grading.')
    reset_to_new.short_description = 'Reset selected submissions to NEW status'
    
    def mark_as_graded(self, request, queryset):
        updated = queryset.update(status=SubmissionStatus.GRADED)
        self.message_user(request, f'{updated} submissions marked as GRADED.')
    mark_as_graded.short_description = 'Mark selected submissions as GRADED'

class UserAdmin(admin.ModelAdmin):
    list_display = ['username', 'first_name', 'last_name', 'user_id', 'assignment_count']
    search_fields = ['username', 'first_name', 'last_name', 'user_id']
    
    def assignment_count(self, obj):
        return obj.assignment_set.count()
    assignment_count.short_description = 'Assignments'

class PlatformAdmin(admin.ModelAdmin):
    list_display = ['name', 'api_url', 'has_api_key', 'assignment_count', 'submission_count', 'connection_status']
    search_fields = ['name', 'api_url']
    actions = ['test_connection']
    
    def has_api_key(self, obj):
        return bool(obj.api_key)
    has_api_key.boolean = True
    has_api_key.short_description = 'API Key Set'
    
    def assignment_count(self, obj):
        return obj.assignment_set.count()
    assignment_count.short_description = 'Assignments'
    
    def submission_count(self, obj):
        return sum(assignment.submission_set.count() for assignment in obj.assignment_set.all())
    submission_count.short_description = 'Total Submissions'
    
    def connection_status(self, obj):
        if obj.api_key:
            return format_html('<span style="color: green;">✓ Ready</span>')
        return format_html('<span style="color: red;">✗ No API Key</span>')
    connection_status.short_description = 'Status'
    
    def test_connection(self, request, queryset):
        # This would test the API connection
        for platform in queryset:
            if platform.name == 'Canvas' and platform.api_key:
                # Test Canvas connection here
                pass
        self.message_user(request, 'Connection test initiated for selected platforms.')
    test_connection.short_description = 'Test API connection'

class AutoGradingAdminSite(admin.AdminSite):
    site_header = 'AutoGrading Admin'
    site_title = 'AutoGrading Admin Portal'
    index_title = 'Welcome to AutoGrading Administration'
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('dashboard/', self.admin_dashboard, name='admin_dashboard'),
        ]
        return custom_urls + urls
    
    def admin_dashboard(self, request):
        from django.db.models import Q
        
        # Status-based submission counts
        submission_stats = {
            'new': Submission.objects.filter(status=SubmissionStatus.NEW).count(),
            'graded': Submission.objects.filter(status=SubmissionStatus.GRADED).count(),
            'verification_sent': Submission.objects.filter(status=SubmissionStatus.VERIFICATION_SENT).count(),
            'grade_posted': Submission.objects.filter(status=SubmissionStatus.GRADE_POSTED).count(),
        }
        
        # Assignment stats
        assignments_with_rubric = Assignment.objects.filter(rubric_grades__isnull=False).distinct().count()
        assignments_without_rubric = Assignment.objects.filter(rubric_grades__isnull=True).count()
        
        context = {
            'title': 'AutoGrading Dashboard',
            'total_assignments': Assignment.objects.count(),
            'total_submissions': Submission.objects.count(),
            'total_users': User.objects.count(),
            'total_platforms': Platform.objects.count(),
            'submission_stats': submission_stats,
            'assignments_with_rubric': assignments_with_rubric,
            'assignments_without_rubric': assignments_without_rubric,
            'recent_submissions': Submission.objects.select_related('assignment', 'assignment__platform').order_by('-submission_time')[:10],
            'recent_grades': Submission.objects.filter(status=SubmissionStatus.GRADE_POSTED).select_related('assignment').order_by('-submission_time')[:5],
        }
        return render(request, 'admin/dashboard.html', context)

admin_site = AutoGradingAdminSite(name='autograding_admin')

admin.site.register(Assignment, AssignmentAdmin)
admin.site.register(Submission, SubmissionAdmin)
admin.site.register(User, UserAdmin)
admin.site.register(Platform, PlatformAdmin)
admin.site.register(RubricGrade, RubricGradeAdmin)

admin_site.register(Assignment, AssignmentAdmin)
admin_site.register(Submission, SubmissionAdmin)
admin_site.register(User, UserAdmin)
admin_site.register(Platform, PlatformAdmin)
admin_site.register(RubricGrade, RubricGradeAdmin)
