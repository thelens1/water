# water_app/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.core.paginator import Paginator
from django.db.models import Q, Count, Avg, Sum, F
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.contrib.auth.models import User
from django.contrib.gis.geos import Point, GEOSGeometry, Polygon
from django.core.serializers import serialize
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
import json
import csv
import os
import math
import random
import tempfile
import zipfile
from datetime import datetime, timedelta
import numpy as np
import traceback

from .forms import (
    LoginForm, RegisterForm, BoundaryUploadForm, WaterPointForm,
    ShapefileUploadForm, ProfileUpdateForm, PasswordChangeForm,
    WaterPointFilterForm, DataExportForm, PredictionForm
)
from .models import (
    SubCounty, BoundaryFile, WaterPoint, PredictionBatch, UserActivity,
    County, Ward, ShapefileUpload, DataImportBatch, ModelMetadata,
    SystemSettings, Notification
)

# Import the ensemble ML service
from .ml_service_ensemble import ml_service

# ==================== AUTHENTICATION VIEWS ====================

def login_view(request):
    """Custom login view with beautiful UI"""
    if request.user.is_authenticated:
        return redirect('water_app:map_view')
    
    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                
                # Log activity
                UserActivity.objects.create(
                    user=user,
                    activity_type='login',
                    description='User logged in',
                    ip_address=request.META.get('REMOTE_ADDR'),
                    user_agent=request.META.get('HTTP_USER_AGENT', '')
                )
                
                messages.success(request, f'Welcome back, {user.username}!')
                
                # Check if there's a next parameter
                next_url = request.GET.get('next')
                if next_url:
                    return redirect(next_url)
                return redirect('water_app:map_view')
        else:
            messages.error(request, 'Invalid username or password.')
    else:
        form = LoginForm()
    
    return render(request, 'login.html', {'form': form})

