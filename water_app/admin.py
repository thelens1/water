from django.contrib import admin
from django.contrib.gis.admin import GISModelAdmin  # Use GISModelAdmin instead of OSMGeoAdmin
from django.utils.html import format_html
from django.urls import reverse
from django.contrib import messages
from .models import (
    County, SubCounty, Ward, WaterPoint,
    ShapefileUpload, DataImportBatch,
    PredictionBatch, ModelMetadata,
    UserActivity, SystemSettings, Notification
)

# ==================== Base Admin Classes ====================

class BaseGeoAdmin(GISModelAdmin):
    """Base class for geographic admin"""
    default_lon = 35.8
    default_lat = 3.5
    default_zoom = 7
    modifiable = False
    gis_widget_kwargs = {
        'attrs': {
            'default_zoom': 7,
            'default_lon': 35.8,
            'default_lat': 3.5,
        }
    }


# ==================== Spatial Data Admins ====================

@admin.register(County)
class CountyAdmin(BaseGeoAdmin):
    list_display = ['county', 'pop_2009', 'country', 'area_display']
    list_filter = ['country']
    search_fields = ['county', 'country']
    readonly_fields = ['created_at', 'updated_at']
    
    def area_display(self, obj):
        if obj.geom:
            # Transform area from degrees to approximate square kilometers
            # This is a rough approximation - for accurate area use proper projections
            area_deg = obj.geom.area
            # Rough conversion: 1 degree ≈ 111 km at equator
            area_km2 = area_deg * 111 * 111
            return f"{area_km2:.2f} km²"
        return "N/A"
    area_display.short_description = "Area (km²)"


@admin.register(SubCounty)
class SubCountyAdmin(BaseGeoAdmin):
    list_display = ['subcounty', 'county', 'province', 'country', 'water_points_count', 'area_display']
    list_filter = ['county', 'province']
    search_fields = ['subcounty', 'county', 'province']
    readonly_fields = ['created_at', 'updated_at']
    
    def area_display(self, obj):
        if obj.geom:
            area_deg = obj.geom.area
            area_km2 = area_deg * 111 * 111
            return f"{area_km2:.2f} km²"
        return "N/A"
    area_display.short_description = "Area (km²)"
    
    def water_points_count(self, obj):
        count = WaterPoint.objects.filter(sub_county=obj).count()
        url = reverse('admin:water_app_waterpoint_changelist') + f'?sub_county__id__exact={obj.id}'
        return format_html('<a href="{}">{}</a>', url, count)
    water_points_count.short_description = "Water Points"


@admin.register(Ward)
class WardAdmin(BaseGeoAdmin):
    list_display = ['ward', 'subcounty', 'county']
    list_filter = ['county', 'subcounty']
    search_fields = ['ward', 'subcounty', 'county']
    readonly_fields = ['created_at', 'updated_at']


# ==================== Water Point Admin ====================

