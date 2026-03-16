# create_mock_model.py
import joblib
import numpy as np
import os
from datetime import datetime

# Create a proper mock model class with required methods
class MockModel:
    def __init__(self):
        self.feature_importances_ = np.array([
            0.211, 0.080, 0.071, 0.063, 0.053, 0.053, 0.044, 0.042, 0.042, 0.040,
            0.038, 0.035, 0.032, 0.030, 0.028, 0.025, 0.023, 0.020, 0.018, 0.015,
            0.012, 0.010, 0.008, 0.005, 0.003
        ])
    
    def predict_proba(self, X):
        """Return mock probabilities"""
        # Return probabilities: [P(negative), P(positive)]
        # Based on your model's threshold of 0.213, return a random-ish value
        # but weighted by the feature importances (simplified)
        if hasattr(X, 'shape') and X.shape[0] > 0:
            # Generate a probability based on a simple linear combination
            # This is just for demonstration
            prob = 0.3  # Default
            return np.array([[1-prob, prob]])
        return np.array([[0.7, 0.3]])

# Create a mock scaler class
class MockScaler:
    def transform(self, X):
        return X
    
    def fit_transform(self, X, y=None):
        return X
    
    def fit(self, X, y=None):
        return self

# Create the deployment package
deployment_package = {
    'model': MockModel(),
    'feature_names': [
        'well_depth', 'ph', 'dist_to_road_m', 'dist_to_nearest_water_m',
        'water_points_5km', 'water_points_10km', 'water_points_20km',
        'people_per_water_point_5km', 'people_per_water_point_10km',
        'building_proximity_score', 'latitude', 'longitude',
        'short_rains_mm', 'sand_pct', 'clay_pct', 'soc',
        'flow_accumulation', 'density_road_interaction',
        'people_water_ratio_sq', 'distance_to_water_scaled',
        'road_access_index', 'water_scarcity_index',
        'soil_quality_index', 'climate_risk_index', 'spatial_cluster'
    ],
    'scaler': MockScaler(),
    'threshold': 0.213,
    'metrics': {
        'accuracy': 0.8535,
        'precision': 0.2083,
        'recall': 0.5556,
        'f1_score': 0.3030,
        'roc_auc': 0.8986,
        'confusion_matrix': [[129, 19], [4, 5]]
    },
    'feature_importance': {
        'well_depth': 0.211,
        'ph': 0.080,
        'water_scarcity_index': 0.071,
        'people_water_ratio_sq': 0.063,
        'dist_to_road_m': 0.053,
        'longitude': 0.053,
        'dist_to_nearest_water_m': 0.044,
        'people_per_water_point_5km': 0.042,
        'density_road_interaction': 0.042,
        'building_proximity_score': 0.040,
        'latitude': 0.038,
        'water_points_5km': 0.035,
        'road_access_index': 0.032,
        'distance_to_water_scaled': 0.030,
        'soil_quality_index': 0.028,
        'climate_risk_index': 0.025,
        'water_points_10km': 0.023,
        'water_points_20km': 0.020,
        'people_per_water_point_10km': 0.018,
        'short_rains_mm': 0.015,
        'sand_pct': 0.012,
        'clay_pct': 0.010,
        'soc': 0.008,
        'flow_accumulation': 0.005,
        'spatial_cluster': 0.003
    },
    'training_info': {
        'n_samples': 1042,
        'n_features': 25,
        'positive_class_ratio': 0.0585,
        'date_trained': datetime.now().isoformat(),
        'model_type': 'EnsembleModel'
    }
}

# Create models directory
os.makedirs('water_app/ml_models', exist_ok=True)

# Save the mock model
joblib.dump(deployment_package, 'water_app/ml_models/latest_model.joblib')
print("✅ Mock model saved to water_app/ml_models/latest_model.joblib")

# Verify the save was successful
print("\nVerifying saved model...")
loaded = joblib.load('water_app/ml_models/latest_model.joblib')
print("Keys in saved model:", list(loaded.keys()))
print(f"Model type: {type(loaded['model']).__name__}")
print(f"Model has predict_proba: {hasattr(loaded['model'], 'predict_proba')}")
print("✅ Model verification complete")