def register_view(request):
    """User registration view"""
    if request.user.is_authenticated:
        return redirect('water_app:map_view')
    
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            username = form.cleaned_data.get('username')
            raw_password = form.cleaned_data.get('password1')
            user = authenticate(username=username, password=raw_password)
            login(request, user)
            
            # Log activity
            UserActivity.objects.create(
                user=user,
                activity_type='register',
                description='New user registered',
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            
            messages.success(request, f'Account created successfully! Welcome, {username}!')
            return redirect('water_app:map_view')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = RegisterForm()
    
    return render(request, 'register.html', {'form': form})

def logout_view(request):
    """Custom logout view"""
    if request.user.is_authenticated:
        UserActivity.objects.create(
            user=request.user,
            activity_type='logout',
            description='User logged out',
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        logout(request)
        messages.info(request, 'You have been logged out successfully.')
    return redirect('water_app:login')

# ==================== MAIN VIEWS ====================

@login_required
def map_view(request):
    """Main map view with enhanced features"""
    # Get statistics
    stats = WaterPoint.get_statistics()
    
    # Get subcounty and ward counts
    subcounty_count = SubCounty.objects.count()
    ward_count = Ward.objects.count()
    
    # Get county bounds for initial view
    county = County.objects.filter(county__icontains='turkana').first()
    county_bounds = None
    if county and county.geom:
        bbox = county.geom.extent  # (xmin, ymin, xmax, ymax)
        county_bounds = {
            'min_lng': bbox[0],
            'min_lat': bbox[1],
            'max_lng': bbox[2],
            'max_lat': bbox[3]
        }
    
    # Get recent notifications
    notifications = Notification.objects.filter(
        Q(user=request.user) | Q(is_global=True),
        Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())
    ).order_by('-created_at')[:5]
    
    context = {
        'subcounties': SubCounty.objects.all().order_by('subcounty'),
        'recent_water_points': WaterPoint.objects.filter(created_by=request.user).order_by('-created_at')[:5],
        'total_points': stats['total'],
        'operational_count': stats['operational'],
        'non_operational_count': stats['non_operational'],
        'unknown_count': stats['unknown'],
        'subcounty_count': subcounty_count,
        'ward_count': ward_count,
        'success_rate': stats['operational_percent'],
        'avg_depth': stats['avg_depth'],
        'avg_yield': stats['avg_yield'],
        'county_bounds': json.dumps(county_bounds) if county_bounds else 'null',
        'notifications': notifications,
        'unread_notifications': Notification.objects.filter(
            user=request.user, is_read=False
        ).count(),
    }
    return render(request, 'map.html', context)

@login_required
def dashboard(request):
    """Dashboard with statistics and charts"""
    # Basic statistics using model method
    stats = WaterPoint.get_statistics()
    
    # User statistics
    user_points = WaterPoint.objects.filter(created_by=request.user).count()
    user_predictions = PredictionBatch.objects.filter(created_by=request.user).count()
    user_uploads = ShapefileUpload.objects.filter(uploaded_by=request.user).count()
    
    # Status distribution for chart
    status_data = {
        'labels': ['Operational', 'Non-Operational', 'Unknown'],
        'values': [stats['operational'], stats['non_operational'], stats['unknown']],
        'colors': ['#00cc44', '#ff4444', '#ffaa00']
    }
    
    # Recent activities
    recent_activities = UserActivity.objects.filter(user=request.user)[:15]
    
    # Top sub-counties by water points (for main table)
    top_subcounties = SubCounty.objects.annotate(
        point_count=Count('waterpoint'),
        operational_count=Count('waterpoint', filter=Q(waterpoint__status='operational'))
    ).order_by('-point_count')[:10]
    
    # Top sub-counties by success rate
    all_subcounties = []
    for sc in SubCounty.objects.all():
        sc_stats = WaterPoint.get_statistics(sub_county=sc)
        if sc_stats['total'] > 0:
            all_subcounties.append({
                'subcounty': sc.subcounty,
                'total': sc_stats['total'],
                'operational': sc_stats['operational'],
                'success_rate': sc_stats['operational_percent']
            })
    
    top_subcounties_by_success = sorted(all_subcounties, key=lambda x: x['success_rate'], reverse=True)[:10]
    top_subcounties_by_count = sorted(all_subcounties, key=lambda x: x['total'], reverse=True)[:10]
    
    # Add percentage to count-based list
    total_points_all = sum([sc['total'] for sc in top_subcounties_by_count])
    for sc in top_subcounties_by_count:
        sc['percentage'] = round((sc['total'] / total_points_all * 100), 1) if total_points_all > 0 else 0
    
    # Monthly trends (last 6 months)
    from django.db.models.functions import TruncMonth
    monthly_trends = WaterPoint.objects.filter(
        created_at__gte=timezone.now() - timedelta(days=180)
    ).annotate(
        month=TruncMonth('created_at')
    ).values('month').annotate(
        count=Count('id'),
        operational_count=Count('id', filter=Q(status='operational'))
    ).order_by('month')
    
    months = []
    monthly_counts = []
    operational_counts = []
    
    for trend in monthly_trends:
        if trend['month']:
            months.append(trend['month'].strftime('%b %Y'))
            monthly_counts.append(trend['count'])
            operational_counts.append(trend['operational_count'])
    
    # Water quality statistics
    depth_points = WaterPoint.objects.exclude(well_depth__isnull=True).exclude(well_depth='')
    depth_values = [wp.depth_m_value for wp in depth_points if wp.depth_m_value is not None]
    avg_depth = sum(depth_values) / len(depth_values) if depth_values else None
    
    yield_values = WaterPoint.objects.exclude(yield_field__isnull=True).values_list('yield_field', flat=True)
    yield_values = [y for y in yield_values if y is not None]
    avg_yield = sum(yield_values) / len(yield_values) if yield_values else None
    
    # Depth and yield by status
    operational_points = WaterPoint.objects.filter(status='operational')
    non_operational_points = WaterPoint.objects.filter(status='non_operational')
    unknown_points = WaterPoint.objects.filter(status='unknown')
    
    def get_avg_depth_for_queryset(queryset):
        depths = []
        for wp in queryset.exclude(well_depth__isnull=True).exclude(well_depth=''):
            depth_val = wp.depth_m_value
            if depth_val is not None:
                depths.append(depth_val)
        return sum(depths) / len(depths) if depths else 0
    
    def get_avg_yield_for_queryset(queryset):
        yields = queryset.exclude(yield_field__isnull=True).values_list('yield_field', flat=True)
        yields = [y for y in yields if y is not None]
        return sum(yields) / len(yields) if yields else 0
    
    depth_operational = get_avg_depth_for_queryset(operational_points)
    depth_non_operational = get_avg_depth_for_queryset(non_operational_points)
    depth_unknown = get_avg_depth_for_queryset(unknown_points)
    
    yield_operational = get_avg_yield_for_queryset(operational_points)
    yield_non_operational = get_avg_yield_for_queryset(non_operational_points)
    yield_unknown = get_avg_yield_for_queryset(unknown_points)
    
    # Classification keyword analysis
    operational_keywords = [
        "operational", "y", "pump installed", "hand pump", 
        "installed", "functional", "working", "yes", "good",
        "active", "in use", "functioning", "ok", "works"
    ]
    
    non_operational_keywords = [
        "dry", "dry hole", "dry well", "blocked", "salty", 
        "abandoned", "no water", "insufficient", "broken", 
        "non functional", "not working", "damaged", "failed",
        "not operational", "non-operational", "nonfunctional",
        "needs repair", "broken down", "not in use", "closed"
    ]
    
    # Count keyword occurrences
    operational_keyword_counts = {}
    non_operational_keyword_counts = {}
    
    all_points = WaterPoint.objects.exclude(operation_field__isnull=True).exclude(operation_field='')
    
    for wp in all_points:
        field_value = str(wp.operation_field).lower()
        for kw in operational_keywords:
            if kw in field_value:
                operational_keyword_counts[kw] = operational_keyword_counts.get(kw, 0) + 1
        for kw in non_operational_keywords:
            if kw in field_value:
                non_operational_keyword_counts[kw] = non_operational_keyword_counts.get(kw, 0) + 1
    
    # Get top keywords
    top_operational_keywords = dict(sorted(operational_keyword_counts.items(), key=lambda x: x[1], reverse=True)[:5])
    top_non_operational_keywords = dict(sorted(non_operational_keyword_counts.items(), key=lambda x: x[1], reverse=True)[:5])
    
    # Critical points (non-operational with depth or yield data)
    critical_points = WaterPoint.objects.filter(
        status='non_operational'
    ).exclude(
        Q(well_depth__isnull=True) & Q(yield_field__isnull=True)
    ).order_by('-created_at')[:10]
    
    # Prediction statistics
    total_predictions = PredictionBatch.objects.count()
    successful_predictions = PredictionBatch.objects.filter(status='completed').count()
    
    # Additional calculated values
    operational_percent = stats['operational_percent']
    non_operational_percent = round((stats['non_operational'] / stats['total'] * 100), 1) if stats['total'] > 0 else 0
    
    # ML Model info
    model_ready = ml_service.is_ready()
    model_info = ml_service.get_model_info() if model_ready else None
    
    # Calculate some extra metrics for the dashboard
    new_points_this_month = WaterPoint.objects.filter(
        created_at__gte=timezone.now() - timedelta(days=30)
    ).count()
    
    prediction_accuracy = round(model_info.get('metrics', {}).get('accuracy', 0) * 100, 1) if model_info else None
    accuracy_improvement = round((prediction_accuracy - 50) if prediction_accuracy else 0, 1)
    
    depth_percent = min(100, round((avg_depth / 100 * 100) if avg_depth else 50, 1)) if avg_depth else 50
    yield_percent = min(100, round((avg_yield / 5 * 100) if avg_yield else 50, 1)) if avg_yield else 50
    
    # Classification summary
    operational_keywords_count = sum(operational_keyword_counts.values())
    non_operational_keywords_count = sum(non_operational_keyword_counts.values())
    classification_ratio = round((operational_keywords_count / (operational_keywords_count + non_operational_keywords_count) * 100), 1) if (operational_keywords_count + non_operational_keywords_count) > 0 else 0
    
    context = {
        'total_water_points': stats['total'],
        'operational': stats['operational'],
        'non_operational': stats['non_operational'],
        'unknown': stats['unknown'],
        'user_points': user_points,
        'user_predictions': user_predictions,
        'user_uploads': user_uploads,
        'status_data': json.dumps(status_data),
        'recent_activities': recent_activities,
        'top_subcounties': top_subcounties,
        'top_subcounties_by_success': top_subcounties_by_success,
        'top_subcounties_by_count': top_subcounties_by_count,
        'months': json.dumps(months),
        'monthly_counts': json.dumps(monthly_counts),
        'operational_counts': json.dumps(operational_counts),
        'operational_percent': operational_percent,
        'non_operational_percent': non_operational_percent,
        'avg_depth': f"{avg_depth:.1f} m" if avg_depth else 'N/A',
        'avg_yield': f"{avg_yield:.2f} L/s" if avg_yield else 'N/A',
        'depth_operational': round(depth_operational, 1),
        'depth_non_operational': round(depth_non_operational, 1),
        'depth_unknown': round(depth_unknown, 1),
        'yield_operational': round(yield_operational, 2),
        'yield_non_operational': round(yield_non_operational, 2),
        'yield_unknown': round(yield_unknown, 2),
        'total_predictions': total_predictions,
        'successful_predictions': successful_predictions,
        'model_ready': model_ready,
        'model_info': model_info,
        'current_date': timezone.now(),
        'new_points_this_month': new_points_this_month,
        'prediction_accuracy': prediction_accuracy,
        'accuracy_improvement': accuracy_improvement,
        'depth_percent': depth_percent,
        'yield_percent': yield_percent,
        'depth_vs_baseline': round((depth_percent - 50), 1) if depth_percent else 0,
        'operational_keywords_labels': json.dumps(list(top_operational_keywords.keys())),
        'operational_keywords_data': json.dumps(list(top_operational_keywords.values())),
        'non_operational_keywords_labels': json.dumps(list(top_non_operational_keywords.keys())),
        'non_operational_keywords_data': json.dumps(list(top_non_operational_keywords.values())),
        'operational_keywords_count': operational_keywords_count,
        'non_operational_keywords_count': non_operational_keywords_count,
        'classification_ratio': classification_ratio,
        'critical_points': critical_points,
    }
    
    return render(request, 'dashboard.html', context)

@login_required
def profile(request):
    """User profile view"""
    user = request.user
    
    if request.method == 'POST':
        # Determine which form was submitted
        if 'update_profile' in request.POST:
            form = ProfileUpdateForm(request.POST, instance=user)
            if form.is_valid():
                form.save()
                messages.success(request, 'Profile updated successfully!')
                return redirect('water_app:profile')
            else:
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, f'{field}: {error}')
        
        elif 'change_password' in request.POST:
            form = PasswordChangeForm(request.POST)
            if form.is_valid():
                if user.check_password(form.cleaned_data['current_password']):
                    user.set_password(form.cleaned_data['new_password'])
                    user.save()
                    messages.success(request, 'Password changed successfully. Please login again.')
                    return redirect('water_app:login')
                else:
                    messages.error(request, 'Current password is incorrect.')
            else:
                for error in form.non_field_errors():
                    messages.error(request, error)
    
    # User statistics
    points_added = WaterPoint.objects.filter(created_by=user).count()
    predictions_run = PredictionBatch.objects.filter(created_by=user).count()
    boundaries_uploaded = BoundaryFile.objects.filter(uploaded_by=user).count()
    shapefiles_uploaded = ShapefileUpload.objects.filter(uploaded_by=user).count()
    
    # Recent activity
    recent_activity = UserActivity.objects.filter(user=user)[:20]
    
    # User's water points
    user_water_points = WaterPoint.objects.filter(created_by=user).order_by('-created_at')[:10]
    
    # Prediction accuracy (if any)
    user_predictions = PredictionBatch.objects.filter(created_by=user, status='completed')
    total_predicted = sum(batch.total_points for batch in user_predictions)
    total_operational = sum(batch.operational_predicted for batch in user_predictions)
    
    # Get user's groups and permissions
    groups = user.groups.all()
    is_staff = user.is_staff
    is_superuser = user.is_superuser
    
    context = {
        'user': user,
        'points_added': points_added,
        'predictions_run': predictions_run,
        'boundaries_uploaded': boundaries_uploaded,
        'shapefiles_uploaded': shapefiles_uploaded,
        'recent_activity': recent_activity,
        'user_water_points': user_water_points,
        'total_predicted': total_predicted,
        'total_operational': total_operational,
        'join_date': user.date_joined.strftime('%B %d, %Y'),
        'last_login': user.last_login.strftime('%B %d, %Y %H:%M') if user.last_login else 'Never',
        'groups': groups,
        'is_staff': is_staff,
        'is_superuser': is_superuser,
    }
    
    return render(request, 'profile.html', context)

