from django.core.management.base import BaseCommand, CommandError
from django.contrib.gis.utils import LayerMapping
from django.contrib.gis.gdal import DataSource
from django.contrib.auth.models import User
from water_app.models import (
    County, SubCounty, Ward, WaterPoint,
    ShapefileUpload, DataImportBatch, UserActivity, BoundaryFile
)
from django.utils import timezone
import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Mapping dictionaries
county_mapping = {
    'county': 'county',
    'pop_2009': 'pop_2009',
    'country': 'country',
    'geom': 'POLYGON',
}

subcounty_mapping = {
    'country': 'country',
    'province': 'province',
    'county': 'county',
    'subcounty': 'subcounty',
    'geom': 'POLYGON',
}

wards_mapping = {
    'county': 'county',
    'subcounty': 'subcounty',
    'ward': 'ward',
    'geom': 'POLYGON',
}

water_points_mapping = {
    'country': 'country',
    'admin_1': 'admin_1',
    'locality': 'locality',
    'latitude': 'latitude',
    'longitude': 'longitude',
    'elevation': 'elevation',
    'yield_field': 'yield',
    'well_depth': 'well_depth',
    'operation_field': 'operation_',
    'drilling_e': 'drilling_e',
    'source_1': 'source_1',
    'first_stru': 'first_stru',
    'second_str': 'second_str',
    'third_stru': 'third_stru',
    'water_rest': 'water_rest',
    'ec': 'ec',
    'ph': 'ph',
    'temperatur': 'temperatur',
    'geom': 'POINT',
}


class Command(BaseCommand):
    help = 'Import shapefiles into the database'

    def add_arguments(self, parser):
        parser.add_argument('shapefile_path', type=str, help='Path to the shapefile')
        parser.add_argument('model_type', type=str, choices=['county', 'subcounty', 'ward', 'water_points'],
                            help='Type of model to import into')
        parser.add_argument('--user_id', type=int, help='User ID for attribution', default=None)
        parser.add_argument('--encoding', type=str, default='utf-8', help='File encoding')
        parser.add_argument('--dry-run', action='store_true', help='Validate without importing')
        parser.add_argument('--clear-existing', action='store_true', help='Clear existing data before import')

    def handle(self, *args, **options):
        shapefile_path = options['shapefile_path']
        model_type = options['model_type']
        user_id = options['user_id']
        encoding = options['encoding']
        dry_run = options['dry_run']
        clear_existing = options['clear_existing']

        # Validate file exists
        if not os.path.exists(shapefile_path):
            raise CommandError(f'Shapefile not found: {shapefile_path}')

        # Get user if provided
        user = None
        if user_id:
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                self.stdout.write(self.style.WARNING(f'User with ID {user_id} not found'))

        try:
            self.stdout.write(self.style.SUCCESS(f'Importing {model_type} from {shapefile_path}...'))
            
            # Get model class
            model_classes = {
                'county': County,
                'subcounty': SubCounty,
                'ward': Ward,
                'water_points': WaterPoint,
            }
            model_class = model_classes[model_type]

            # Get mapping
            mappings = {
                'county': county_mapping,
                'subcounty': subcounty_mapping,
                'ward': wards_mapping,
                'water_points': water_points_mapping,
            }
            mapping = mappings[model_type]

            # Open data source to count features
            ds = DataSource(shapefile_path, encoding=encoding)
            layer = ds[0]
            total_features = len(layer)
            
            self.stdout.write(f'Found {total_features} features to import')

            # Clear existing data if requested
            if clear_existing:
                self.stdout.write(f'Clearing existing {model_type} data...')
                model_class.objects.all().delete()

            # Get count before import
            count_before = model_class.objects.count()
            self.stdout.write(f'Records before import: {count_before}')

            if dry_run:
                self.stdout.write(self.style.SUCCESS('Dry run completed successfully'))
                return

            # Perform import with LayerMapping
            lm = LayerMapping(
                model_class,
                shapefile_path,
                mapping,
                encoding=encoding,
            )
            
            # Import data
            lm.save()
            
            # Get count after import
            count_after = model_class.objects.count()
            imported_count = count_after - count_before
            
            self.stdout.write(self.style.SUCCESS(f'Successfully imported {imported_count} new records'))
            self.stdout.write(f'Total records now: {count_after}')

            # Create import batch record
            batch = DataImportBatch.objects.create(
                name=f"Import {model_type} - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                source_type='shapefile',
                source_file=shapefile_path,
                uploaded_by=user,
                total_records=imported_count,
                successful_imports=imported_count,
                failed_imports=0,
                import_log={
                    'model_type': model_type, 
                    'file': shapefile_path, 
                    'features_in_file': total_features,
                    'count_before': count_before,
                    'count_after': count_after,
                    'imported': imported_count
                }
            )

            # Log activity
            if user:
                UserActivity.objects.create(
                    user=user,
                    activity_type='upload_shapefile',
                    description=f'Imported {imported_count} {model_type} records from shapefile',
                    batch=batch,
                    ip_address='127.0.0.1',
                )

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Import failed: {str(e)}'))
            logger.error(f'Shapefile import failed: {str(e)}', exc_info=True)
            raise CommandError(f'Import failed: {str(e)}')