from django.contrib.gis.db import models as gis_models
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import uuid

# ==================== Spatial Data Models ====================

class County(models.Model):
    """Model for county boundaries from county.shp"""
    county = models.CharField(max_length=254, null=True, blank=True)
    pop_2009 = models.BigIntegerField(null=True, blank=True)
    country = models.CharField(max_length=5, null=True, blank=True)
    geom = gis_models.MultiPolygonField(srid=4326, null=True, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name_plural = "Counties"
        indexes = [
            models.Index(fields=['county']),
        ]
    
    def __str__(self):
        return self.county or f"County {self.id}"


class SubCounty(models.Model):
    """Model for sub-county boundaries from subcounty.shp"""
    country = models.CharField(max_length=254, null=True, blank=True)
    province = models.CharField(max_length=254, null=True, blank=True)
    county = models.CharField(max_length=254, null=True, blank=True)
    subcounty = models.CharField(max_length=254, null=True, blank=True)
    geom = gis_models.MultiPolygonField(srid=4326, null=True, blank=True)
    
    # Additional calculated fields
    area_sqkm = models.FloatField(null=True, blank=True)
    population = models.IntegerField(null=True, blank=True)
    water_points_count = models.IntegerField(default=0, null=True, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name_plural = "Sub Counties"
        indexes = [
            models.Index(fields=['county']),
            models.Index(fields=['subcounty']),
        ]
    
    def __str__(self):
        return self.subcounty or f"SubCounty {self.id}"


class Ward(models.Model):
    """Model for ward boundaries from wards.shp"""
    county = models.CharField(max_length=40, null=True, blank=True)
    subcounty = models.CharField(max_length=80, null=True, blank=True)
    ward = models.CharField(max_length=80, null=True, blank=True)
    geom = gis_models.MultiPolygonField(srid=4326, null=True, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name_plural = "Wards"
        indexes = [
            models.Index(fields=['county']),
            models.Index(fields=['subcounty']),
            models.Index(fields=['ward']),
        ]
    
    def __str__(self):
        return self.ward or f"Ward {self.id}"


# ==================== Water Points Model ====================

class WaterPoint(models.Model):
    """Model for water points from water_points.shp with all fields"""
    
    STATUS_CHOICES = [
        ('operational', 'Operational'),
        ('non_operational', 'Non-Operational'),
        ('unknown', 'Unknown'),
    ]
    
    SOURCE_CHOICES = [
        ('field_survey', 'Field Survey'),
        ('bulk_upload', 'Bulk Upload'),
        ('api_import', 'API Import'),
        ('manual_entry', 'Manual Entry'),
        ('shapefile', 'Shapefile Import'),
    ]
    
    # Original fields from shapefile (all nullable)
    id = models.BigAutoField(primary_key=True)
    country = models.CharField(max_length=254, null=True, blank=True)
    admin_1 = models.CharField(max_length=254, null=True, blank=True)
    locality = models.CharField(max_length=254, null=True, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    elevation = models.CharField(max_length=254, null=True, blank=True)
    yield_field = models.FloatField(null=True, blank=True, db_column='yield')
    well_depth = models.CharField(max_length=254, null=True, blank=True)
    operation_field = models.CharField(max_length=254, null=True, blank=True, db_column='operation_')
    drilling_e = models.CharField(max_length=254, null=True, blank=True)
    source_1 = models.CharField(max_length=254, null=True, blank=True)
    first_stru = models.CharField(max_length=254, null=True, blank=True)
    second_str = models.CharField(max_length=254, null=True, blank=True)
    third_stru = models.CharField(max_length=254, null=True, blank=True)
    water_rest = models.CharField(max_length=254, null=True, blank=True)
    ec = models.BigIntegerField(null=True, blank=True)
    ph = models.FloatField(null=True, blank=True)
    temperatur = models.CharField(max_length=254, null=True, blank=True)
    geom = gis_models.PointField(srid=4326, geography=True, null=True, blank=True)
    
    # Additional fields for enhanced functionality
    name = models.CharField(max_length=200, null=True, blank=True)
    sub_county = models.ForeignKey('SubCounty', on_delete=models.SET_NULL, null=True, blank=True)
    ward = models.ForeignKey('Ward', on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='unknown', null=True, blank=True)
    water_quality = models.CharField(max_length=50, null=True, blank=True)
    
    # Infrastructure
    has_pump = models.BooleanField(default=False, null=True, blank=True)
    pump_type = models.CharField(max_length=100, null=True, blank=True)
    installed_year = models.IntegerField(null=True, blank=True)
    last_maintenance = models.DateField(null=True, blank=True)
    
    # Environmental factors (calculated)
    annual_rainfall_mm = models.FloatField(null=True, blank=True)
    soil_type = models.CharField(max_length=100, null=True, blank=True)
    distance_to_road_m = models.FloatField(null=True, blank=True)
    distance_to_water_m = models.FloatField(null=True, blank=True)
    distance_to_settlement_m = models.FloatField(null=True, blank=True)
    
    # Metadata
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='shapefile', null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    import_batch = models.CharField(max_length=100, null=True, blank=True)
    
    # Prediction fields
    predicted_status = models.CharField(max_length=20, null=True, blank=True)
    prediction_probability = models.FloatField(null=True, blank=True)
    prediction_date = models.DateTimeField(null=True, blank=True)
    suitability_score = models.FloatField(null=True, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['sub_county']),
            models.Index(fields=['ward']),
            models.Index(fields=['country']),
            models.Index(fields=['admin_1']),
            models.Index(fields=['locality']),
            models.Index(fields=['created_at']),
            models.Index(fields=['operation_field']),
            models.Index(fields=['source_1']),
        ]
    
    def __str__(self):
        return self.name or self.locality or f"Water Point {self.id}"
    
    def save(self, *args, **kwargs):
        # Auto-classify status from operation_field if status is unknown or not set
        if not self.status or self.status == 'unknown':
            self.status = self.classify_operational_from_operation_field()
        
        # Auto-populate lat/long from geometry
        if self.geom and not (self.latitude and self.longitude):
            self.longitude = self.geom.x
            self.latitude = self.geom.y
        # Or create geometry from lat/long
        elif self.latitude and self.longitude and not self.geom:
            from django.contrib.gis.geos import Point
            self.geom = Point(self.longitude, self.latitude, srid=4326)
        
        super().save(*args, **kwargs)
    
    @property
    def depth_m_value(self):
        """Convert well_depth string to float if possible"""
        if self.well_depth and str(self.well_depth).replace('.', '').replace('-', '').isdigit():
            try:
                return float(self.well_depth)
            except (ValueError, TypeError):
                return None
        return None
    
    @property
    def depth_m(self):
        """Alias for depth_m_value for template compatibility"""
        return self.depth_m_value
    
    @property
    def yield_value(self):
        """Return yield field value"""
        return self.yield_field
    
    @property
    def is_operational(self):
        """Return True if water point is operational"""
        return self.status == 'operational'
    
    @property
    def is_non_operational(self):
        """Return True if water point is non-operational"""
        return self.status == 'non_operational'
    
    @property
    def has_valid_coordinates(self):
        """Check if water point has valid coordinates"""
        return self.latitude and self.longitude and \
               -90 <= self.latitude <= 90 and -180 <= self.longitude <= 180
    
    def classify_operational_from_operation_field(self):
        """Classify operational status based on operation_field value"""
        if not self.operation_field:
            return 'unknown'
        
        v = str(self.operation_field).strip().lower()
        
        # Operational indicators
        operational_keywords = [
            "operational", "y", "pump installed", "hand pump", 
            "installed", "functional", "working", "yes", "good",
            "active", "in use", "functioning", "ok", "works"
        ]
        
        # Non-operational indicators
        non_operational_keywords = [
            "dry", "dry hole", "dry well", "blocked", "salty", 
            "abandoned", "no water", "insufficient", "broken", 
            "non functional", "not working", "damaged", "failed",
            "not operational", "non-operational", "nonfunctional",
            "needs repair", "broken down", "not in use", "closed"
        ]
        
        # Check operational first (more specific)
        for word in operational_keywords:
            if word in v:
                return 'operational'
        
        # Check non-operational
        for word in non_operational_keywords:
            if word in v:
                return 'non_operational'
        
        # Try to interpret common patterns
        if v in ['0', 'no', 'n', 'false']:
            return 'non_operational'
        if v in ['1', 'yes', 'y']:
            return 'operational'
        
        # Default
        return 'unknown'
    
    @classmethod
    def update_all_status_from_operation_field(cls, dry_run=False):
        """
        Update all water points status based on operation_field
        
        Args:
            dry_run (bool): If True, only count how many would be updated without saving
            
        Returns:
            dict: Statistics about the update operation
        """
        water_points = cls.objects.all()
        stats = {
            'total': water_points.count(),
            'updated': 0,
            'operational': 0,
            'non_operational': 0,
            'unknown': 0,
            'skipped': 0
        }
        
        for wp in water_points:
            old_status = wp.status
            new_status = wp.classify_operational_from_operation_field()
            
            if old_status != new_status:
                stats['updated'] += 1
                if not dry_run:
                    wp.status = new_status
                    wp.save()
            
            # Count by new status
            if new_status == 'operational':
                stats['operational'] += 1
            elif new_status == 'non_operational':
                stats['non_operational'] += 1
            else:
                stats['unknown'] += 1
        
        return stats
    
    @classmethod
    def get_statistics(cls, sub_county=None, ward=None):
        """
        Get statistics for water points
        
        Args:
            sub_county: Optional SubCounty instance to filter by
            ward: Optional Ward instance to filter by
            
        Returns:
            dict: Statistics dictionary
        """
        queryset = cls.objects.all()
        
        if sub_county:
            queryset = queryset.filter(sub_county=sub_county)
        if ward:
            queryset = queryset.filter(ward=ward)
        
        total = queryset.count()
        operational = queryset.filter(status='operational').count()
        non_operational = queryset.filter(status='non_operational').count()
        unknown = queryset.filter(status='unknown').count()
        
        # Calculate average depth (convert strings to floats)
        depths = []
        for wp in queryset.exclude(well_depth__isnull=True).exclude(well_depth=''):
            depth_value = wp.depth_m_value
            if depth_value is not None:
                depths.append(depth_value)
        
        avg_depth = sum(depths) / len(depths) if depths else None
        
        # Calculate average yield
        yields = queryset.exclude(yield_field__isnull=True).values_list('yield_field', flat=True)
        yields = [y for y in yields if y is not None]
        avg_yield = sum(yields) / len(yields) if yields else None
        
        return {
            'total': total,
            'operational': operational,
            'non_operational': non_operational,
            'unknown': unknown,
            'operational_percent': round((operational / total * 100), 1) if total > 0 else 0,
            'avg_depth': round(avg_depth, 1) if avg_depth else None,
            'avg_yield': round(avg_yield, 2) if avg_yield else None,
        }
    
    @classmethod
    def get_points_in_bounds(cls, min_lng, min_lat, max_lng, max_lat):
        """
        Get water points within specified bounds
        
        Args:
            min_lng, min_lat, max_lng, max_lat: Bounding box coordinates
            
        Returns:
            QuerySet of WaterPoint objects
        """
        return cls.objects.filter(
            latitude__gte=min_lat,
            latitude__lte=max_lat,
            longitude__gte=min_lng,
            longitude__lte=max_lng
        )
    
    @classmethod
    def get_nearby_points(cls, latitude, longitude, radius_km=5):
        """
        Get water points within radius of a point
        
        Args:
            latitude, longitude: Center point
            radius_km: Radius in kilometers
            
        Returns:
            QuerySet of WaterPoint objects
        """
        # Approximate conversion: 1 degree ≈ 111 km
        deg_radius = radius_km / 111.0
        
        return cls.objects.filter(
            latitude__range=(latitude - deg_radius, latitude + deg_radius),
            longitude__range=(longitude - deg_radius, longitude + deg_radius)
        ).exclude(
            latitude=latitude,
            longitude=longitude
        )
    
    def get_nearby_points_for_this(self, radius_km=5):
        """Get water points near this one"""
        if not self.has_valid_coordinates:
            return cls.objects.none()
        return self.__class__.get_nearby_points(
            self.latitude, self.longitude, radius_km
        ).exclude(id=self.id)
    
    def to_geojson(self):
        """Return GeoJSON representation of this water point"""
        if not self.has_valid_coordinates:
            return None
        
        return {
            'type': 'Feature',
            'geometry': {
                'type': 'Point',
                'coordinates': [self.longitude, self.latitude]
            },
            'properties': {
                'id': self.id,
                'name': self.name or self.locality,
                'locality': self.locality,
                'status': self.status,
                'status_display': self.get_status_display(),
                'sub_county': self.sub_county.subcounty if self.sub_county else None,
                'ward': self.ward.ward if self.ward else None,
                'depth': self.well_depth,
                'depth_value': self.depth_m_value,
                'yield': self.yield_field,
                'has_pump': self.has_pump,
                'source': self.source_1,
                'operation_field': self.operation_field,
                'ph': self.ph,
                'ec': self.ec,
                'created_at': self.created_at.isoformat() if self.created_at else None,
                'predicted_status': self.predicted_status,
            }
        }
    
    @classmethod
    def to_geojson_collection(cls, queryset=None):
        """Return GeoJSON FeatureCollection of water points"""
        if queryset is None:
            queryset = cls.objects.all()
        
        features = []
        for point in queryset:
            geojson = point.to_geojson()
            if geojson:
                features.append(geojson)
        
        return {
            'type': 'FeatureCollection',
            'features': features,
            'total_count': queryset.count(),
            'returned_count': len(features)
        }

    def classify_from_operation_field(self):
        """Classify operational status based on operation_field"""
        if not self.operation_field:
            return 'unknown'
        
        v = str(self.operation_field).strip().lower()
        
        # Operational indicators
        operational_keywords = [
            "operational", "y", "pump installed", "hand pump", "installed",
            "functional", "working", "yes", "good", "active"
        ]
        
        # Non-operational indicators
        non_operational_keywords = [
            "dry", "dry hole", "dry well", "blocked", "salty",
            "abandoned", "no water", "insufficient", "broken",
            "non functional", "not working", "damaged"
        ]
        
        # Check operational
        for word in operational_keywords:
            if word in v:
                return 'operational'
        
        # Check non-operational
        for word in non_operational_keywords:
            if word in v:
                return 'non_operational'
        
        return 'non_operational'  # Default
    
    def save(self, *args, **kwargs):
        # Auto-classify if status is not set
        if not self.status or self.status == 'unknown':
            self.status = self.classify_from_operation_field()
        super().save(*args, **kwargs)


# ==================== Upload/Import Models ====================

class ShapefileUpload(models.Model):
    """Model for uploaded shapefiles"""
    UPLOAD_TYPE_CHOICES = [
        ('water_points', 'Water Points'),
        ('county', 'County Boundaries'),
        ('subcounty', 'Sub-County Boundaries'),
        ('ward', 'Ward Boundaries'),
        ('custom', 'Custom'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    upload_type = models.CharField(max_length=20, choices=UPLOAD_TYPE_CHOICES, default='custom')
    
    # Files
    shapefile = models.FileField(upload_to='uploads/shapefiles/', null=True, blank=True)
    shx_file = models.FileField(upload_to='uploads/shapefiles/', null=True, blank=True)
    dbf_file = models.FileField(upload_to='uploads/shapefiles/', null=True, blank=True)
    prj_file = models.FileField(upload_to='uploads/shapefiles/', null=True, blank=True)
    
    # Metadata
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    error_message = models.TextField(blank=True, null=True)
    
    # Statistics
    total_features = models.IntegerField(default=0, null=True, blank=True)
    imported_count = models.IntegerField(default=0, null=True, blank=True)
    failed_count = models.IntegerField(default=0, null=True, blank=True)
    
    class Meta:
        verbose_name_plural = "Shapefile Uploads"
        ordering = ['-uploaded_at']
    
    def __str__(self):
        return f"{self.name} - {self.uploaded_at.strftime('%Y-%m-%d %H:%M')}"


class DataImportBatch(models.Model):
    """Track bulk data imports"""
    SOURCE_CHOICES = [
        ('shapefile', 'Shapefile'),
        ('csv', 'CSV'),
        ('excel', 'Excel'),
        ('json', 'JSON'),
        ('api', 'API'),
    ]
    
    batch_id = models.CharField(max_length=100, unique=True, default=uuid.uuid4)
    name = models.CharField(max_length=200)
    source_type = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    
    # Files
    source_file = models.FileField(upload_to='uploads/imports/', null=True, blank=True)
    
    # Metadata
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Statistics
    total_records = models.IntegerField(default=0)
    successful_imports = models.IntegerField(default=0)
    failed_imports = models.IntegerField(default=0)
    
    # Logs
    import_log = models.JSONField(null=True, blank=True)
    error_log = models.JSONField(null=True, blank=True)
    
    class Meta:
        ordering = ['-uploaded_at']
    
    def __str__(self):
        return f"{self.name} - {self.uploaded_at.strftime('%Y-%m-%d %H:%M')}"


# ==================== ML Models ====================

class PredictionBatch(models.Model):
    """Track batch predictions"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    name = models.CharField(max_length=200, default=f"Prediction Batch {timezone.now().strftime('%Y%m%d')}")
    description = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Area of interest (GeoJSON)
    area_of_interest = models.JSONField(null=True, blank=True)
    
    # Statistics
    total_points = models.IntegerField(default=0, null=True, blank=True)
    operational_predicted = models.IntegerField(default=0, null=True, blank=True)
    non_operational_predicted = models.IntegerField(default=0, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Results
    results_summary = models.JSONField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"


class ModelMetadata(models.Model):
    """Store information about ML models - WITH DEFAULTS ADDED"""
    MODEL_TYPE_CHOICES = [
        ('random_forest', 'Random Forest'),
        ('xgboost', 'XGBoost'),
        ('lightgbm', 'LightGBM'),
        ('ensemble', 'Ensemble'),
        ('neural_network', 'Neural Network'),
    ]
    
    name = models.CharField(max_length=200, default='Default Model')
    model_type = models.CharField(max_length=20, choices=MODEL_TYPE_CHOICES, default='ensemble')
    version = models.CharField(max_length=50, default='1.0.0')
    description = models.TextField(null=True, blank=True, default='No description provided')
    
    # File paths
    file_path = models.FileField(upload_to='models/', null=True, blank=True)
    
    # Performance metrics
    accuracy = models.FloatField(null=True, blank=True, default=0.0)
    precision = models.FloatField(null=True, blank=True, default=0.0)
    recall = models.FloatField(null=True, blank=True, default=0.0)
    f1_score = models.FloatField(null=True, blank=True, default=0.0)
    roc_auc = models.FloatField(null=True, blank=True, default=0.0)
    
    # Feature importance
    feature_importance = models.JSONField(null=True, blank=True, default=dict)
    performance_metrics = models.JSONField(null=True, blank=True, default=dict)
    
    # Metadata
    is_active = models.BooleanField(default=False)
    training_date = models.DateTimeField(null=True, blank=True)
    training_samples = models.IntegerField(null=True, blank=True, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name_plural = "Model Metadata"
        ordering = ['-is_active', '-created_at']
    
    def __str__(self):
        return f"{self.name} v{self.version}"


# ==================== User Activity ====================

class UserActivity(models.Model):
    """Track user activities"""
    ACTIVITY_TYPES = [
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('view_map', 'View Map'),
        ('add_point', 'Add Water Point'),
        ('edit_point', 'Edit Water Point'),
        ('delete_point', 'Delete Water Point'),
        ('upload_shapefile', 'Upload Shapefile'),
        ('run_prediction', 'Run Prediction'),
        ('export_data', 'Export Data'),
        ('view_report', 'View Report'),
        ('settings_change', 'Settings Change'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    activity_type = models.CharField(max_length=50, choices=ACTIVITY_TYPES, default='view_map')
    description = models.TextField(default='No description')
    
    # Additional context
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True, default='')
    location = models.JSONField(null=True, blank=True, default=dict)  # Store lat/long if available
    
    # Related objects
    water_point = models.ForeignKey(WaterPoint, on_delete=models.SET_NULL, null=True, blank=True)
    batch = models.ForeignKey(DataImportBatch, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Timestamp
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name_plural = "User Activities"
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', '-timestamp']),
            models.Index(fields=['activity_type']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.activity_type} - {self.timestamp.strftime('%Y-%m-%d %H:%M')}"


# ==================== System Settings ====================

class SystemSettings(models.Model):
    """Store system-wide settings"""
    key = models.CharField(max_length=100, unique=True)
    value = models.JSONField(default=dict)
    description = models.TextField(null=True, blank=True, default='')
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name_plural = "System Settings"
    
    def __str__(self):
        return self.key


class Notification(models.Model):
    """System notifications"""
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    
    title = models.CharField(max_length=200, default='Notification')
    message = models.TextField(default='')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='normal')
    
    # Recipients
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    is_global = models.BooleanField(default=False)
    
    # Status
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_notifications')
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return self.title


class BoundaryFile(models.Model):
    """Model for uploaded boundary shapefiles"""
    name = models.CharField(max_length=200, default='Boundary File')
    description = models.TextField(blank=True, null=True, default='')
    shapefile = models.FileField(upload_to='boundaries/', null=True, blank=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    is_processed = models.BooleanField(default=False)
    
    # Additional fields for processing
    processed_at = models.DateTimeField(null=True, blank=True)
    feature_count = models.IntegerField(default=0, null=True, blank=True)
    error_message = models.TextField(blank=True, null=True, default='')
    
    class Meta:
        verbose_name_plural = "Boundary Files"
        ordering = ['-uploaded_at']
    
    def __str__(self):
        return self.name