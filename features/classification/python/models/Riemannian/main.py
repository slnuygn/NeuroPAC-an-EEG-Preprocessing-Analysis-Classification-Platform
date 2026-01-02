import os
import sys
import json
import numpy as np
import joblib
import warnings
from sklearn.model_selection import GridSearchCV, GroupKFold

# Suppress warnings
warnings.filterwarnings('ignore', category=FutureWarning)

# -----------------------------------------------------------------------------
# Path Setup
# -----------------------------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
python_root = os.path.abspath(os.path.join(current_dir, "../../"))
capstone_root = os.path.abspath(os.path.join(current_dir, "../../../../.."))
venv_site = os.path.join(capstone_root, ".venv", "Lib", "site-packages")

if python_root not in sys.path:
    sys.path.insert(0, python_root)
if capstone_root not in sys.path:
    sys.path.insert(0, capstone_root)
if os.path.exists(venv_site) and venv_site not in sys.path:
    sys.path.insert(0, venv_site)

# -----------------------------------------------------------------------------
# Imports
# -----------------------------------------------------------------------------
try:
    from features.classification.python.core.preprocess_bridge import PreprocessBridge
except ImportError as e:
    try:
        from core.preprocess_bridge import PreprocessBridge
    except ImportError as e2:
        print(f"Error importing PreprocessBridge: {e2}")
        sys.exit(1)

try:
    from .model import create_riemannian_pipeline, get_default_config
    from .model_connectivity import create_connectivity_pipeline, get_connectivity_default_config
except ImportError:
    try:
        from model import create_riemannian_pipeline, get_default_config
        from model_connectivity import create_connectivity_pipeline, get_connectivity_default_config
    except ImportError as e:
        print(f"Error importing Riemannian model helpers: {e}")
        sys.exit(1)


def load_config(config_path):
    """Load configuration from JSON file."""
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            content = f.read().strip()
            if not content:
                return {}
            return json.loads(content)
    return {}

def extract_unique_groups(selected_classes):
    """Extract unique group names from selected_classes list.
    
    Examples:
    - ["PD_target", "PD_standard"] -> ["PD"]
    - ["PD_target", "CTL_standard"] -> ["PD", "CTL"]
    - None or [] -> None
    """
    if not selected_classes or len(selected_classes) == 0:
        return None
    
    unique_groups = set()
    for class_str in selected_classes:
        if '_' in class_str:
            group = class_str.split('_')[0]
            unique_groups.add(group)
    
    if len(unique_groups) == 0:
        return None
    
    return sorted(list(unique_groups))


def summarize_labels(y_meta, y):
    """Print a compact summary of label distributions to help debug filtering."""
    groups = y_meta.get('group', [])
    conditions = y_meta.get('condition', [])
    subject_ids = y_meta.get('subject_id', [])

    def fmt_counts(values, name):
        values = np.array(values)
        unique, counts = np.unique(values, return_counts=True) if len(values) else ([], [])
        pairs = [f"{u}:{c}" for u, c in zip(unique.tolist(), counts.tolist())]
        print(f"{name} counts -> {'; '.join(pairs) if pairs else 'none'}")

    print("\n[Debug] Label summary after filtering:")
    fmt_counts(groups, "Group")
    fmt_counts(conditions, "Condition")
    fmt_counts(y, "Combined")
    unique_subs = np.unique(subject_ids) if len(subject_ids) else []
    print(f"Unique subjects kept: {len(unique_subs)}")
    print(f"WARNING: With only {len(y)} samples ({len(unique_subs)} subjects), high overfitting is expected.")
    print(f"Training accuracy is typically inflated; focus on CV accuracy as the true performance.")


