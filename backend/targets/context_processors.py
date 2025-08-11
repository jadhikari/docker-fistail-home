from django.utils import timezone
from .models import Target, RentalContract


def current_target_context(request):
    """
    Context processor to add current target information to all templates
    """
    context = {
        'current_target': None,
        'has_current_target': False,
        'current_target_progress': 0,
        'current_target_achieved': 0
    }
    
    # Only add target info for authenticated non-superusers
    if request.user.is_authenticated and not request.user.is_superuser:
        today = timezone.now().date()
        
        try:
            current_target = Target.objects.select_related('assigned_by').get(
                user=request.user,
                target_month=today.month,
                target_year=today.year
            )
            
            # Calculate current month achievements (rental contracts created by this user)
            current_month_achievements = RentalContract.objects.filter(
                created_by=request.user,
                created_at__year=today.year,
                created_at__month=today.month
            )
            
            # Calculate current month achievement total
            current_month_achievement_total = sum(
                achievement.agent_fee + achievement.ad_fee for achievement in current_month_achievements
            )
            
            # Calculate progress percentage
            if current_target.target_amount > 0:
                progress_percentage = (current_month_achievement_total / current_target.target_amount) * 100
            else:
                progress_percentage = 0
            
            context['current_target'] = current_target
            context['has_current_target'] = True
            context['current_target_progress'] = round(progress_percentage, 1)
            context['current_target_achieved'] = current_month_achievement_total
            
        except Target.DoesNotExist:
            pass
    
    return context