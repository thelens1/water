from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User
from .models import (
    WaterPoint, SubCounty, Ward, County, BoundaryFile, 
    ShapefileUpload, PredictionBatch
)

# ==================== Custom Multiple File Upload Widget ====================

class MultipleFileInput(forms.Widget):
    """Completely custom widget for multiple file uploads"""
    template_name = 'django/forms/widgets/file.html'
    
    def __init__(self, attrs=None):
        if attrs is None:
            attrs = {}
        attrs['multiple'] = True
        super().__init__(attrs)
    
    def format_value(self, value):
        """Return the value as a string."""
        if value is None:
            return ''
        return value
    
    def value_from_datadict(self, data, files, name):
        """Return the list of uploaded files."""
        if hasattr(files, 'getlist'):
            return files.getlist(name)
        return [files.get(name)]
    
    def get_context(self, name, value, attrs):
        """Return the context for rendering the widget."""
        context = super().get_context(name, value, attrs)
        context['widget']['type'] = 'file'
        return context
    
    def use_required_attribute(self, initial):
        """Don't use the required attribute for file inputs."""
        return False

class MultipleFileField(forms.Field):
    """Custom field that handles multiple files"""
    widget = MultipleFileInput
    
    def __init__(self, **kwargs):
        # Set default error messages
        self.error_messages = {
            'required': 'Please select at least one file.',
            'invalid': 'Please upload valid files.',
        }
        super().__init__(**kwargs)
    
    def clean(self, data, initial=None):
        """Validate that we have files and return them."""
        if not data and self.required:
            raise forms.ValidationError(self.error_messages['required'], code='required')
        
        if data is None:
            return []
        
        # Ensure we have a list
        if not isinstance(data, (list, tuple)):
            data = [data]
        
        # Remove any empty values
        data = [f for f in data if f]
        
        if not data and self.required:
            raise forms.ValidationError(self.error_messages['required'], code='required')
        
        return data

# ==================== Authentication Forms ====================

class LoginForm(AuthenticationForm):
    """Custom login form"""
    username = forms.CharField(widget=forms.TextInput(attrs={
        'class': 'form-control',
        'placeholder': 'Username',
        'autofocus': True
    }))
    password = forms.CharField(widget=forms.PasswordInput(attrs={
        'class': 'form-control',
        'placeholder': 'Password'
    }))


class RegisterForm(UserCreationForm):
    """Custom registration form"""
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={
        'class': 'form-control',
        'placeholder': 'Email Address'
    }))
    first_name = forms.CharField(required=False, widget=forms.TextInput(attrs={
        'class': 'form-control',
        'placeholder': 'First Name'
    }))
    last_name = forms.CharField(required=False, widget=forms.TextInput(attrs={
        'class': 'form-control',
        'placeholder': 'Last Name'
    }))
    
    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'password1', 'password2')
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Username'
        })
        self.fields['password1'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Password'
        })
        self.fields['password2'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Confirm Password'
        })
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email and User.objects.filter(email=email).exists():
            raise forms.ValidationError('This email address is already in use.')
        return email


# ==================== Water Point Form ====================

class WaterPointForm(forms.ModelForm):
    """Form for adding/editing water points"""
    
    class Meta:
        model = WaterPoint
        fields = [
            # Basic Information
            'name', 'locality', 'country', 'admin_1',
            'sub_county', 'ward', 'status',
            
            # Location Coordinates
            'latitude', 'longitude', 'elevation',
            
            # Water Point Details
            'yield_field', 'well_depth', 'operation_field',
            'water_rest', 'source_1', 'water_quality',
            
            # Water Quality
            'ph', 'ec', 'temperatur',
            'first_stru', 'second_str', 'third_stru',
            
            # Drilling Information
            'drilling_e', 'installed_year', 'last_maintenance',
            'has_pump', 'pump_type',
        ]
        
        widgets = {
            # Basic Information
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter water point name'}),
            'locality': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Locality/Village name'}),
            'country': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Country', 'value': 'Kenya'}),
            'admin_1': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Admin level 1 (e.g., Turkana)'}),
            'sub_county': forms.Select(attrs={'class': 'form-control', 'id': 'sub_county_select'}),
            'ward': forms.Select(attrs={'class': 'form-control', 'id': 'ward_select'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            
            # Location Coordinates
            'latitude': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'placeholder': 'e.g., 3.5678'}),
            'longitude': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'placeholder': 'e.g., 35.6789'}),
            'elevation': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Elevation in meters'}),
            
            # Water Point Details
            'yield_field': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'placeholder': 'Yield in L/s'}),
            'well_depth': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Well depth in meters'}),
            'operation_field': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Operational status'}),
            'water_rest': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Water restriction'}),
            'source_1': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Data source'}),
            'water_quality': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Good, Fair, Poor'}),
            
            # Water Quality
            'ph': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'placeholder': '0-14'}),
            'ec': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Electrical conductivity'}),
            'temperatur': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Temperature in °C'}),
            'first_stru': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First structure'}),
            'second_str': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Second structure'}),
            'third_stru': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Third structure'}),
            
            # Drilling Information
            'drilling_e': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Drilling entity'}),
            'installed_year': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'YYYY', 'min': 1900, 'max': 2100}),
            'last_maintenance': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'has_pump': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'pump_type': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Hand pump, Solar, Diesel'}),
        }
    
    def clean_latitude(self):
        lat = self.cleaned_data.get('latitude')
        if lat and (lat < -90 or lat > 90):
            raise forms.ValidationError('Latitude must be between -90 and 90')
        return lat
    
    def clean_longitude(self):
        lon = self.cleaned_data.get('longitude')
        if lon and (lon < -180 or lon > 180):
            raise forms.ValidationError('Longitude must be between -180 and 180')
        return lon
    
    def clean_ph(self):
        ph = self.cleaned_data.get('ph')
        if ph and (ph < 0 or ph > 14):
            raise forms.ValidationError('pH must be between 0 and 14')
        return ph


