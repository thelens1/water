# water_app/ml_service_ensemble.py

import joblib
import numpy as np
import pandas as pd
from django.conf import settings
import os
import logging
import json
from datetime import datetime
from sklearn.preprocessing import RobustScaler
from django.contrib.gis.geos import Point
from django.db.models import Q, Count, Avg
from .models import WaterPoint, SubCounty, Ward, PredictionBatch, ModelMetadata
from scipy.spatial import cKDTree
import math

# Import required classes for loading
from sklearn.ensemble import RandomForestClassifier
from sklearn.pipeline import Pipeline
try:
    from imblearn.pipeline import Pipeline as ImbPipeline
except ImportError:
    ImbPipeline = Pipeline
import xgboost as xgb
import lightgbm as lgb

logger = logging.getLogger(__name__)

class EnsembleMLService:
    """
    ML Service that loads individual models and performs ensemble predictions
    with advanced feature engineering and explanations
    """
    
    _instance = None
    _rf_model = None
    _xgb_model = None
    _lgbm_model = None
    _weights = None
    _feature_names = None
    _threshold = None
    _scaler = None
    _metrics = None
    _feature_importance = None
    _training_info = None
    _all_water_points = None
    _water_points_coords = None
    _water_points_tree = None
    _kmeans_model = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_models()
            cls._instance._load_water_points_for_sampling()
        return cls._instance
    
    def _load_models(self):
        """Load all individual models and ensemble components"""
        try:
            model_dir = os.path.join(settings.BASE_DIR, 'water_app', 'ml_models')
            
            # First, load the ensemble components to get metadata
            ensemble_path = os.path.join(model_dir, 'latest_ensemble.joblib')
            
            if not os.path.exists(ensemble_path):
                # Try to find any ensemble components file
                files = os.listdir(model_dir)
                ensemble_files = [f for f in files if f.startswith('ensemble_components_') and f.endswith('.joblib')]
                if ensemble_files:
                    ensemble_path = os.path.join(model_dir, sorted(ensemble_files)[-1])
                    print(f"🔍 Found ensemble components: {ensemble_path}")
                else:
                    logger.error("❌ No ensemble components file found")
                    return
            
            print(f"📦 Loading ensemble components from: {ensemble_path}")
            ensemble_components = joblib.load(ensemble_path)
            
            self._weights = ensemble_components.get('weights')
            self._feature_names = ensemble_components.get('feature_names')
            self._threshold = ensemble_components.get('threshold', 0.213)
            self._scaler = ensemble_components.get('scaler')
            self._metrics = ensemble_components.get('metrics', {})
            self._feature_importance = ensemble_components.get('feature_importance', {})
            self._training_info = ensemble_components.get('training_info', {})
            
            print(f"✅ Ensemble components loaded")
            print(f"   Weights: {self._weights}")
            print(f"   Features: {len(self._feature_names)}")
            print(f"   Threshold: {self._threshold:.4f}")
            
            # Now load individual models
            model_files = self._training_info.get('model_files', {})
            
            # Try to find model files
            rf_path = os.path.join(model_dir, model_files.get('rf', 'rf_model_latest.joblib'))
            xgb_path = os.path.join(model_dir, model_files.get('xgb', 'xgb_model_latest.joblib'))
            lgbm_path = os.path.join(model_dir, model_files.get('lgbm', 'lgbm_model_latest.joblib'))
            
            # If specific files not found, look for latest
            if not os.path.exists(rf_path):
                rf_files = [f for f in os.listdir(model_dir) if f.startswith('rf_model_') and f.endswith('.joblib')]
                if rf_files:
                    rf_path = os.path.join(model_dir, sorted(rf_files)[-1])
            
            if not os.path.exists(xgb_path):
                xgb_files = [f for f in os.listdir(model_dir) if f.startswith('xgb_model_') and f.endswith('.joblib')]
                if xgb_files:
                    xgb_path = os.path.join(model_dir, sorted(xgb_files)[-1])
            
            if not os.path.exists(lgbm_path):
                lgbm_files = [f for f in os.listdir(model_dir) if f.startswith('lgbm_model_') and f.endswith('.joblib')]
                if lgbm_files:
                    lgbm_path = os.path.join(model_dir, sorted(lgbm_files)[-1])
            
            # Load models
            print("\n📦 Loading individual models...")
            
            if os.path.exists(rf_path):
                self._rf_model = joblib.load(rf_path)
                print(f"   ✅ Random Forest loaded from: {os.path.basename(rf_path)}")
            else:
                print(f"   ❌ Random Forest not found at {rf_path}")
            
            if os.path.exists(xgb_path):
                self._xgb_model = joblib.load(xgb_path)
                print(f"   ✅ XGBoost loaded from: {os.path.basename(xgb_path)}")
            else:
                print(f"   ❌ XGBoost not found at {xgb_path}")
            
            if os.path.exists(lgbm_path):
                self._lgbm_model = joblib.load(lgbm_path)
                print(f"   ✅ LightGBM loaded from: {os.path.basename(lgbm_path)}")
            else:
                print(f"   ❌ LightGBM not found at {lgbm_path}")
            
            # Check if all models loaded
            if self._rf_model is None or self._xgb_model is None or self._lgbm_model is None:
                logger.error("❌ Some models failed to load")
                return
            
            logger.info(f"✅ All models loaded successfully!")
            
        except Exception as e:
            logger.error(f"❌ Error loading models: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def _load_water_points_for_sampling(self):
        """Load water points into memory for spatial sampling"""
        try:
            # Get all water points with their features
            self._all_water_points = list(WaterPoint.objects.exclude(
                latitude__isnull=True
            ).exclude(
                longitude__isnull=True
            ).values(
                'id', 'latitude', 'longitude', 'well_depth', 'yield_field', 
                'ph', 'operation_field', 'status', 'distance_to_road_m',
                'distance_to_water_m', 'annual_rainfall_mm'
            ))
            
            if self._all_water_points:
                # Create KD-tree for fast nearest neighbor searches
                coords = np.array([[p['latitude'], p['longitude']] for p in self._all_water_points])
                self._water_points_coords = coords
                self._water_points_tree = cKDTree(coords)
                print(f"✅ Loaded {len(self._all_water_points)} water points for spatial sampling")
                
                # Also create and fit KMeans model for spatial clustering
                from sklearn.cluster import KMeans
                self._kmeans_model = KMeans(n_clusters=5, random_state=42, n_init=10)
                self._kmeans_model.fit(coords)
                print(f"✅ KMeans model fitted with 5 clusters")
        except Exception as e:
            logger.error(f"Error loading water points for sampling: {e}")
    
    def is_ready(self):
        """Check if all models are loaded"""
        return (self._rf_model is not None and 
                self._xgb_model is not None and 
                self._lgbm_model is not None and 
                self._weights is not None)
    
    def get_model_info(self):
        """Get complete model information"""
        if not self.is_ready():
            return {
                'status': 'not_ready',
                'message': 'Models not fully loaded',
                'metrics': self._metrics or {},
                'feature_names': self._feature_names or [],
                'threshold': self._threshold or 0.213
            }
        
        # Sort feature importance for display
        sorted_importance = {}
        if self._feature_importance:
            sorted_importance = dict(sorted(
                self._feature_importance.items(), 
                key=lambda x: x[1], 
                reverse=True
            )[:20])
        
        return {
            'status': 'ready',
            'feature_names': self._feature_names,
            'n_features': len(self._feature_names) if self._feature_names else 0,
            'threshold': self._threshold,
            'metrics': self._metrics,
            'feature_importance': sorted_importance,
            'training_info': self._training_info,
            'model_type': 'WeightedEnsemble',
            'weights': self._weights.tolist() if hasattr(self._weights, 'tolist') else self._weights
        }
    
    def prepare_features_advanced(self, lat, lon, use_spatial_sampling=True, n_neighbors=15):
        """
        Advanced feature preparation using spatial sampling from existing water points
        
        This replicates the notebook's approach:
        1. Find nearest neighbors using KDTree
        2. Use inverse distance weighting
        3. Extract feature values from neighbors
        4. Create engineered features
        """
        features = {}
        
        # Get actual water point counts in different radii (REAL DATA)
        try:
            for radius in [5, 10, 20]:
                deg_radius = radius / 111.0
                count = WaterPoint.objects.filter(
                    latitude__range=(lat - deg_radius, lat + deg_radius),
                    longitude__range=(lon - deg_radius, lon + deg_radius)
                ).count()
                features[f'water_points_{radius}km'] = float(count)
                print(f"   {radius}km radius: {count} points")
        except Exception as e:
            print(f"Error counting water points: {e}")
            for radius in [5, 10, 20]:
                features[f'water_points_{radius}km'] = 0
        
        # Use spatial sampling to get feature values from nearest neighbors
        if use_spatial_sampling and self._water_points_tree is not None and len(self._all_water_points) > 0:
            try:
                # Find nearest neighbors
                k = min(n_neighbors, len(self._all_water_points))
                distances, indices = self._water_points_tree.query([[lat, lon]], k=k)
                
                # Inverse distance weighting
                weights = 1 / (distances[0] + 0.001)
                weights = weights / weights.sum()
                
                # Get neighbor points
                neighbor_points = [self._all_water_points[i] for i in indices[0]]
                
                # Extract feature values from neighbors
                # Well depth
                depth_values = []
                depth_weights = []
                for j, point in enumerate(neighbor_points):
                    if point.get('well_depth') is not None:
                        try:
                            depth_val = float(point['well_depth'])
                            depth_values.append(depth_val)
                            depth_weights.append(weights[j])
                        except (ValueError, TypeError):
                            pass
                
                if depth_values:
                    depth_weights = np.array(depth_weights) / sum(depth_weights)
                    features['well_depth'] = float(np.average(depth_values, weights=depth_weights))
                else:
                    features['well_depth'] = 61.342  # Default from training
                
                # pH
                ph_values = []
                ph_weights = []
                for j, point in enumerate(neighbor_points):
                    if point.get('ph') is not None:
                        try:
                            ph_val = float(point['ph'])
                            ph_values.append(ph_val)
                            ph_weights.append(weights[j])
                        except (ValueError, TypeError):
                            pass
                
                if ph_values:
                    ph_weights = np.array(ph_weights) / sum(ph_weights)
                    features['ph'] = float(np.average(ph_values, weights=ph_weights))
                else:
                    features['ph'] = 3.46  # Default from training
                
                # Distance to road
                road_values = []
                road_weights = []
                for j, point in enumerate(neighbor_points):
                    if point.get('distance_to_road_m') is not None:
                        try:
                            road_val = float(point['distance_to_road_m'])
                            road_values.append(road_val)
                            road_weights.append(weights[j])
                        except (ValueError, TypeError):
                            pass
                
                if road_values:
                    road_weights = np.array(road_weights) / sum(road_weights)
                    features['dist_to_road_m'] = float(np.average(road_values, weights=road_weights))
                else:
                    features['dist_to_road_m'] = 3094.548  # Default from training
                
                # Distance to water
                water_dist_values = []
                water_dist_weights = []
                for j, point in enumerate(neighbor_points):
                    if point.get('distance_to_water_m') is not None:
                        try:
                            water_val = float(point['distance_to_water_m'])
                            water_dist_values.append(water_val)
                            water_dist_weights.append(weights[j])
                        except (ValueError, TypeError):
                            pass
                
                if water_dist_values:
                    water_dist_weights = np.array(water_dist_weights) / sum(water_dist_weights)
                    features['dist_to_nearest_water_m'] = float(np.average(water_dist_values, weights=water_dist_weights))
                else:
                    features['dist_to_nearest_water_m'] = 1704.461  # Default from training
                
                # Short rains (annual rainfall)
                rain_values = []
                rain_weights = []
                for j, point in enumerate(neighbor_points):
                    if point.get('annual_rainfall_mm') is not None:
                        try:
                            rain_val = float(point['annual_rainfall_mm'])
                            rain_values.append(rain_val)
                            rain_weights.append(weights[j])
                        except (ValueError, TypeError):
                            pass
                
                if rain_values:
                    rain_weights = np.array(rain_weights) / sum(rain_weights)
                    features['short_rains_mm'] = float(np.average(rain_values, weights=rain_weights))
                else:
                    features['short_rains_mm'] = 381.737  # Default from training
                
            except Exception as e:
                logger.error(f"Error in spatial sampling: {e}")
                print(f"Spatial sampling error: {e}")
                # Fall back to default values
                features['well_depth'] = 61.342
                features['ph'] = 3.46
                features['dist_to_road_m'] = 3094.548
                features['dist_to_nearest_water_m'] = 1704.461
                features['short_rains_mm'] = 381.737
        else:
            # Default values if no spatial sampling available
            features['well_depth'] = 61.342
            features['ph'] = 3.46
            features['dist_to_road_m'] = 3094.548
            features['dist_to_nearest_water_m'] = 1704.461
            features['short_rains_mm'] = 381.737
        
        # Set default values for other features
        features['sand_pct'] = 50.0
        features['clay_pct'] = 30.0
        features['soc'] = 1.0
        features['flow_accumulation'] = 1000.0
        features['people_per_water_point_5km'] = 1.0 / (features.get('water_points_5km', 15) + 1)
        features['people_per_water_point_10km'] = 1.0 / (features.get('water_points_10km', 26) + 1)
        features['building_proximity_score'] = 0.028
        features['latitude'] = lat
        features['longitude'] = lon
        
        # Engineered features (EXACTLY as in notebook)
        features['density_road_interaction'] = features.get('water_points_5km', 15) * features.get('dist_to_road_m', 3094)
        features['people_water_ratio_sq'] = features.get('people_per_water_point_5km', 0.252) ** 2
        features['distance_to_water_scaled'] = np.log1p(features.get('dist_to_nearest_water_m', 1704))
        features['road_access_index'] = 1 / (1 + features.get('dist_to_road_m', 3094)/1000)
        features['water_scarcity_index'] = features.get('people_per_water_point_5km', 0.252) * features.get('dist_to_nearest_water_m', 1704)
        features['soil_quality_index'] = (features.get('sand_pct', 50) * 0.3 + 
                                          (100 - features.get('clay_pct', 30)) * 0.3 + 
                                          features.get('soc', 1) * 0.4)
        features['climate_risk_index'] = 100 - features.get('short_rains_mm', 381) / 5
        
        # Spatial cluster
        if self._kmeans_model is not None and 'latitude' in features and 'longitude' in features:
            features['spatial_cluster'] = int(self._kmeans_model.predict([[features['latitude'], features['longitude']]])[0])
        else:
            features['spatial_cluster'] = self._assign_spatial_cluster(lat, lon)
        
        return features
    
    def _assign_spatial_cluster(self, lat, lon):
        """Assign spatial cluster based on geographic regions (fallback)"""
        if lat > 4.0:
            return 0
        elif lat > 3.0:
            return 1
        elif lat > 2.5:
            return 2
        elif lat > 2.0:
            return 3
        else:
            return 4
    
    def _get_confidence_from_score(self, score):
        """Helper method to determine confidence from score"""
        distance_from_threshold = abs(score - self._threshold)
        if distance_from_threshold > 0.3:
            return 'high'
        elif distance_from_threshold > 0.15:
            return 'medium'
        else:
            return 'low'
    
    def predict_advanced(self, lat, lon, return_detailed=True):
        """
        Advanced prediction with detailed explanations and model scores
        
        This replicates the notebook's predict_water_point_advanced function
        """
        if not self.is_ready():
            return {
                'success': False,
                'error': 'Models not loaded',
                'score': 0.5,
                'prediction': 'UNKNOWN',
                'category': 'UNKNOWN',
                'reasons': ['Model not loaded']
            }
        
        try:
            print(f"\n🔍 Predicting for location: ({lat:.4f}, {lon:.4f})")
            
            # Prepare advanced features with spatial sampling (EXACTLY as in notebook)
            features = self.prepare_features_advanced(lat, lon, use_spatial_sampling=True)
            
            # Create feature array in the correct order
            feature_values = []
            for name in self._feature_names:
                if name in features:
                    feature_values.append(features[name])
                else:
                    print(f"⚠️ Missing feature: {name}")
                    feature_values.append(0.0)
            
            feature_vector = np.array(feature_values).reshape(1, -1)
            print(f"   Feature vector shape: {feature_vector.shape}")
            
            # Scale features
            if self._scaler is not None:
                try:
                    feature_vector = self._scaler.transform(feature_vector)
                    print("   Features scaled successfully")
                except Exception as e:
                    print(f"   Scaling error: {e}")
            
            # Get predictions from each model
            try:
                rf_proba = self._rf_model.predict_proba(feature_vector)[0, 1]
                print(f"   RF probability: {rf_proba:.4f}")
            except Exception as e:
                print(f"   RF prediction error: {e}")
                rf_proba = 0.5
            
            try:
                xgb_proba = self._xgb_model.predict_proba(feature_vector)[0, 1]
                print(f"   XGB probability: {xgb_proba:.4f}")
            except Exception as e:
                print(f"   XGB prediction error: {e}")
                xgb_proba = 0.5
            
            try:
                lgbm_proba = self._lgbm_model.predict_proba(feature_vector)[0, 1]
                print(f"   LGBM probability: {lgbm_proba:.4f}")
            except Exception as e:
                print(f"   LGBM prediction error: {e}")
                lgbm_proba = 0.5
            
            # Weighted ensemble probability (using stored weights)
            probability = (rf_proba * self._weights[0] + 
                          xgb_proba * self._weights[1] + 
                          lgbm_proba * self._weights[2])
            
            print(f"   Ensemble probability: {probability:.4f}")
            print(f"   Threshold: {self._threshold:.4f}")
            
            # Determine category (EXACT thresholds from notebook)
            if probability > 0.7:
                category = 'HIGHLY SUITABLE'
            elif probability > 0.5:
                category = 'MODERATELY SUITABLE'
            elif probability > 0.3:
                category = 'LOW SUITABILITY'
            else:
                category = 'UNSUITABLE'
            
            prediction = 'SUITABLE' if probability >= self._threshold else 'UNSUITABLE'
            
            # Generate detailed reasons (EXACT logic from notebook)
            reasons = []
            
            # Water availability (short rains)
            if features.get('short_rains_mm', 0) > 150:
                reasons.append(f"✓ Good rainfall: {features['short_rains_mm']:.0f} mm")
            else:
                reasons.append(f"⚠️ Low rainfall: {features['short_rains_mm']:.0f} mm")
            
            # Competition (water points within 5km)
            water_points = features.get('water_points_5km', 0)
            if water_points < 5:
                reasons.append(f"✓ Low competition: {water_points:.0f} points nearby")
            elif water_points > 15:
                reasons.append(f"✗ High competition: {water_points:.0f} points nearby")
            
            # Accessibility (distance to road)
            road_dist_km = features.get('dist_to_road_m', 0) / 1000
            if road_dist_km < 5:
                reasons.append(f"✓ Good road access: {road_dist_km:.1f} km")
            elif road_dist_km > 10:
                reasons.append(f"✗ Remote: {road_dist_km:.1f} km from road")
            
            # Water table (well depth)
            well_depth = features.get('well_depth', 0)
            if well_depth > 70:
                reasons.append(f"✓ Deep water table: {well_depth:.0f} m (reliable)")
            elif well_depth < 40:
                reasons.append(f"⚠️ Shallow water table: {well_depth:.0f} m")
            
            # Water quality (pH)
            ph = features.get('ph', 7)
            if 6 <= ph <= 8:
                reasons.append(f"✓ Good pH: {ph:.1f}")
            elif ph < 4:
                reasons.append(f"⚠️ Acidic water: pH {ph:.1f}")
            
            # Soil quality
            if features.get('sand_pct', 50) > 50:
                reasons.append(f"✓ Sandy soil: {features['sand_pct']:.0f}% sand")
            
            result = {
                'success': True,
                'score': float(probability),
                'prediction': prediction,
                'category': category,
                'reasons': reasons[:5],  # Limit to top 5 reasons
                'model_scores': {
                    'Random Forest': float(rf_proba),
                    'XGBoost': float(xgb_proba),
                    'LightGBM': float(lgbm_proba)
                },
                'threshold_used': float(self._threshold),
                'weights': self._weights.tolist() if hasattr(self._weights, 'tolist') else self._weights,
                'feature_values': {k: float(v) for k, v in features.items() if k in self._feature_names[:10]},
                'confidence': self._get_confidence_from_score(probability)
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Advanced prediction error: {str(e)}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'error': str(e),
                'score': 0.5,
                'prediction': 'ERROR',
                'category': 'ERROR',
                'reasons': [f'Error: {str(e)[:50]}'],
                'confidence': 'low'
            }
    
    def find_optimal_locations_advanced(self, bounds, n_locations=10, grid_size=20, min_distance_km=15):
        """
        Find optimal locations using grid search with minimum distance constraint
        
        This replicates the notebook's find_optimal_locations_advanced function
        """
        min_lat, max_lat, min_lon, max_lon = bounds
        
        # Generate grid points
        lats = np.linspace(min_lat, max_lat, grid_size)
        lons = np.linspace(min_lon, max_lon, grid_size)
        
        candidates = []
        total = len(lats) * len(lons)
        print(f"\n   Scanning {total} potential locations...")
        
        for i, lat in enumerate(lats):
            for j, lon in enumerate(lons):
                result = self.predict_advanced(lat, lon, return_detailed=True)
                if result['success']:
                    candidates.append({
                        'lat': float(lat),
                        'lon': float(lon),
                        'score': result['score'],
                        'category': result['category'],
                        'prediction': result['prediction'],
                        'reasons': result['reasons'][:3]  # Store top 3 reasons
                    })
        
        # Sort by score
        candidates.sort(key=lambda x: x['score'], reverse=True)
        
        # Select top locations with minimum distance constraint
        optimal = []
        for cand in candidates:
            if len(optimal) >= n_locations:
                break
            
            # Check if score is above threshold
            if cand['score'] < self._threshold:
                continue
            
            # Check distance from already selected locations
            too_close = False
            for selected in optimal:
                # Rough distance calculation (1 degree ≈ 111 km)
                dist_km = ((cand['lat'] - selected['lat'])**2 +
                          (cand['lon'] - selected['lon'])**2)**0.5 * 111
                if dist_km < min_distance_km:
                    too_close = True
                    break
            
            if not too_close:
                optimal.append(cand)
        
        # Calculate statistics
        scores = [c['score'] for c in candidates if c['score'] > self._threshold]
        
        stats = {
            'total_analyzed': len(candidates),
            'locations_found': len(optimal),
            'avg_score': float(np.mean(scores)) if scores else 0,
            'max_score': float(np.max(scores)) if scores else 0,
            'min_score': float(np.min(scores)) if scores else 0,
            'above_threshold': len(scores)
        }
        
        return {
            'success': True,
            'optimal_locations': optimal,
            'statistics': stats,
            'threshold': float(self._threshold)
        }
    
    def predict(self, water_point, return_features=False):
        """Original predict method for backward compatibility"""
        try:
            if isinstance(water_point, dict):
                lat = water_point.get('latitude')
                lon = water_point.get('longitude')
            else:
                lat = water_point.latitude
                lon = water_point.longitude
            
            if lat is None or lon is None:
                return {
                    'success': False,
                    'error': 'No coordinates provided',
                    'status': 'unknown',
                    'probability': 0.5,
                    'confidence': 'low'
                }
            
            result = self.predict_advanced(lat, lon, return_detailed=True)
            
            return {
                'success': result.get('success', False),
                'status': 'operational' if result.get('score', 0.5) >= self._threshold else 'non_operational',
                'probability': result.get('score', 0.5),
                'threshold': self._threshold,
                'confidence': result.get('confidence', 'low'),
                'distance_from_threshold': abs(result.get('score', 0.5) - self._threshold),
                'individual_probabilities': result.get('model_scores', {}),
                'weights': self._weights.tolist() if hasattr(self._weights, 'tolist') else self._weights,
                'model_metrics': self._metrics,
                'category': result.get('category', 'UNKNOWN'),
                'reasons': result.get('reasons', [])
            }
            
        except Exception as e:
            logger.error(f"Prediction error: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'status': 'error',
                'probability': 0.5,
                'confidence': 'low'
            }
    
    def predict_for_location(self, lat, lon):
        """Predict suitability for a new location"""
        return self.predict_advanced(lat, lon, return_detailed=True)


# Singleton instance
ml_service = EnsembleMLService()