# ==================== WATER POINT MANAGEMENT ====================

@login_required
def add_water_point(request):
    """Add a new water point manually"""
    if request.method == 'POST':
        form = WaterPointForm(request.POST)
        if form.is_valid():
            point = form.save(commit=False)
            point.created_by = request.user
            
            # Classify status based on operation_field if not set
            if not point.status or point.status == 'unknown':
                point.status = point.classify_operational_from_operation_field()
            
            point.save()
            
            # Log activity
            UserActivity.objects.create(
                user=request.user,
                activity_type='add_point',
                description=f'Added water point: {point.name or point.locality}',
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                water_point=point
            )
            
            messages.success(request, 'Water point added successfully!')
            return redirect('water_app:map_view')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        initial = {}
        if 'lat' in request.GET and 'lng' in request.GET:
            initial['latitude'] = float(request.GET.get('lat'))
            initial['longitude'] = float(request.GET.get('lng'))
        form = WaterPointForm(initial=initial)
    
    context = {
        'form': form,
        'subcounties': SubCounty.objects.all().order_by('subcounty'),
    }
    return render(request, 'add_water_point.html', context)

@login_required
def water_point_detail(request, point_id):
    """View water point details"""
    point = get_object_or_404(WaterPoint, id=point_id)
    
    # Get nearby water points (within 5km)
    nearby_points = point.get_nearby_points_for_this(radius_km=5)
    
    # Get statistics for the subcounty
    subcounty_stats = None
    if point.sub_county:
        subcounty_stats = WaterPoint.get_statistics(sub_county=point.sub_county)
    
    # Get ML prediction if model is ready
    ml_prediction = None
    if ml_service.is_ready():
        ml_prediction = ml_service.predict(point)
    
    context = {
        'point': point,
        'nearby_points': nearby_points[:10],
        'nearby_count': nearby_points.count(),
        'can_edit': point.created_by == request.user or request.user.is_superuser,
        'subcounty_stats': subcounty_stats,
        'ml_prediction': ml_prediction,
        'model_ready': ml_service.is_ready(),
    }
    return render(request, 'water_point_detail.html', context)

@login_required
def edit_water_point(request, point_id):
    """Edit an existing water point"""
    point = get_object_or_404(WaterPoint, id=point_id)
    
    # Check permissions
    if point.created_by != request.user and not request.user.is_superuser:
        messages.error(request, 'You do not have permission to edit this water point.')
        return redirect('water_app:water_point_detail', point_id=point.id)
    
    if request.method == 'POST':
        form = WaterPointForm(request.POST, instance=point)
        if form.is_valid():
            updated_point = form.save(commit=False)
            
            # Re-classify status if needed
            if not updated_point.status or updated_point.status == 'unknown':
                updated_point.status = updated_point.classify_operational_from_operation_field()
            
            updated_point.save()
            
            # Log activity
            UserActivity.objects.create(
                user=request.user,
                activity_type='edit_point',
                description=f'Edited water point: {point.name or point.locality}',
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                water_point=point
            )
            
            messages.success(request, 'Water point updated successfully!')
            return redirect('water_app:water_point_detail', point_id=point.id)
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = WaterPointForm(instance=point)
    
    context = {
        'form': form,
        'point': point,
        'subcounties': SubCounty.objects.all().order_by('subcounty'),
    }
    return render(request, 'edit_water_point.html', context)