# ==================== Boundary Upload Form ====================

class BoundaryUploadForm(forms.ModelForm):
    """Form for uploading boundary files"""
    class Meta:
        model = BoundaryFile
        fields = ['name', 'description', 'shapefile']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter a name for this boundary file'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Optional description'}),
            'shapefile': forms.FileInput(attrs={'class': 'form-control', 'accept': '.shp,.shx,.dbf,.prj,.zip'}),
        }
    
    def clean_shapefile(self):
        shapefile = self.cleaned_data.get('shapefile')
        if shapefile:
            ext = shapefile.name.split('.')[-1].lower()
            if ext not in ['shp', 'zip']:
                raise forms.ValidationError('Please upload a .shp file or a .zip archive')
            if shapefile.size > 50 * 1024 * 1024:
                raise forms.ValidationError('File size must be less than 50MB')
        return shapefile


# ==================== Shapefile Upload Form ====================

class ShapefileUploadForm(forms.ModelForm):
    """Form for uploading shapefile components"""
    
    # Use custom MultipleFileField
    shapefile_files = MultipleFileField(
        label='Shapefile Files',
        help_text='Select all shapefile component files (.shp, .shx, .dbf, .prj, .cpg)',
        required=True
    )
    
    class Meta:
        model = ShapefileUpload
        fields = ['name', 'description', 'upload_type']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter a name for this upload'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Optional description'
            }),
            'upload_type': forms.Select(attrs={
                'class': 'form-control'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add custom attributes to the file input
        self.fields['shapefile_files'].widget.attrs.update({
            'accept': '.shp,.shx,.dbf,.prj,.cpg,.sbn,.sbx',
            'class': 'form-control'
        })
    
    def clean_shapefile_files(self):
        files = self.cleaned_data.get('shapefile_files')
        
        if not files:
            raise forms.ValidationError('Please select at least one file')
        
        # Check if .shp file is present
        has_shp = any(f.name.endswith('.shp') for f in files)
        if not has_shp:
            raise forms.ValidationError('No .shp file found in upload. A shapefile must include a .shp file.')
        
        # Allowed extensions
        allowed_extensions = ['.shp', '.shx', '.dbf', '.prj', '.cpg', '.sbn', '.sbx']
        
        # Validate each file
        total_size = 0
        for file in files:
            # Check extension
            ext = '.' + file.name.split('.')[-1].lower()
            if ext not in allowed_extensions:
                raise forms.ValidationError(
                    f'File {file.name} has an invalid extension. '
                    f'Allowed: {", ".join(allowed_extensions)}'
                )
            
            # Check file size (max 50MB each)
            if file.size > 50 * 1024 * 1024:
                raise forms.ValidationError(f'File {file.name} is too large. Max size is 50MB.')
            
            total_size += file.size
        
        # Check total size (max 100MB)
        if total_size > 100 * 1024 * 1024:
            raise forms.ValidationError('Total file size must be less than 100MB')
        
        return files
    
    def save(self, commit=True):
        """Save the form instance"""
        instance = super().save(commit=False)
        instance.status = 'pending'
        
        if commit:
            instance.save()
        
        return instance


# ==================== Filter Form ====================

class WaterPointFilterForm(forms.Form):
    """Form for filtering water points"""
    status = forms.ChoiceField(
        choices=[('', 'All Status')] + WaterPoint.STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    sub_county = forms.ModelChoiceField(
        queryset=SubCounty.objects.all().order_by('subcounty'),
        required=False,
        empty_label='All Sub-Counties',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    ward = forms.ModelChoiceField(
        queryset=Ward.objects.all().order_by('ward'),
        required=False,
        empty_label='All Wards',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Search by name or locality'})
    )
    has_pump = forms.NullBooleanField(
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}, choices=[
            ('', 'All'),
            ('true', 'Yes'),
            ('false', 'No')
        ])
    )
    min_depth = forms.FloatField(
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Min depth (m)'})
    )
    max_depth = forms.FloatField(
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Max depth (m)'})
    )


# ==================== Data Export Form ====================

class DataExportForm(forms.Form):
    """Form for exporting data"""
    FORMAT_CHOICES = [
        ('csv', 'CSV'),
        ('json', 'JSON'),
        ('geojson', 'GeoJSON'),
        ('excel', 'Excel'),
    ]
    
    DATA_TYPE_CHOICES = [
        ('water_points', 'Water Points'),
        ('subcounties', 'Sub-Counties'),
        ('wards', 'Wards'),
        ('counties', 'Counties'),
        ('all', 'All Data'),
    ]
    
    STATUS_CHOICES = [
        ('all', 'All Status'),
        ('operational', 'Operational'),
        ('non_operational', 'Non-Operational'),
        ('unknown', 'Unknown'),
    ]
    
    format = forms.ChoiceField(
        choices=FORMAT_CHOICES,
        initial='csv',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    data_type = forms.ChoiceField(
        choices=DATA_TYPE_CHOICES,
        initial='water_points',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    sub_county = forms.ModelChoiceField(
        queryset=SubCounty.objects.all().order_by('subcounty'),
        required=False,
        empty_label='All Sub-Counties',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    ward = forms.ModelChoiceField(
        queryset=Ward.objects.all().order_by('ward'),
        required=False,
        empty_label='All Wards',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        initial='all',
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    include_geometry = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    include_metadata = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    start_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    
    end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    
    filename = forms.CharField(
        required=False,
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Custom filename (optional)'
        })
    )
    
    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        
        if start_date and end_date and start_date > end_date:
            raise forms.ValidationError('Start date must be before end date')
        
        return cleaned_data
    
    def get_filename(self):
        """Generate filename based on form data"""
        filename = self.cleaned_data.get('filename')
        if filename:
            return filename
        
        data_type = self.cleaned_data.get('data_type', 'water_points')
        file_format = self.cleaned_data.get('format', 'csv')
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        
        return f"{data_type}_{timestamp}.{file_format}"


# ==================== Profile Forms ====================

class ProfileUpdateForm(forms.ModelForm):
    """Form for updating user profile"""
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First Name'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last Name'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email Address'}),
        }
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email and User.objects.filter(email=email).exclude(id=self.instance.id).exists():
            raise forms.ValidationError('This email address is already in use.')
        return email


class PasswordChangeForm(forms.Form):
    """Form for changing password"""
    current_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Current Password'})
    )
    new_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'New Password'})
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirm New Password'})
    )
    
    def clean(self):
        cleaned_data = super().clean()
        new_password = cleaned_data.get('new_password')
        confirm_password = cleaned_data.get('confirm_password')
        
        if new_password and confirm_password and new_password != confirm_password:
            raise forms.ValidationError('Passwords do not match.')
        
        return cleaned_data