@admin.register(WaterPoint)
class WaterPointAdmin(BaseGeoAdmin):
    list_display = [
        'name_display', 'locality', 'sub_county', 'ward',
        'status_colored', 'depth_display', 'yield_display',
        'operation_field', 'created_at_short'
    ]
    list_filter = [
        'status', 'source', 'has_pump', 'sub_county__county',
        'operation_field', 'source_1', 'created_at'
    ]
    search_fields = [
        'name', 'locality', 'country', 'admin_1',
        'water_rest', 'source_1'
    ]
    readonly_fields = [
        'id', 'created_at', 'updated_at', 'prediction_date',
        'location_link', 'geometry_preview'
    ]
    list_per_page = 50
    
    # Organize fields into sections
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'name', 'locality', 'country', 'admin_1',
                'sub_county', 'ward', 'status'
            )
        }),
        ('Location Coordinates', {
            'fields': (
                'latitude', 'longitude', 'elevation',
                'location_link', 'geometry_preview'
            )
        }),
        ('Water Point Details', {
            'fields': (
                'yield_field', 'well_depth', 'operation_field',
                'water_rest', 'source_1', 'water_quality'
            )
        }),
        ('Water Quality', {
            'fields': (
                'ph', 'ec', 'temperatur',
                'first_stru', 'second_str', 'third_stru'
            )
        }),
        ('Drilling Information', {
            'fields': (
                'drilling_e', 'installed_year', 'last_maintenance',
                'has_pump', 'pump_type'
            )
        }),
        ('Environmental Factors', {
            'fields': (
                'annual_rainfall_mm', 'soil_type',
                'distance_to_road_m', 'distance_to_water_m',
                'distance_to_settlement_m'
            ),
            'classes': ('collapse',)
        }),
        ('Prediction Results', {
            'fields': (
                'predicted_status', 'prediction_probability',
                'suitability_score', 'prediction_date'
            ),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': (
                'id', 'source', 'import_batch',
                'created_by', 'created_at', 'updated_at'
            ),
            'classes': ('collapse',)
        }),
    )
    
    def name_display(self, obj):
        return obj.name or obj.locality or f"WP-{str(obj.id)[:8]}"
    name_display.short_description = "Name"
    
    def status_colored(self, obj):
        colors = {
            'operational': '#28a745',
            'non_operational': '#dc3545',
            'unknown': '#ffc107'
        }
        color = colors.get(obj.status, '#6c757d')
        status_text = obj.get_status_display() if obj.status else 'Unknown'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, status_text
        )
    status_colored.short_description = "Status"
    
    def depth_display(self, obj):
        depth = obj.depth_m_value
        if depth:
            return f"{depth:.1f} m"
        return obj.well_depth or "N/A"
    depth_display.short_description = "Depth"
    
    def yield_display(self, obj):
        if obj.yield_field:
            return f"{obj.yield_field:.2f} L/s"
        return "N/A"
    yield_display.short_description = "Yield"
    
    def created_at_short(self, obj):
        return obj.created_at.strftime("%Y-%m-%d") if obj.created_at else "N/A"
    created_at_short.short_description = "Created"
    
    def location_link(self, obj):
        if obj.latitude and obj.longitude:
            return format_html(
                '<a href="https://www.google.com/maps?q={},{}" target="_blank">View on Google Maps</a>',
                obj.latitude, obj.longitude
            )
        return "No coordinates"
    location_link.short_description = "Map Link"
    
    def geometry_preview(self, obj):
        if obj.geom:
            return format_html(
                '<div style="height: 200px; width: 100%; background: #f8f9fa; '
                'border-radius: 5px; padding: 10px;">'
                '<strong>Point:</strong> ({:.4f}, {:.4f})</div>',
                obj.geom.y, obj.geom.x
            )
        return "No geometry"
    geometry_preview.short_description = "Geometry Preview"


# ==================== Import/Upload Admins ====================

@admin.register(ShapefileUpload)
class ShapefileUploadAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'upload_type', 'status_colored',
        'uploaded_by', 'uploaded_at', 'progress'
    ]
    list_filter = ['status', 'upload_type', 'uploaded_at']
    search_fields = ['name', 'description', 'uploaded_by__username']
    readonly_fields = ['uploaded_at', 'processed_at']
    
    def status_colored(self, obj):
        colors = {
            'completed': 'green',
            'processing': 'blue',
            'pending': 'orange',
            'failed': 'red'
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.get_status_display()
        )
    status_colored.short_description = "Status"
    
    def progress(self, obj):
        if obj.total_features and obj.total_features > 0:
            imported = obj.imported_count or 0
            percentage = (imported / obj.total_features) * 100
            return format_html(
                '<div style="width: 100px; background: #f0f0f0; border-radius: 3px;">'
                '<div style="height: 20px; width: {}%; background: #28a745; '
                'border-radius: 3px; text-align: center; color: white; font-size: 12px; line-height: 20px;">'
                '{}%</div></div>',
                percentage, int(percentage)
            )
        return "N/A"
    progress.short_description = "Progress"


