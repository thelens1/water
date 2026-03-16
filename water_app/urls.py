# water_app/urls.py

from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

app_name = 'water_app'

urlpatterns = [
    # ==================== AUTHENTICATION ====================
    path('', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),
    
    # Password Reset
    path('password-reset/', 
         auth_views.PasswordResetView.as_view(template_name='password_reset.html'),
         name='password_reset'),
    path('password-reset/done/', 
         auth_views.PasswordResetDoneView.as_view(template_name='password_reset_done.html'),
         name='password_reset_done'),
    path('password-reset-confirm/<uidb64>/<token>/', 
         auth_views.PasswordResetConfirmView.as_view(template_name='password_reset_confirm.html'),
         name='password_reset_confirm'),
    path('password-reset-complete/', 
         auth_views.PasswordResetCompleteView.as_view(template_name='password_reset_complete.html'),
         name='password_reset_complete'),
    
    # ==================== MAIN VIEWS ====================
    path('map/', views.map_view, name='map_view'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('profile/', views.profile, name='profile'),
    
    # ==================== WATER POINT MANAGEMENT ====================
    path('water-point/add/', views.add_water_point, name='add_water_point'),
    path('water-point/<int:point_id>/', views.water_point_detail, name='water_point_detail'),
    path('water-point/<int:point_id>/edit/', views.edit_water_point, name='edit_water_point'),
    path('water-point/<int:point_id>/delete/', views.delete_water_point, name='delete_water_point'),
    
    # ==================== BOUNDARY MANAGEMENT ====================
    path('upload-boundary/', views.upload_boundary, name='upload_boundary'),
    path('import/shapefile/', views.import_shapefile_view, name='import_shapefile'),
    
    # ==================== PREDICTIONS ====================
    path('predictions/', views.prediction_dashboard, name='prediction_dashboard'),
    path('api/predict/<int:point_id>/', views.predict_water_point, name='predict_water_point'),
    path('api/predict-area/', views.predict_area, name='predict_area'),
    path('api/predict-suitable/', views.predict_suitable_locations, name='predict_suitable_locations'),
    path('api/batch-prediction/', views.batch_prediction, name='batch_prediction'),
    path('api/model-info/', views.model_info, name='model_info'),
    path('api/prediction-history/', views.prediction_history, name='prediction_history'),
    path('api/prediction-history/<int:batch_id>/', views.prediction_history, name='prediction_history_detail'),
    path('api/compare-predictions/', views.compare_predictions, name='compare_predictions'),
    path('batch-prediction/<int:batch_id>/', views.prediction_results, name='prediction_results'),
    
    # ==================== UTILITY ====================
    path('export-data/', views.export_data, name='export_data'),
    path('api/status/', views.api_status, name='api_status'),
    path('admin/update-status/', views.update_status_from_operation, name='update_status'),
    
    # ==================== NOTIFICATIONS ====================
    path('api/notifications/', views.get_notifications, name='get_notifications'),
    path('api/notifications/<int:notification_id>/read/', views.mark_notification_read, name='mark_notification_read'),
    
    # ==================== WELCOME BOX ====================
    path('api/get-welcome-box/', views.get_welcome_box, name='get_welcome_box'),
    
    # ==================== GEOJSON API ENDPOINTS ====================
    path('api/county-boundary/', views.get_county_boundary, name='get_county_boundary'),
    path('api/subcounties-geojson/', views.get_subcounties_geojson, name='get_subcounties_geojson'),
    path('api/wards-geojson/', views.get_wards_geojson, name='get_wards_geojson'),
    
    # ==================== LIST API ENDPOINTS ====================
    path('api/subcounties-list/', views.get_subcounties_list, name='get_subcounties_list'),
    path('api/wards-list/', views.get_wards_list, name='get_wards_list'),
    
    # ==================== MAIN DATA API ====================
    path('api/filtered-water-points/', views.get_filtered_water_points, name='get_filtered_water_points'),
    path('api/water-point/<int:point_id>/', views.get_water_point_by_id, name='get_water_point_by_id'),
    
    # ==================== STATISTICS API ====================
    path('api/subcounty-stats/', views.get_subcounty_stats, name='get_subcounty_stats'),
    
    # ==================== CALCULATION API ====================
    path('api/calculate-distance/', views.calculate_distance, name='calculate_distance'),
    path('api/calculate-area/', views.calculate_area, name='calculate_area'),
    path('api/points-in-polygon/', views.get_points_in_polygon, name='points_in_polygon'),
]