# ==================== Prediction Form ====================

class PredictionForm(forms.Form):
    """Form for running predictions"""
    name = forms.CharField(
        max_length=200,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter a name for this prediction batch'
        })
    )
    
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Optional description'
        })
    )
    
    model = forms.ModelChoiceField(
        queryset=PredictionBatch.objects.none(),
        required=False,
        empty_label='Use latest active model',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    sub_county = forms.ModelChoiceField(
        queryset=SubCounty.objects.all().order_by('subcounty'),
        required=False,
        empty_label='All Sub-Counties',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    ward = forms.ModelChoiceField(
        queryset=Ward.objects.all().order_by('ward'),
        required=False,
        empty_label='All Wards',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    bounds = forms.CharField(
        required=False,
        widget=forms.HiddenInput()
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # This will be populated in the view with actual models
        from .models import ModelMetadata
        self.fields['model'].queryset = ModelMetadata.objects.filter(is_active=True)


# ==================== System Settings Form ====================

class SystemSettingsForm(forms.Form):
    """Form for system settings"""
    site_title = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    
    default_map_center_lat = forms.FloatField(
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'})
    )
    
    default_map_center_lng = forms.FloatField(
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'})
    )
    
    default_map_zoom = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 20})
    )
    
    items_per_page = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 10, 'max': 500})
    )
    
    enable_predictions = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    enable_export = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    maintenance_mode = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )