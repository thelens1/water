from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.contrib.gis.geos import Point, MultiPolygon, Polygon
from water_app.models import SubCounty, WaterPoint
import random
import math

class Command(BaseCommand):
    help = 'Load sample data for testing'
    
    def handle(self, *args, **kwargs):
        self.stdout.write('Loading sample data...')
        
        # Create superuser if not exists
        if not User.objects.filter(username='admin').exists():
            User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
            self.stdout.write(self.style.SUCCESS('Created admin user'))
        
        # Create sample sub-counties
        counties = ['Nairobi', 'Kiambu', 'Kajiado', 'Machakos', 'Kitui']
        subcounties = []
        
        for i, county in enumerate(counties):
            for j in range(3):  # 3 sub-counties per county
                # Create a simple bounding box polygon
                x = 36.0 + i * 2 + j * 0.5
                y = -1.0 + i * 0.5 + j * 0.2
                
                # Create a polygon (simplified)
                coords = (
                    (x, y),
                    (x + 0.5, y),
                    (x + 0.5, y - 0.5),
                    (x, y - 0.5),
                    (x, y)
                )
                
                polygon = Polygon(coords)
                multipolygon = MultiPolygon([polygon])
                
                subcounty = SubCounty.objects.create(
                    name=f"Sub-County {j+1}",
                    code=f"{county[:3].upper()}{j+1:02d}",
                    county=county,
                    area_sqkm=random.uniform(100, 500),
                    population=random.randint(50000, 200000),
                    geometry=multipolygon
                )
                subcounties.append(subcounty)
                self.stdout.write(f"Created sub-county: {subcounty}")
        
        # Create sample water points
        statuses = ['operational', 'non_operational', 'unknown']
        sources = ['Borehole', 'Well', 'Spring', 'River', 'Dam']
        
        for i in range(200):  # Create 200 sample water points
            # Random coordinates within our sub-county bounds
            lon = 36.0 + random.uniform(0, 10)
            lat = -1.5 + random.uniform(0, 2)
            
            status = random.choices(
                statuses, 
                weights=[0.3, 0.3, 0.4]  # 30% operational, 30% non, 40% unknown
            )[0]
            
            point = WaterPoint.objects.create(
                name=f"Water Point {i+1}",
                sub_county=random.choice(subcounties),
                location=Point(lon, lat),
                latitude=lat,
                longitude=lon,
                elevation=random.uniform(1000, 2000),
                status=status,
                water_source=random.choice(sources),
                water_quality=random.choice(['Good', 'Fair', 'Poor']),
                depth_m=random.uniform(10, 100) if random.random() > 0.3 else None,
                yield_lps=random.uniform(0.5, 5) if random.random() > 0.5 else None,
                has_pump=random.choice([True, False]),
                pump_type=random.choice(['Hand Pump', 'Solar Pump', 'Electric Pump']) if random.random() > 0.5 else '',
                installed_year=random.randint(2000, 2023) if random.random() > 0.5 else None,
                created_by=User.objects.first()
            )
            
            if i % 20 == 0:
                self.stdout.write(f"Created {i} water points...")
        
        self.stdout.write(self.style.SUCCESS(f'Successfully loaded sample data: {SubCounty.objects.count()} sub-counties, {WaterPoint.objects.count()} water points'))