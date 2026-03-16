from django.core.management.base import BaseCommand
from django.core.serializers import serialize
from water_app.models import WaterPoint, County, SubCounty, Ward
import json
import csv
import os
from datetime import datetime


class Command(BaseCommand):
    help = 'Export data to various formats'

    def add_arguments(self, parser):
        parser.add_argument('model', type=str, choices=['water_points', 'counties', 'subcounties', 'wards'],
                            help='Model to export')
        parser.add_argument('--format', type=str, choices=['geojson', 'json', 'csv'], default='geojson',
                            help='Export format')
        parser.add_argument('--output', type=str, help='Output file path')
        parser.add_argument('--pretty', action='store_true', help='Pretty print JSON')

    def handle(self, *args, **options):
        model_name = options['model']
        export_format = options['format']
        output_file = options['output']
        pretty = options['pretty']

        # Map model names to classes
        models = {
            'water_points': WaterPoint,
            'counties': County,
            'subcounties': SubCounty,
            'wards': Ward,
        }
        model_class = models[model_name]

        # Generate default filename if not provided
        if not output_file:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = f'{model_name}_{timestamp}.{export_format}'

        self.stdout.write(f'Exporting {model_name} to {output_file}...')

        try:
            queryset = model_class.objects.all()
            count = queryset.count()
            self.stdout.write(f'Found {count} records to export')

            if export_format == 'geojson':
                # Export as GeoJSON
                geojson = serialize('geojson', queryset,
                                  geometry_field='geom',
                                  fields=('pk',) + tuple(
                                      [f.name for f in model_class._meta.fields 
                                       if f.name not in ['geom', 'id']]
                                  ))
                
                if pretty:
                    data = json.loads(geojson)
                    with open(output_file, 'w') as f:
                        json.dump(data, f, indent=2)
                else:
                    with open(output_file, 'w') as f:
                        f.write(geojson)

            elif export_format == 'json':
                # Export as JSON
                data = list(queryset.values())
                for item in data:
                    if 'geom' in item:
                        del item['geom']
                
                with open(output_file, 'w') as f:
                    if pretty:
                        json.dump(data, f, indent=2, default=str)
                    else:
                        json.dump(data, f, default=str)

            elif export_format == 'csv':
                # Export as CSV
                fieldnames = [f.name for f in model_class._meta.fields 
                            if f.name not in ['geom']]
                
                with open(output_file, 'w', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    
                    for obj in queryset:
                        row = {}
                        for field in fieldnames:
                            value = getattr(obj, field)
                            row[field] = str(value) if value is not None else ''
                        writer.writerow(row)

            self.stdout.write(self.style.SUCCESS(f'Successfully exported {count} records to {output_file}'))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Export failed: {str(e)}'))