@login_required
def delete_water_point(request, point_id):
    """Delete a water point"""
    point = get_object_or_404(WaterPoint, id=point_id)
    
    # Check permissions
    if point.created_by != request.user and not request.user.is_superuser:
        messages.error(request, 'You do not have permission to delete this water point.')
        return redirect('water_app:water_point_detail', point_id=point.id)
    
    if request.method == 'POST':
        point_name = point.name or point.locality or 'Unnamed'
        point.delete()
        
        # Log activity
        UserActivity.objects.create(
            user=request.user,
            activity_type='delete_point',
            description=f'Deleted water point: {point_name}',
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        messages.success(request, 'Water point deleted successfully.')
        return redirect('water_app:map_view')
    
    return render(request, 'confirm_delete.html', {'point': point})

# ==================== API ENDPOINTS ====================

@login_required
def get_county_boundary(request):
    """API endpoint to get county boundary as GeoJSON"""
    try:
        # Get Turkana county (assuming it's the only one or filter by name)
        county = County.objects.filter(county__icontains='turkana').first()
        if not county:
            county = County.objects.first()
        
        if county and county.geom:
            # Serialize to GeoJSON
            geojson = serialize('geojson', [county], geometry_field='geom', 
                               fields=('county', 'pop_2009', 'country'))
            return JsonResponse(json.loads(geojson))
        else:
            return JsonResponse({'type': 'FeatureCollection', 'features': []})
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def get_subcounties_geojson(request):
    """API endpoint to get sub-county boundaries as GeoJSON with real-time counts"""
    try:
        subcounties = SubCounty.objects.all()
        
        if not subcounties.exists():
            return JsonResponse({'type': 'FeatureCollection', 'features': []})
        
        # Serialize to GeoJSON
        geojson = serialize('geojson', subcounties, geometry_field='geom', 
                           fields=('subcounty', 'county', 'province', 'country', 'area_sqkm', 'population'))
        
        data = json.loads(geojson)
        
        for feature in data['features']:
            subcounty_id = feature['id']
            try:
                subcounty = SubCounty.objects.get(id=subcounty_id)
                
                # Get water points in this subcounty
                water_points = WaterPoint.objects.filter(sub_county=subcounty)
                
                # Count with on-the-fly classification
                operational = 0
                non_operational = 0
                
                for wp in water_points:
                    status = wp.classify_from_operation_field()
                    if status == 'operational':
                        operational += 1
                    elif status == 'non_operational':
                        non_operational += 1
                
                total = water_points.count()
                
                feature['properties']['point_count'] = total
                feature['properties']['operational_count'] = operational
                feature['properties']['non_operational_count'] = non_operational
                feature['properties']['name'] = subcounty.subcounty or f"SubCounty {subcounty.id}"
                feature['properties']['area'] = subcounty.area_sqkm
                feature['properties']['success_rate'] = round((operational / total * 100), 1) if total > 0 else 0
                
            except SubCounty.DoesNotExist:
                feature['properties']['point_count'] = 0
                feature['properties']['operational_count'] = 0
                feature['properties']['non_operational_count'] = 0
                feature['properties']['name'] = 'Unknown'
                feature['properties']['success_rate'] = 0
        
        return JsonResponse(data)
    
    except Exception as e:
        print(f"Error in get_subcounties_geojson: {str(e)}")
        return JsonResponse({'type': 'FeatureCollection', 'features': [], 'error': str(e)}, status=500)

@login_required
def get_wards_geojson(request):
    """API endpoint to get ward boundaries as GeoJSON"""
    try:
        subcounty_id = request.GET.get('subcounty_id')
        
        if subcounty_id and subcounty_id != 'all':
            try:
                subcounty = SubCounty.objects.get(id=subcounty_id)
                wards = Ward.objects.filter(subcounty=subcounty)
            except SubCounty.DoesNotExist:
                return JsonResponse({'type': 'FeatureCollection', 'features': []})
        else:
            wards = Ward.objects.all()
        
        if not wards.exists():
            return JsonResponse({'type': 'FeatureCollection', 'features': []})
        
        # Serialize to GeoJSON
        geojson = serialize('geojson', wards, geometry_field='geom',
                           fields=('ward', 'subcounty', 'county'))
        
        data = json.loads(geojson)
        
        for feature in data['features']:
            feature['properties']['name'] = feature['properties'].get('ward', 'Unknown')
            
            # Add water point counts
            ward_id = feature['id']
            try:
                ward = Ward.objects.get(id=ward_id)
                point_count = WaterPoint.objects.filter(ward=ward).count()
                operational_count = WaterPoint.objects.filter(ward=ward, status='operational').count()
                feature['properties']['point_count'] = point_count
                feature['properties']['operational_count'] = operational_count
                feature['properties']['success_rate'] = round((operational_count / point_count * 100), 1) if point_count > 0 else 0
            except:
                feature['properties']['point_count'] = 0
                feature['properties']['operational_count'] = 0
                feature['properties']['success_rate'] = 0
        
        return JsonResponse(data)
    
    except Exception as e:
        print(f"Error in get_wards_geojson: {str(e)}")
        return JsonResponse({'type': 'FeatureCollection', 'features': []})

@login_required
def get_filtered_water_points(request):
    """API endpoint to get filtered water points as GeoJSON with automatic classification"""
    try:
        # Start with all points
        points = WaterPoint.objects.all()
        
        # Apply filters
        subcounty_id = request.GET.get('subcounty_id')
        if subcounty_id and subcounty_id != 'all':
            points = points.filter(sub_county_id=subcounty_id)
        
        ward_id = request.GET.get('ward_id')
        if ward_id and ward_id != 'all':
            points = points.filter(ward_id=ward_id)
        
        # Filter by bounds (for performance)
        bounds = request.GET.get('bounds', '')
        if bounds:
            bounds = bounds.split(',')
            if len(bounds) == 4:
                min_lng, min_lat, max_lng, max_lat = map(float, bounds)
                points = points.filter(
                    longitude__gte=min_lng,
                    longitude__lte=max_lng,
                    latitude__gte=min_lat,
                    latitude__lte=max_lat
                )
        
        # Get total count before limiting
        total_count = points.count()
        
        # Limit for performance
        points = points[:2000]
        
        # Build GeoJSON features with on-the-fly classification
        features = []
        counts = {'operational': 0, 'non_operational': 0, 'unknown': 0}
        
        for point in points:
            # Classify on-the-fly based on operation_field
            classified_status = point.classify_from_operation_field()
            
            # Use the classified status for display
            display_status = classified_status
            
            # Update counts based on classification
            if display_status == 'operational':
                counts['operational'] += 1
            elif display_status == 'non_operational':
                counts['non_operational'] += 1
            else:
                counts['unknown'] += 1
            
            feature = {
                'type': 'Feature',
                'id': point.id,
                'geometry': {
                    'type': 'Point',
                    'coordinates': [point.longitude or 0, point.latitude or 0]
                },
                'properties': {
                    'id': point.id,
                    'name': point.name or point.locality or 'Unnamed',
                    'locality': point.locality,
                    'status': display_status,  # Use classified status
                    'status_display': display_status.title(),
                    'operation_field': point.operation_field,
                    'sub_county': point.sub_county.subcounty if point.sub_county else None,
                    'sub_county_id': point.sub_county.id if point.sub_county else None,
                    'ward': point.ward.ward if point.ward else None,
                    'ward_id': point.ward.id if point.ward else None,
                    'depth': point.well_depth,
                    'depth_value': point.depth_m_value,
                    'yield': point.yield_field,
                    'has_pump': point.has_pump,
                    'ph': point.ph,
                    'ec': point.ec,
                    'source': point.source_1,
                    'created_at': point.created_at.isoformat() if point.created_at else None,
                }
            }
            features.append(feature)
        
        # Create the GeoJSON response
        geojson = {
            'type': 'FeatureCollection',
            'features': features,
            'total_count': total_count,
            'returned_count': len(features),
            'counts': counts  # Include counts in the response
        }
        
        return JsonResponse(geojson)
    
    except Exception as e:
        print(f"Error in get_filtered_water points: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def get_subcounties_list(request):
    """API endpoint to get list of subcounties for dropdown"""
    try:
        subcounties = SubCounty.objects.all().order_by('subcounty')
        data = []
        for sc in subcounties:
            stats = WaterPoint.get_statistics(sub_county=sc)
            data.append({
                'id': sc.id,
                'name': sc.subcounty or f'SubCounty {sc.id}',
                'point_count': stats['total'],
                'success_rate': stats['operational_percent']
            })
        return JsonResponse(data, safe=False)
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def get_wards_list(request):
    """API endpoint to get list of wards for dropdown"""
    try:
        subcounty_id = request.GET.get('subcounty_id')
        
        if subcounty_id and subcounty_id != 'all':
            try:
                # Validate that subcounty exists
                subcounty = SubCounty.objects.get(id=subcounty_id)
                wards = Ward.objects.filter(subcounty=subcounty).order_by('ward')
            except SubCounty.DoesNotExist:
                # Return empty array if subcounty doesn't exist
                return JsonResponse([], safe=False)
        else:
            wards = Ward.objects.all().order_by('ward')[:100]  # Limit to 100 for performance
        
        data = []
        for w in wards:
            try:
                point_count = WaterPoint.objects.filter(ward=w).count()
                operational_count = WaterPoint.objects.filter(ward=w, status='operational').count()
                data.append({
                    'id': w.id,
                    'name': w.ward or f'Ward {w.id}',
                    'subcounty_id': w.subcounty.id if w.subcounty else None,
                    'point_count': point_count,
                    'operational_count': operational_count,
                    'success_rate': round((operational_count / point_count * 100), 1) if point_count > 0 else 0
                })
            except Exception as e:
                # Log error but continue
                print(f"Error processing ward {w.id}: {str(e)}")
                continue
        
        return JsonResponse(data, safe=False)
    
    except Exception as e:
        print(f"Error in get_wards_list: {str(e)}")
        # Always return an array, even on error
        return JsonResponse([], safe=False)

@login_required
def get_subcounty_stats(request):
    """API endpoint to get statistics for a specific subcounty"""
    try:
        subcounty_id = request.GET.get('subcounty_id')
        if not subcounty_id:
            return JsonResponse({'error': 'subcounty_id required'}, status=400)
        
        subcounty = get_object_or_404(SubCounty, id=subcounty_id)
        stats = WaterPoint.get_statistics(sub_county=subcounty)
        
        # Get ward breakdown
        wards = Ward.objects.filter(subcounty=subcounty)
        ward_stats = []
        for ward in wards:
            ward_stats.append({
                'id': ward.id,
                'name': ward.ward,
                **WaterPoint.get_statistics(ward=ward)
            })
        
        stats['wards'] = ward_stats
        stats['name'] = subcounty.subcounty
        stats['area'] = subcounty.area_sqkm
        stats['population'] = subcounty.population
        
        return JsonResponse(stats)
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def calculate_distance(request):
    """API endpoint to calculate distance between two points"""
    try:
        lat1 = float(request.GET.get('lat1'))
        lng1 = float(request.GET.get('lng1'))
        lat2 = float(request.GET.get('lat2'))
        lng2 = float(request.GET.get('lng2'))
        
        # Haversine formula
        R = 6371  # Earth's radius in km
        dlat = math.radians(lat2 - lat1)
        dlng = math.radians(lng2 - lng1)
        a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        distance = R * c
        
        return JsonResponse({
            'distance_km': round(distance, 2),
            'distance_m': round(distance * 1000, 0),
            'distance_mi': round(distance * 0.621371, 2)
        })
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def calculate_area(request):
    """API endpoint to calculate area of a drawn polygon"""
    try:
        data = json.loads(request.body)
        coordinates = data.get('coordinates', [])
        
        if len(coordinates) < 3:
            return JsonResponse({'error': 'Need at least 3 points'}, status=400)
        
        # Shoelace formula for planar area
        area = 0
        n = len(coordinates)
        for i in range(n):
            x1, y1 = coordinates[i]
            x2, y2 = coordinates[(i + 1) % n]
            area += (x1 * y2 - x2 * y1)
        
        area = abs(area) / 2
        
        # Rough conversion from square degrees to square km
        # 1 degree ≈ 111 km at equator
        area_km2 = area * 111 * 111
        area_hectares = area_km2 * 100
        area_acres = area_km2 * 247.105
        
        return JsonResponse({
            'area_sq_km': round(area_km2, 2),
            'area_sq_m': round(area_km2 * 1000000, 0),
            'area_hectares': round(area_hectares, 2),
            'area_acres': round(area_acres, 2)
        })
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def get_water_point_by_id(request, point_id):
    """API endpoint to get a specific water point"""
    try:
        point = get_object_or_404(WaterPoint, id=point_id)
        
        data = {
            'id': point.id,
            'name': point.name or point.locality,
            'latitude': point.latitude,
            'longitude': point.longitude,
            'status': point.status,
            'status_display': point.get_status_display(),
            'depth': point.well_depth,
            'depth_value': point.depth_m_value,
            'yield': point.yield_field,
            'sub_county': point.sub_county.subcounty if point.sub_county else None,
            'sub_county_id': point.sub_county.id if point.sub_county else None,
            'ward': point.ward.ward if point.ward else None,
            'ward_id': point.ward.id if point.ward else None,
            'source': point.source_1,
            'ph': point.ph,
            'ec': point.ec,
            'operation_field': point.operation_field,
            'has_pump': point.has_pump,
            'pump_type': point.pump_type,
            'installed_year': point.installed_year,
            'created_at': point.created_at.isoformat() if point.created_at else None,
            'created_by': point.created_by.username if point.created_by else None,
            'predicted_status': point.predicted_status,
            'prediction_probability': point.prediction_probability,
        }
        
        return JsonResponse(data)
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

# ==================== BOUNDARY MANAGEMENT ====================

@login_required
def upload_boundary(request):
    """Handle boundary file upload"""
    if request.method == 'POST':
        form = BoundaryUploadForm(request.POST, request.FILES)
        if form.is_valid():
            boundary_file = form.save(commit=False)
            boundary_file.uploaded_by = request.user
            boundary_file.save()
            
            # Log activity
            UserActivity.objects.create(
                user=request.user,
                activity_type='upload_boundary',
                description=f'Uploaded boundary file: {boundary_file.name}',
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            
            messages.success(request, 'Boundary file uploaded successfully!')
            return redirect('water_app:map_view')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = BoundaryUploadForm()
    
    return render(request, 'upload_boundary.html', {'form': form})

@staff_member_required
def import_shapefile_view(request):
    """View for uploading and importing shapefiles"""
    if request.method == 'POST':
        form = ShapefileUploadForm(request.POST, request.FILES)
        if form.is_valid():
            upload = form.save(commit=False)
            upload.uploaded_by = request.user
            upload.save()
            
            # Get the uploaded files from the form
            uploaded_files = form.cleaned_data['shapefile_files']
            
            # Create a directory for this upload
            upload_dir = f'uploads/shapefiles/{upload.id}/'
            
            shp_file = None
            shx_file = None
            dbf_file = None
            prj_file = None
            
            # Save each file
            for f in uploaded_files:
                file_path = default_storage.save(upload_dir + f.name, ContentFile(f.read()))
                
                # Track files by extension
                if f.name.endswith('.shp'):
                    shp_file = file_path
                    upload.shapefile = file_path
                elif f.name.endswith('.shx'):
                    shx_file = file_path
                    upload.shx_file = file_path
                elif f.name.endswith('.dbf'):
                    dbf_file = file_path
                    upload.dbf_file = file_path
                elif f.name.endswith('.prj'):
                    prj_file = file_path
                    upload.prj_file = file_path
            
            upload.save()
            
            if not shp_file:
                messages.error(request, 'No .shp file found in upload')
                upload.status = 'failed'
                upload.error_message = 'No .shp file found'
                upload.save()
                return redirect('admin:water_app_shapefileupload_changelist')
            
            try:
                # Get the full path of the saved shp file
                shp_full_path = os.path.join(settings.MEDIA_ROOT, shp_file)
                
                # Run import command
                from django.core.management import call_command
                
                call_command(
                    'import_shapefiles',
                    shp_full_path,
                    upload.upload_type,
                    user_id=request.user.id,
                    encoding='utf-8',
                )
                
                # Update water point statuses after import
                if upload.upload_type == 'water_points':
                    updated = WaterPoint.update_all_status_from_operation_field()
                    messages.info(request, f'Classified {updated["updated"]} water points based on operation field.')
                
                messages.success(request, f'Successfully imported {upload.upload_type}')
                upload.status = 'completed'
                upload.processed_at = timezone.now()
                upload.imported_count = 1
                upload.save()
                
            except Exception as e:
                messages.error(request, f'Import failed: {str(e)}')
                upload.status = 'failed'
                upload.error_message = str(e)
                upload.save()
            
            return redirect('admin:water_app_shapefileupload_changelist')
    else:
        form = ShapefileUploadForm()
    
    return render(request, 'admin/import_shapefile.html', {
        'form': form,
        'title': 'Import Shapefile'
    })

# ==================== PREDICTION VIEWS ====================

@login_required
def prediction_dashboard(request):
    """ML Prediction Dashboard"""
    context = {
        'subcounties': SubCounty.objects.all().order_by('subcounty'),
        'model_ready': ml_service.is_ready(),
        'model_info': ml_service.get_model_info() if ml_service.is_ready() else None
    }
    return render(request, 'prediction_dashboard.html', context)

@login_required
def predict_water_point(request, point_id):
    """Predict operational status for a single water point with full metrics"""
    try:
        point = get_object_or_404(WaterPoint, id=point_id)
        
        # Check if ML service is ready
        if not ml_service.is_ready():
            return JsonResponse({
                'success': False,
                'error': 'ML model not loaded',
                'status': 'unavailable'
            }, status=503)
        
        # Make prediction
        result = ml_service.predict(point, return_features=True)
        
        if not result['success']:
            return JsonResponse(result, status=500)
        
        # Update the water point with prediction
        point.predicted_status = result['status']
        point.prediction_probability = result['probability']
        point.prediction_date = timezone.now()
        point.suitability_score = result['probability']
        point.save()
        
        # Log the prediction
        UserActivity.objects.create(
            user=request.user,
            activity_type='prediction',
            description=f'Predicted status for water point {point.id}: {result["status"]} (prob: {result["probability"]:.3f})',
            ip_address=request.META.get('REMOTE_ADDR'),
            water_point=point
        )
        
        return JsonResponse({
            'success': True,
            'point_id': point.id,
            'point_name': point.name or point.locality,
            'prediction': result,
            'model_info': ml_service.get_model_info()
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def predict_area(request):
    """Predict for all water points in a drawn area with comprehensive statistics"""
    try:
        data = json.loads(request.body)
        geometry = data.get('geometry')
        include_features = data.get('include_features', False)
        
        if not geometry:
            return JsonResponse({'error': 'No geometry provided'}, status=400)
        
        print(f"Received geometry type: {geometry.get('type')}")
        
        # Convert GeoJSON to GEOS geometry
        try:
            geom_str = json.dumps(geometry)
            poly = GEOSGeometry(geom_str, srid=4326)
            print(f"Created polygon with area: {poly.area}")
        except Exception as e:
            print(f"Error creating GEOS geometry: {str(e)}")
            return JsonResponse({'error': f'Invalid geometry: {str(e)}'}, status=400)
        
        # Find water points within polygon using spatial query
        points = []
        all_water_points = WaterPoint.objects.filter(
            latitude__isnull=False,
            longitude__isnull=False
        )
        print(f"Total water points with coordinates: {all_water_points.count()}")
        
        for wp in all_water_points:
            try:
                point = Point(wp.longitude, wp.latitude, srid=4326)
                if poly.contains(point):
                    points.append(wp)
            except Exception as e:
                print(f"Error checking point {wp.id}: {str(e)}")
                continue
        
        print(f"Points within polygon: {len(points)}")
        
        if not points:
            return JsonResponse({
                'success': True,
                'total_points': 0,
                'predictions': [],
                'summary': {
                    'total': 0,
                    'operational': 0,
                    'non_operational': 0,
                    'high_confidence': 0,
                    'medium_confidence': 0,
                    'low_confidence': 0,
                    'operational_percent': 0,
                    'avg_probability': 0,
                    'std_probability': 0,
                    'min_probability': 0,
                    'max_probability': 0
                }
            })
        
        # Make predictions for all points
        predictions = []
        operational_count = 0
        high_confidence = 0
        medium_confidence = 0
        low_confidence = 0
        
        probabilities = []
        
        for point in points:
            try:
                result = ml_service.predict(point)
                
                if result.get('success', False):
                    predictions.append({
                        'point_id': point.id,
                        'name': point.name or point.locality or 'Unnamed',
                        'latitude': point.latitude,
                        'longitude': point.longitude,
                        'prediction': result
                    })
                    
                    prob = result.get('probability', 0.5)
                    probabilities.append(prob)
                    
                    if result.get('status') == 'operational':
                        operational_count += 1
                    
                    confidence = result.get('confidence', 'low')
                    if confidence == 'high':
                        high_confidence += 1
                    elif confidence == 'medium':
                        medium_confidence += 1
                    else:
                        low_confidence += 1
                    
                    # Update the water point with prediction
                    point.predicted_status = result.get('status')
                    point.prediction_probability = prob
                    point.prediction_date = timezone.now()
                    point.save()
            except Exception as e:
                print(f"Error predicting point {point.id}: {str(e)}")
                continue
        
        total = len(predictions)
        
        # Calculate statistics
        if probabilities:
            avg_prob = float(np.mean(probabilities))
            std_prob = float(np.std(probabilities)) if len(probabilities) > 1 else 0
            min_prob = float(np.min(probabilities))
            max_prob = float(np.max(probabilities))
        else:
            avg_prob = std_prob = min_prob = max_prob = 0
        
        summary = {
            'total': total,
            'operational': operational_count,
            'non_operational': total - operational_count,
            'operational_percent': round(operational_count / total * 100, 1) if total > 0 else 0,
            'high_confidence': high_confidence,
            'medium_confidence': medium_confidence,
            'low_confidence': low_confidence,
            'avg_probability': round(avg_prob, 3),
            'std_probability': round(std_prob, 3),
            'min_probability': round(min_prob, 3),
            'max_probability': round(max_prob, 3)
        }
        
        # Create prediction batch
        batch = PredictionBatch.objects.create(
            name=f"Area Prediction {timezone.now().strftime('%Y-%m-%d %H:%M')}",
            description=f"Predicted {total} points in selected area",
            created_by=request.user,
            total_points=total,
            operational_predicted=operational_count,
            non_operational_predicted=total - operational_count,
            status='completed',
            completed_at=timezone.now(),
            results_summary=summary
        )
        
        response = {
            'success': True,
            'batch_id': batch.id,
            'summary': summary,
            'predictions': predictions[:50] if not include_features else predictions,
            'model_metrics': ml_service.get_model_info().get('metrics', {}),
            'threshold': ml_service._threshold
        }
        
        return JsonResponse(response)
        
    except json.JSONDecodeError as e:
        print(f"JSON decode error: {str(e)}")
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        print(f"Error in predict_area: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def predict_suitable_locations(request):
    """
    Find suitable locations for new water points within an area using advanced grid search
    """
    try:
        data = json.loads(request.body)
        geometry = data.get('geometry')
        n_locations = data.get('n_locations', 10)
        grid_spacing = data.get('grid_spacing', 2)  # km
        
        if not geometry:
            return JsonResponse({'error': 'No geometry provided'}, status=400)
        
        # Convert GeoJSON to GEOS geometry
        geom_str = json.dumps(geometry)
        poly = GEOSGeometry(geom_str, srid=4326)
        
        # Get bounds
        bounds = poly.extent  # (xmin, ymin, xmax, ymax)
        
        # Calculate grid size based on area
        lat_range = bounds[3] - bounds[1]
        lon_range = bounds[2] - bounds[0]
        area_deg = lat_range * lon_range
        
        # Adjust grid size based on area (more points for larger areas)
        if area_deg > 10:  # Large area
            grid_size = 30
        elif area_deg > 5:  # Medium area
            grid_size = 25
        elif area_deg > 2:  # Small area
            grid_size = 20
        else:  # Very small area
            grid_size = 15
        
        # Use advanced method to find optimal locations
        result = ml_service.find_optimal_locations_advanced(
            bounds=(bounds[1], bounds[3], bounds[0], bounds[2]),
            n_locations=n_locations,
            grid_size=grid_size,
            min_distance_km=5  # Minimum 5km between recommendations
        )
        
        if not result['success']:
            return JsonResponse({'error': 'Failed to find optimal locations'}, status=500)
        
        # Format response
        optimal_locations = []
        for loc in result['optimal_locations']:
            optimal_locations.append({
                'rank': len(optimal_locations) + 1,
                'latitude': loc['lat'],
                'longitude': loc['lon'],
                'score': loc['score'],
                'category': loc['category'],
                'prediction': loc['prediction'],
                'reasons': loc['reasons']
            })
        
        response = {
            'success': True,
            'n_analyzed': result['statistics']['total_analyzed'],
            'optimal_locations': optimal_locations,
            'statistics': {
                'locations_found': result['statistics']['locations_found'],
                'mean_probability': result['statistics']['avg_score'],
                'max_probability': result['statistics']['max_score'],
                'min_probability': result['statistics']['min_score'],
                'locations_above_threshold': result['statistics']['above_threshold']
            },
            'model_metrics': ml_service.get_model_info()['metrics'],
            'threshold': result['threshold']
        }
        
        return JsonResponse(response)
        
    except Exception as e:
        print(f"Error in predict_suitable_locations: {str(e)}")
        traceback.print_exc()
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def batch_prediction(request):
    """Create and run a batch prediction with full metrics"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            batch_name = data.get('name', f"Batch Prediction {timezone.now().strftime('%Y-%m-%d %H:%M')}")
            subcounty_id = data.get('subcounty_id')
            ward_id = data.get('ward_id')
            status_filter = data.get('status', 'all')
            
            # Filter water points
            points = WaterPoint.objects.all()
            if subcounty_id and subcounty_id != 'all':
                points = points.filter(sub_county_id=subcounty_id)
            if ward_id and ward_id != 'all':
                points = points.filter(ward_id=ward_id)
            if status_filter != 'all':
                points = points.filter(status=status_filter)
            
            # Limit to points without recent predictions
            points = points.filter(
                Q(predicted_status__isnull=True) |
                Q(prediction_date__lt=timezone.now() - timezone.timedelta(days=30))
            )
            
            total_points = points.count()
            
            if total_points == 0:
                return JsonResponse({'message': 'No points need prediction'})
            
            # Create batch record
            batch = PredictionBatch.objects.create(
                name=batch_name,
                description=f"Predicting {total_points} water points",
                created_by=request.user,
                total_points=total_points,
                status='processing'
            )
            
            # Process in chunks
            chunk_size = 100
            operational_count = 0
            predictions = []
            probabilities = []
            confidence_counts = {'high': 0, 'medium': 0, 'low': 0}
            
            for i in range(0, total_points, chunk_size):
                chunk = points[i:i+chunk_size]
                for point in chunk:
                    result = ml_service.predict(point)
                    
                    if result['success']:
                        point.predicted_status = result['status']
                        point.prediction_probability = result['probability']
                        point.prediction_date = timezone.now()
                        point.save()
                        
                        if result['status'] == 'operational':
                            operational_count += 1
                        
                        probabilities.append(result['probability'])
                        confidence_counts[result['confidence']] += 1
                        
                        predictions.append({
                            'point_id': point.id,
                            'name': point.name or point.locality,
                            'status': result['status'],
                            'probability': result['probability'],
                            'confidence': result['confidence'],
                            'individual_probabilities': result.get('individual_probabilities', {})
                        })
                
                # Update batch progress
                batch.operational_predicted = operational_count
                batch.non_operational_predicted = (i + len(chunk)) - operational_count
                batch.save()
            
            # Calculate statistics
            summary = {
                'total': total_points,
                'operational': operational_count,
                'non_operational': total_points - operational_count,
                'operational_percent': round(operational_count / total_points * 100, 1),
                'avg_probability': round(float(np.mean(probabilities)), 3) if probabilities else 0,
                'std_probability': round(float(np.std(probabilities)), 3) if probabilities else 0,
                'high_confidence': confidence_counts['high'],
                'medium_confidence': confidence_counts['medium'],
                'low_confidence': confidence_counts['low']
            }
            
            # Complete batch
            batch.status = 'completed'
            batch.completed_at = timezone.now()
            batch.results_summary = summary
            batch.save()
            
            # Log activity
            UserActivity.objects.create(
                user=request.user,
                activity_type='batch_prediction',
                description=f'Completed batch prediction: {batch_name} with {total_points} points',
                ip_address=request.META.get('REMOTE_ADDR'),
                batch=batch
            )
            
            return JsonResponse({
                'success': True,
                'batch_id': batch.id,
                'summary': summary,
                'predictions': predictions[:50],
                'model_metrics': ml_service.get_model_info()['metrics']
            })
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    # GET request - show form
    context = {
        'recent_batches': PredictionBatch.objects.filter(created_by=request.user).order_by('-created_at')[:10],
        'subcounties': SubCounty.objects.all().order_by('subcounty'),
        'model_info': ml_service.get_model_info() if ml_service.is_ready() else None,
        'model_ready': ml_service.is_ready()
    }
    return render(request, 'batch_prediction.html', context)

@login_required
def model_info(request):
    """Get complete information about the current ML model"""
    if not ml_service.is_ready():
        return JsonResponse({
            'status': 'not_ready',
            'message': 'Model not loaded',
            'metrics': {},
            'feature_importance': {}
        })
    
    info = ml_service.get_model_info()
    
    # Add feature importance with descriptions
    feature_descriptions = {
        'well_depth': 'Depth of well in meters',
        'ph': 'pH level of water',
        'dist_to_road_m': 'Distance to nearest road (m)',
        'dist_to_nearest_water_m': 'Distance to nearest water source (m)',
        'water_points_5km': 'Number of water points within 5km',
        'people_per_water_point_5km': 'People per water point within 5km',
        'building_proximity_score': 'Proximity to buildings score',
        'latitude': 'Latitude coordinate',
        'longitude': 'Longitude coordinate',
        'short_rains_mm': 'Short rains precipitation (mm)',
        'sand_pct': 'Sand percentage in soil',
        'clay_pct': 'Clay percentage in soil',
        'soc': 'Soil organic carbon',
        'flow_accumulation': 'Flow accumulation',
        'water_scarcity_index': 'Water scarcity index (engineered)',
        'road_access_index': 'Road access index (engineered)',
        'soil_quality_index': 'Soil quality index (engineered)',
        'climate_risk_index': 'Climate risk index (engineered)',
        'spatial_cluster': 'Spatial cluster'
    }
    
    enhanced_importance = []
    for feat, imp in info['feature_importance'].items():
        enhanced_importance.append({
            'feature': feat,
            'importance': imp,
            'description': feature_descriptions.get(feat, 'No description'),
            'category': 'engineered' if feat in [
                'density_road_interaction', 'people_water_ratio_sq', 'distance_to_water_scaled',
                'road_access_index', 'water_scarcity_index', 'soil_quality_index',
                'climate_risk_index', 'spatial_cluster'
            ] else 'base'
        })
    
    info['feature_importance_detailed'] = enhanced_importance
    
    return JsonResponse(info)

@login_required
def prediction_history(request, batch_id=None):
    """Get prediction history and batch details"""
    if batch_id:
        # Get specific batch
        batch = get_object_or_404(PredictionBatch, id=batch_id, created_by=request.user)
        
        # Get points predicted in this batch (approximate by date range)
        points = WaterPoint.objects.filter(
            prediction_date__range=[batch.created_at, batch.completed_at or timezone.now()]
        ).select_related('sub_county', 'ward')[:100]
        
        points_data = [{
            'id': p.id,
            'name': p.name or p.locality,
            'status': p.status,
            'predicted_status': p.predicted_status,
            'prediction_probability': p.prediction_probability,
            'sub_county': p.sub_county.subcounty if p.sub_county else None,
            'ward': p.ward.ward if p.ward else None
        } for p in points]
        
        return JsonResponse({
            'batch': {
                'id': batch.id,
                'name': batch.name,
                'description': batch.description,
                'created_at': batch.created_at,
                'completed_at': batch.completed_at,
                'total_points': batch.total_points,
                'operational_predicted': batch.operational_predicted,
                'non_operational_predicted': batch.non_operational_predicted,
                'status': batch.status,
                'results_summary': batch.results_summary
            },
            'points': points_data
        })
    
    else:
        # List all batches
        batches = PredictionBatch.objects.filter(created_by=request.user).order_by('-created_at')
        batches_data = [{
            'id': b.id,
            'name': b.name,
            'created_at': b.created_at,
            'completed_at': b.completed_at,
            'total_points': b.total_points,
            'operational_predicted': b.operational_predicted,
            'non_operational_predicted': b.non_operational_predicted,
            'status': b.status,
            'results_summary': b.results_summary
        } for b in batches]
        
        return JsonResponse({'batches': batches_data})

@login_required
def compare_predictions(request):
    """Compare predictions with actual status"""
    try:
        # Get points with both actual and predicted status
        points = WaterPoint.objects.filter(
            status__isnull=False,
            predicted_status__isnull=False
        ).exclude(status='unknown')
        
        total = points.count()
        if total == 0:
            return JsonResponse({'message': 'No points with both actual and predicted status'})
        
        correct = points.filter(status=F('predicted_status')).count()
        accuracy = correct / total if total > 0 else 0
        
        # Confusion matrix
        cm = {
            'true_positive': points.filter(status='operational', predicted_status='operational').count(),
            'false_positive': points.filter(status='non_operational', predicted_status='operational').count(),
            'true_negative': points.filter(status='non_operational', predicted_status='non_operational').count(),
            'false_negative': points.filter(status='operational', predicted_status='non_operational').count()
        }
        
        # Calculate metrics
        precision = cm['true_positive'] / (cm['true_positive'] + cm['false_positive']) if (cm['true_positive'] + cm['false_positive']) > 0 else 0
        recall = cm['true_positive'] / (cm['true_positive'] + cm['false_negative']) if (cm['true_positive'] + cm['false_negative']) > 0 else 0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
        
        return JsonResponse({
            'total_points': total,
            'correct_predictions': correct,
            'accuracy': round(accuracy, 4),
            'precision': round(precision, 4),
            'recall': round(recall, 4),
            'f1_score': round(f1, 4),
            'confusion_matrix': cm,
            'model_metrics': ml_service.get_model_info()['metrics'] if ml_service.is_ready() else None
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

# ==================== SPATIAL QUERY ENDPOINTS ====================

@login_required
def get_points_in_polygon(request):
    """API endpoint to get statistics for points within a drawn polygon or clicked boundary"""
    try:
        if request.method != 'POST':
            return JsonResponse({'error': 'POST method required'}, status=405)
        
        # Parse request body
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        
        geometry = data.get('geometry')
        
        if not geometry:
            return JsonResponse({'error': 'No geometry provided'}, status=400)
        
        if not geometry.get('coordinates'):
            return JsonResponse({'error': 'Invalid geometry coordinates'}, status=400)
        
        print(f"Received geometry type: {geometry['type']}")
        
        # Handle different geometry types
        try:
            if geometry['type'] == 'Polygon':
                # Handle single polygon
                coords = geometry['coordinates'][0]  # Outer ring
                
                # Ensure we have at least 3 points
                if len(coords) < 3:
                    return JsonResponse({'error': 'Polygon must have at least 3 points'}, status=400)
                
                # Convert to list of tuples (x, y)
                poly_coords = [(coord[0], coord[1]) for coord in coords]
                
                # Create polygon
                polygon = Polygon(poly_coords, srid=4326)
                
            elif geometry['type'] == 'MultiPolygon':
                # Handle multipolygon - take the first polygon for simplicity
                if len(geometry['coordinates']) == 0:
                    return JsonResponse({'error': 'MultiPolygon has no polygons'}, status=400)
                
                first_polygon_coords = geometry['coordinates'][0][0]  # First polygon, outer ring
                
                if len(first_polygon_coords) < 3:
                    return JsonResponse({'error': 'Polygon must have at least 3 points'}, status=400)
                
                poly_coords = [(coord[0], coord[1]) for coord in first_polygon_coords]
                polygon = Polygon(poly_coords, srid=4326)
                
            else:
                return JsonResponse({'error': f'Unsupported geometry type: {geometry["type"]}'}, status=400)
            
        except Exception as e:
            print(f"Error creating polygon: {str(e)}")
            traceback.print_exc()
            return JsonResponse({'error': f'Invalid polygon: {str(e)}'}, status=400)
        
        # Find all water points within this polygon
        water_points = WaterPoint.objects.all()
        
        points_in_polygon = []
        operational = 0
        non_operational = 0
        unknown = 0
        
        # Manual spatial filtering (works even without PostGIS)
        for wp in water_points:
            if wp.latitude and wp.longitude:
                try:
                    point = Point(wp.longitude, wp.latitude, srid=4326)
                    if polygon.contains(point):
                        points_in_polygon.append(wp)
                        
                        # Classify status
                        status = wp.classify_from_operation_field()
                        if status == 'operational':
                            operational += 1
                        elif status == 'non_operational':
                            non_operational += 1
                        else:
                            unknown += 1
                except Exception as e:
                    print(f"Error processing point {wp.id}: {str(e)}")
                    continue
        
        total = len(points_in_polygon)
        
        # Calculate statistics
        stats = {
            'total': total,
            'operational': operational,
            'non_operational': non_operational,
            'unknown': unknown,
            'success_rate': round((operational / total * 100), 1) if total > 0 else 0,
            'points': [
                {
                    'id': wp.id,
                    'name': wp.name or wp.locality or f"WP-{wp.id}",
                    'latitude': wp.latitude,
                    'longitude': wp.longitude,
                    'status': wp.classify_from_operation_field(),
                    'depth': wp.depth_m_value,
                    'yield': wp.yield_field,
                } for wp in points_in_polygon[:50]
            ]
        }
        
        return JsonResponse(stats)
    
    except Exception as e:
        print(f"Error in get_points_in_polygon: {str(e)}")
        traceback.print_exc()
        return JsonResponse({
            'error': str(e),
            'message': 'Internal server error processing polygon query'
        }, status=500)

# ==================== UTILITY VIEWS ====================

@login_required
def export_data(request):
    """Export water points data as CSV or GeoJSON"""
    format_type = request.GET.get('format', 'csv')
    subcounty_id = request.GET.get('subcounty_id')
    status = request.GET.get('status')
    
    # Get filtered data
    points = WaterPoint.objects.all()
    
    if subcounty_id and subcounty_id != 'all':
        points = points.filter(sub_county_id=subcounty_id)
    
    if status and status != 'all':
        points = points.filter(status=status)
    
    if format_type == 'geojson':
        # Export as GeoJSON
        geojson = WaterPoint.to_geojson_collection(points)
        response = JsonResponse(geojson)
        response['Content-Disposition'] = f'attachment; filename="water_points_{timezone.now().strftime("%Y%m%d_%H%M%S")}.geojson"'
        return response
    
    else:
        # Export as CSV
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="water_points_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'ID', 'Name', 'Locality', 'Sub-County', 'County', 'Ward',
            'Latitude', 'Longitude', 'Elevation', 'Status', 'Operation Field',
            'Depth (m)', 'Yield (L/s)', 'Has Pump', 'Pump Type', 'Installed Year',
            'Water Quality', 'pH', 'EC', 'Temperature', 'Source',
            'Predicted Status', 'Prediction Probability', 'Created By', 'Created At'
        ])
        
        for point in points.select_related('sub_county', 'ward', 'created_by'):
            writer.writerow([
                point.id,
                point.name,
                point.locality,
                point.sub_county.subcounty if point.sub_county else '',
                point.sub_county.county if point.sub_county else '',
                point.ward.ward if point.ward else '',
                point.latitude,
                point.longitude,
                point.elevation,
                point.get_status_display(),
                point.operation_field,
                point.well_depth,
                point.yield_field,
                'Yes' if point.has_pump else 'No',
                point.pump_type,
                point.installed_year,
                point.water_quality,
                point.ph,
                point.ec,
                point.temperatur,
                point.source_1,
                point.predicted_status,
                point.prediction_probability,
                point.created_by.username if point.created_by else '',
                point.created_at.strftime('%Y-%m-%d %H:%M')
            ])
        
        # Log activity
        UserActivity.objects.create(
            user=request.user,
            activity_type='export_data',
            description=f'Exported {points.count()} water points to {format_type.upper()}',
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        return response

@login_required
def api_status(request):
    """API endpoint to check system status"""
    stats = {
        'status': 'online',
        'timestamp': timezone.now().isoformat(),
        'user': {
            'username': request.user.username,
            'is_authenticated': request.user.is_authenticated,
            'is_staff': request.user.is_staff,
            'is_superuser': request.user.is_superuser,
        },
        'statistics': {
            'total_water_points': WaterPoint.objects.count(),
            'total_subcounties': SubCounty.objects.count(),
            'total_wards': Ward.objects.count(),
            'total_counties': County.objects.count(),
            'total_predictions': PredictionBatch.objects.count(),
            'user_points': WaterPoint.objects.filter(created_by=request.user).count(),
        },
        'system': {
            'debug': settings.DEBUG,
            'timezone': str(settings.TIME_ZONE),
        },
        'ml_model': {
            'ready': ml_service.is_ready(),
            'info': ml_service.get_model_info() if ml_service.is_ready() else None
        }
    }
    return JsonResponse(stats)

@staff_member_required
def update_status_from_operation(request):
    """Admin endpoint to update all water point statuses from operation_field"""
    if not request.user.is_superuser:
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    try:
        dry_run = request.GET.get('dry_run') == 'true'
        stats = WaterPoint.update_all_status_from_operation_field(dry_run=dry_run)
        
        if not dry_run:
            UserActivity.objects.create(
                user=request.user,
                activity_type='system_update',
                description=f'Updated {stats["updated"]} water point statuses from operation field',
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
        
        return JsonResponse({
            'success': True,
            'dry_run': dry_run,
            **stats
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def get_notifications(request):
    """API endpoint to get user notifications"""
    notifications = Notification.objects.filter(
        Q(user=request.user) | Q(is_global=True),
        Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())
    ).order_by('-created_at')[:20]
    
    data = []
    for n in notifications:
        data.append({
            'id': n.id,
            'title': n.title,
            'message': n.message,
            'priority': n.priority,
            'is_read': n.is_read,
            'created_at': n.created_at.isoformat(),
        })
    
    return JsonResponse(data, safe=False)

@login_required
def mark_notification_read(request, notification_id):
    """Mark a notification as read"""
    notification = get_object_or_404(Notification, id=notification_id, user=request.user)
    notification.is_read = True
    notification.read_at = timezone.now()
    notification.save()
    
    return JsonResponse({'success': True})

@login_required
def get_welcome_box(request):
    """Return the welcome box HTML for AJAX requests"""
    stats = WaterPoint.get_statistics()
    context = {
        'total_points': stats['total'],
        'operational_count': stats['operational'],
        'subcounty_count': SubCounty.objects.count(),
        'ward_count': Ward.objects.count(),
        'model_ready': ml_service.is_ready()
    }
    return render(request, 'partials/welcome_box.html', context)



@login_required
def prediction_results(request, batch_id):
    """View prediction batch results"""
    try:
        batch = get_object_or_404(PredictionBatch, id=batch_id, created_by=request.user)
        
        # Get points predicted in this batch (approximate by date range)
        points = WaterPoint.objects.filter(
            prediction_date__range=[batch.created_at, batch.completed_at or timezone.now()]
        ).select_related('sub_county', 'ward')[:100]
        
        context = {
            'batch': batch,
            'points': points,
            'model_ready': ml_service.is_ready(),
        }
        return render(request, 'prediction_results.html', context)
        
    except Exception as e:
        messages.error(request, f'Error loading prediction results: {str(e)}')
        return redirect('water_app:prediction_dashboard')