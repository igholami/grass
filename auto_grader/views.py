from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.admin.views.decorators import staff_member_required
from .models import Platform
from .canvas import CanvasGrader

@staff_member_required
def get_courses_for_platform(request):
    """AJAX endpoint to get courses for a selected platform"""
    import logging
    logger = logging.getLogger(__name__)
    
    platform_id = request.GET.get('platform_id')
    logger.info(f"Received request for platform_id: {platform_id}")
    
    if not platform_id:
        return JsonResponse({'courses': [], 'debug': 'No platform_id provided'})
    
    try:
        platform = Platform.objects.get(id=platform_id)
        logger.info(f"Found platform: {platform.name}")
        
        if platform.api_key and platform.api_url:
            grader = CanvasGrader(platform.api_url, platform.api_key)
            courses = grader.get_courses()
            logger.info(f"Retrieved {len(courses)} courses")
            return JsonResponse({'courses': courses, 'platform_name': platform.name})
        else:
            return JsonResponse({'courses': [], 'debug': 'Platform missing API key or URL'})
    except Platform.DoesNotExist:
        return JsonResponse({'courses': [], 'error': 'Platform not found'})
    except Exception as e:
        logger.error(f"Error fetching courses: {str(e)}")
        return JsonResponse({'courses': [], 'error': str(e)})

@staff_member_required
def get_assignments_for_course(request):
    """AJAX endpoint to get assignments for a selected course"""
    platform_id = request.GET.get('platform_id')
    course_id = request.GET.get('course_id')
    
    if not platform_id or not course_id:
        return JsonResponse({'assignments': []})
    
    try:
        platform = Platform.objects.get(id=platform_id)
        if platform.api_key and platform.api_url:
            grader = CanvasGrader(platform.api_url, platform.api_key)
            assignments = grader.get_assignments_for_course(course_id)
            return JsonResponse({'assignments': assignments})
        else:
            return JsonResponse({'assignments': []})
    except Platform.DoesNotExist:
        return JsonResponse({'assignments': []})
    except Exception as e:
        return JsonResponse({'assignments': [], 'error': str(e)})