@admin.register(DataImportBatch)
class DataImportBatchAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'batch_id_short', 'source_type',
        'uploaded_by', 'uploaded_at', 'stats'
    ]
    list_filter = ['source_type', 'uploaded_at']
    search_fields = ['name', 'batch_id', 'uploaded_by__username']
    readonly_fields = ['batch_id', 'uploaded_at', 'completed_at', 'import_log', 'error_log']
    
    def batch_id_short(self, obj):
        return str(obj.batch_id)[:8] + "..."
    batch_id_short.short_description = "Batch ID"
    
    def stats(self, obj):
        return format_html(
            '<span style="color: #28a745;">✓ {}</span> / '
            '<span style="color: #dc3545;">✗ {}</span> / '
            '<span style="font-weight: bold;">∑ {}</span>',
            obj.successful_imports or 0, obj.failed_imports or 0, obj.total_records or 0
        )
    stats.short_description = "Import Stats"


# ==================== ML Model Admins ====================

@admin.register(PredictionBatch)
class PredictionBatchAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'status_colored', 'created_by',
        'created_at', 'completed_at', 'results'
    ]
    list_filter = ['status', 'created_at']
    search_fields = ['name', 'description', 'created_by__username']
    readonly_fields = ['created_at', 'completed_at']
    
    def status_colored(self, obj):
        colors = {
            'completed': 'green',
            'processing': 'blue',
            'pending': 'orange',
            'failed': 'red'
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.get_status_display()
        )
    status_colored.short_description = "Status"
    
    def results(self, obj):
        if obj.total_points:
            return format_html(
                'Op: {} / Non: {} / Total: {}',
                obj.operational_predicted or 0, obj.non_operational_predicted or 0, obj.total_points
            )
        return "N/A"
    results.short_description = "Results"


@admin.register(ModelMetadata)
class ModelMetadataAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'model_type', 'version', 'active_badge',
        'accuracy', 'f1_score', 'created_at'
    ]
    list_filter = ['model_type', 'is_active', 'created_at']
    search_fields = ['name', 'version', 'description']
    readonly_fields = ['created_at']
    
    def active_badge(self, obj):
        if obj.is_active:
            return format_html(
                '<span style="background: #28a745; color: white; padding: 3px 8px; '
                'border-radius: 3px; font-weight: bold;">ACTIVE</span>'
            )
        return format_html(
            '<span style="background: #6c757d; color: white; padding: 3px 8px; '
            'border-radius: 3px;">Inactive</span>'
        )
    active_badge.short_description = "Status"
    
    def accuracy(self, obj):
        return f"{obj.accuracy * 100:.1f}%" if obj.accuracy else "N/A"
    
    def f1_score(self, obj):
        return f"{obj.f1_score:.3f}" if obj.f1_score else "N/A"


# ==================== User Activity Admin ====================

@admin.register(UserActivity)
class UserActivityAdmin(admin.ModelAdmin):
    list_display = ['user', 'activity_type', 'description_short', 'timestamp', 'ip_address']
    list_filter = ['activity_type', 'timestamp', 'user']
    search_fields = ['user__username', 'description']
    readonly_fields = ['timestamp', 'user_agent']
    date_hierarchy = 'timestamp'
    
    def description_short(self, obj):
        return obj.description[:50] + "..." if len(obj.description) > 50 else obj.description
    description_short.short_description = "Description"
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False


# ==================== System Settings Admin ====================

@admin.register(SystemSettings)
class SystemSettingsAdmin(admin.ModelAdmin):
    list_display = ['key', 'value_preview', 'updated_by', 'updated_at']
    search_fields = ['key', 'description']
    readonly_fields = ['updated_at']
    
    def value_preview(self, obj):
        val = str(obj.value)
        return val[:50] + "..." if len(val) > 50 else val
    value_preview.short_description = "Value"


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['title', 'priority_colored', 'user', 'is_global', 'is_read', 'created_at']
    list_filter = ['priority', 'is_read', 'is_global', 'created_at']
    search_fields = ['title', 'message', 'user__username']
    readonly_fields = ['created_at', 'read_at']
    
    def priority_colored(self, obj):
        colors = {
            'urgent': 'red',
            'high': 'orange',
            'normal': 'blue',
            'low': 'green'
        }
        color = colors.get(obj.priority, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.get_priority_display()
        )
    priority_colored.short_description = "Priority"


# ==================== Custom Admin Site Configuration ====================

# Customize admin site
admin.site.site_header = 'Water Point System Administration'
admin.site.site_title = 'Water Point Admin'
admin.site.index_title = 'Dashboard'
admin.site.site_url = '/'