def main():
    # -------------------------------------------------------------------------
    # 1. Configuration
    # -------------------------------------------------------------------------
    # Default data folder
    data_folder = os.path.join(python_root, "data")
    
    # Determine which analysis type to use
    # Options: 'spectral' or 'connectivity'
    analysis_type = 'spectral'
    if len(sys.argv) > 1:
        analysis_type = sys.argv[1]
    
    # Override data folder if provided as command line argument
    if len(sys.argv) > 2:
        data_folder = sys.argv[2]
        print(f"Using data folder from argument: {data_folder}")
    
    # Parse selected_classes from command line argument
    selected_classes = None
    if len(sys.argv) > 3:
        try:
            selected_classes = json.loads(sys.argv[3])
            print(f"Selected classes: {selected_classes}")
        except (json.JSONDecodeError, ValueError) as e:
            print(f"Warning: Could not parse selected_classes: {e}")
            selected_classes = None
    
    # Map analysis types for config files
    # spectral -> spectral_config.json
    # connectivity -> connectivity_config.json
    config_file = f"{analysis_type}_config.json"
    config_path = os.path.join(current_dir, "configs", config_file)
    
    print(f"Using configuration: {config_file}")
    config = load_config(config_path)
    
    # Merge with defaults (use connectivity-specific defaults for connectivity analysis)
    if analysis_type == 'connectivity':
        default_config = get_connectivity_default_config()
    else:
        default_config = get_default_config()
    for key, value in default_config.items():
        if key not in config:
            config[key] = value
    
    # Extract hyperparameters
    estimator = config.get('estimator', 'scm')
    metric = config.get('metric', 'riemann')
    kernel = config.get('kernel', 'linear')
    C = config.get('C', 1.0)
    use_mdm = config.get('use_mdm', False)
    use_deep = config.get('use_deep', True)
    class_weight = config.get('class_weight', 'balanced')
    enable_grid_search = config.get('enable_grid_search', True)
    test_size = config.get('test_size', 0.3)
    val_split = config.get('val_split', 0.5)
    random_state = config.get('random_state', 42)
    hidden_dims = tuple(config.get('hidden_dims', [256, 128]))
    dropout = config.get('dropout', 0.3)
    input_dropout = config.get('input_dropout', 0.0)
    lr = config.get('lr', 1e-3)
    max_epochs = config.get('max_epochs', 60)
    batch_size = config.get('batch_size', 128)
    weight_decay = config.get('weight_decay', 1e-4)
    patience = config.get('patience', 5)
    train_split_ratio = config.get('train_split', None)
    train_split = train_split_ratio if isinstance(train_split_ratio, (int, float)) else None
    label_smoothing = config.get('label_smoothing', 0.0)
    
    # Connectivity-specific regularization parameters
    reg = config.get('reg', 1e-5)
    shrinkage = config.get('shrinkage', 0.02)
    min_eigenvalue = config.get('min_eigenvalue', 1e-6)
    use_vectorized = config.get('use_vectorized', True)  # Use vectorized by default for connectivity
    
    # -------------------------------------------------------------------------
    # 2. Load Data using Bridge
    # -------------------------------------------------------------------------
    print("Initializing PreprocessBridge...")
    bridge = PreprocessBridge(data_folder=data_folder)
    
    print(f"Loading {analysis_type} data for Riemannian...")
    try:
        # Bridge returns data in format (n_trials, n_channels, n_features)
        # spectral: (n_trials, 12, 15)
        # connectivity: (n_trials, 12, 12)
        X, y_meta = bridge.load_and_transform(analysis_type, "riemannian")
    except FileNotFoundError as e:
        print(f"Error loading data: {e}")
        return
    except Exception as e:
        print(f"An unexpected error occurred during data loading: {e}")
        return
    
    print(f"Data Loaded. Shape: {X.shape}")
    
    # Impute NaNs/Infs to keep samples usable for covariance
    nan_count = np.isnan(X).sum()
    inf_count = np.isinf(X).sum()
    if nan_count or inf_count:
        print(f"Warning: Found {nan_count} NaNs and {inf_count} Infs in data. Replacing with 0.")
        X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)
    
    # Apply class filtering if selected classes provided
    if selected_classes and len(selected_classes) > 0:
        print(f"Filtering data for selected classes: {selected_classes}")
        try:
            # Extract the lists for filtering
            group_labels = y_meta.get('group', [])
            condition_labels = y_meta.get('condition', [])
            
            # Use the filter method from bridge
            X_filtered, group_filtered, condition_filtered, kept_indices = bridge.filter_by_selected_classes(
                X, group_labels, condition_labels, selected_classes
            )
            
            if len(X_filtered) > 0:
                X = np.array(X_filtered)
                # Update y_meta dict with filtered values as numpy arrays
                y_meta['group'] = np.array(group_filtered)
                y_meta['condition'] = np.array(condition_filtered)
                # Filter subject_id using kept_indices
                if 'subject_id' in y_meta and isinstance(y_meta['subject_id'], (list, np.ndarray)):
                    original_ids = y_meta['subject_id'] if isinstance(y_meta['subject_id'], list) else y_meta['subject_id'].tolist()
                    y_meta['subject_id'] = np.array([original_ids[i] for i in kept_indices])
                print(f"After filtering: {len(X)} samples selected")
            else:
                print("Warning: Filtering resulted in no samples. Using all classes.")
        except Exception as e:
            print(f"Warning: Could not filter data by selected classes: {e}")
            print("Proceeding with all classes.")
    
    # Extract labels and subject IDs
    conditions = y_meta['condition']  # 0: Target, 1: Standard, 2: Novelty
    groups = y_meta['group']  # 0: HC/CTL, 1: PD
    subject_ids = y_meta['subject_id']
    
    # Create combined labels for multi-class classification
    combined_labels = groups * 3 + conditions
    
    # Get unique classes actually present in the filtered data
    unique_class_indices = np.unique(combined_labels)
    nb_classes = len(unique_class_indices)
    
    # Remap labels to contiguous range [0, nb_classes-1] for the model
    label_mapping = {old_idx: new_idx for new_idx, old_idx in enumerate(unique_class_indices)}
    y = np.array([label_mapping[label] for label in combined_labels])
    
    print(f"Number of classes after filtering: {nb_classes}")
    print(f"Class indices present: {unique_class_indices.tolist()}")
    summarize_labels(y_meta, y)
    
    # -------------------------------------------------------------------------
    # 3. Five-Fold subject-wise cross validation
    # -------------------------------------------------------------------------
    rng = np.random.default_rng(random_state)
    perm = rng.permutation(len(X))
    X = X[perm]
    y = y[perm]
    subject_ids = subject_ids[perm]

    unique_subjects = np.unique(subject_ids)
    print(f"Total unique subjects found: {len(unique_subjects)}")

    gkf = GroupKFold(n_splits=5)
    fold_accuracies = []

    for fold_idx, (train_idx, test_idx) in enumerate(gkf.split(X, y, groups=subject_ids), start=1):
        print("\n" + "-" * 40)
        print(f"Fold {fold_idx}/5")
        print("-" * 40)

        # Use connectivity-specific pipeline for connectivity analysis
        if analysis_type == 'connectivity':
            clf_fold = create_connectivity_pipeline(
                estimator=estimator,
                metric=metric,
                kernel=kernel,
                C=C,
                use_mdm=use_mdm,
                class_weight=class_weight,
                use_deep=use_deep,
                hidden_dims=hidden_dims,
                dropout=dropout,
                input_dropout=input_dropout,
                lr=lr,
                max_epochs=max_epochs,
                batch_size=batch_size,
                weight_decay=weight_decay,
                patience=patience,
                n_classes=nb_classes,
                train_split=train_split,
                label_smoothing=label_smoothing,
                reg=reg,
                shrinkage=shrinkage,
                min_eigenvalue=min_eigenvalue,
                use_vectorized=use_vectorized,
            )
        else:
            clf_fold = create_riemannian_pipeline(
                estimator=estimator,
                metric=metric,
                kernel=kernel,
                C=C,
                use_mdm=use_mdm,
                class_weight=class_weight,
                use_deep=use_deep,
                hidden_dims=hidden_dims,
                dropout=dropout,
                input_dropout=input_dropout,
                lr=lr,
                max_epochs=max_epochs,
                batch_size=batch_size,
                weight_decay=weight_decay,
                patience=patience,
                n_classes=nb_classes,
                train_split=train_split,
                label_smoothing=label_smoothing,
            )

        X_train_fold, y_train_fold = X[train_idx], y[train_idx]
        X_test_fold, y_test_fold = X[test_idx], y[test_idx]

        clf_fold.fit(X_train_fold, y_train_fold)
        fold_acc = clf_fold.score(X_test_fold, y_test_fold)
        fold_accuracies.append(fold_acc)

        print(f"Fold {fold_idx} accuracy: {fold_acc * 100:.2f}%")

    cv_mean = float(np.mean(fold_accuracies)) if fold_accuracies else 0.0
    cv_std = float(np.std(fold_accuracies)) if fold_accuracies else 0.0

    print("\n" + "=" * 60)
    print("5-FOLD CROSS-VALIDATION SUMMARY")
    print("=" * 60)
    for idx, acc in enumerate(fold_accuracies, start=1):
        print(f"  Fold {idx}: {acc * 100:.2f}%")
    print(f"  Mean Accuracy: {cv_mean * 100:.2f}% (std: {cv_std * 100:.2f}%)")
    print("=" * 60)

    # -------------------------------------------------------------------------
    # 4. Train final model on full dataset and save
    # -------------------------------------------------------------------------
    print("\nTraining final model on full dataset...")
    
    # Use connectivity-specific pipeline for connectivity analysis
    if analysis_type == 'connectivity':
        clf_final = create_connectivity_pipeline(
            estimator=estimator,
            metric=metric,
            kernel=kernel,
            C=C,
            use_mdm=use_mdm,
            class_weight=class_weight,
            use_deep=use_deep,
            hidden_dims=hidden_dims,
            dropout=dropout,
            input_dropout=input_dropout,
            lr=lr,
            max_epochs=max_epochs,
            batch_size=batch_size,
            weight_decay=weight_decay,
            patience=patience,
            n_classes=nb_classes,
            train_split=train_split,
            label_smoothing=label_smoothing,
            reg=reg,
            shrinkage=shrinkage,
            min_eigenvalue=min_eigenvalue,
            use_vectorized=use_vectorized,
        )
    else:
        clf_final = create_riemannian_pipeline(
            estimator=estimator,
            metric=metric,
            kernel=kernel,
            C=C,
            use_mdm=use_mdm,
            class_weight=class_weight,
            use_deep=use_deep,
            hidden_dims=hidden_dims,
            dropout=dropout,
            input_dropout=input_dropout,
            lr=lr,
            max_epochs=max_epochs,
            batch_size=batch_size,
            weight_decay=weight_decay,
            patience=patience,
            n_classes=nb_classes,
            train_split=train_split,
            label_smoothing=label_smoothing,
        )

    clf_final.fit(X, y)

    unique_groups = extract_unique_groups(selected_classes)
    if unique_groups:
        groups_str = "_".join(unique_groups)
        weights_filename = f"Riemannian_{analysis_type}_g{groups_str}_weights_best.pkl"
    else:
        weights_filename = f"Riemannian_{analysis_type}_weights_best.pkl"
    weight_path = os.path.join(data_folder, weights_filename)
    joblib.dump(clf_final, weight_path)
    print(f"\nModel saved to: {weight_path}")

    # Report final training accuracy for reference
    final_train_acc = clf_final.score(X, y)
    print(f"Final model training accuracy on full data: {final_train_acc * 100:.2f}%")
    print(f"\nNOTE: Training accuracy on full data is always optimistic.")
    print(f"Use the CV Mean Accuracy ({cv_mean * 100:.2f}%) as the true performance estimate.")
    print(f"Gap between training ({final_train_acc * 100:.2f}%) and CV ({cv_mean * 100:.2f}%): {(final_train_acc - cv_mean) * 100:.2f}%")


if __name__ == "__main__":
    main()

