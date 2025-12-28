import sys
import os
import json
import subprocess
import traceback
import importlib
from PyQt6.QtCore import QObject, pyqtSlot, pyqtSignal, QThread

# Ensure the current directory is in sys.path so we can import from 'models'
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

# Import the config parser
from core.config_parser import ConfigParser

# Import diagnosis labels
try:
    from core.labels import labels as diagnosis_labels
except Exception:
    diagnosis_labels = []

# Import the main function from the EEGNet script
try:
    from models.EEGNet.main import main as run_eegnet_training
except ImportError:
    # Fallback for different path structures (e.g. if running from src/)
    try:
        from features.classification.python.models.EEGNet.main import main as run_eegnet_training
    except ImportError as e:
        print(f"Error importing EEGNet main: {e}")
        run_eegnet_training = None

# Import the main function from the EEG-Inception script
try:
    from models.EEG_Inception.main import main as run_eeginception_training
except ImportError:
    try:
        # Note: The folder name is 'EEG-Inception' (with dash), but python imports usually don't like dashes.
        # However, if the folder is literally named 'EEG-Inception', standard import might fail.
        # We might need to use importlib or ensure the folder is importable.
        # Assuming the user might rename it or we use importlib for safety if dash is present.
        # For now, let's try the direct import assuming standard python path resolution works or folder is renamed.
        # If the folder has a dash, we can't use dot notation directly in some python versions.
        # Let's use importlib to be safe for "EEG-Inception".
        import importlib
        eeg_inception_module = importlib.import_module("features.classification.python.models.EEG-Inception.main")
        run_eeginception_training = eeg_inception_module.main
    except ImportError as e:
        # Try relative path if running from classification root
        try:
            import importlib
            eeg_inception_module = importlib.import_module("models.EEG-Inception.main")
            run_eeginception_training = eeg_inception_module.main
        except ImportError as e2:
            print(f"Error importing EEG-Inception main: {e2}")
            run_eeginception_training = None

class TrainingWorker(QObject):
    finished = pyqtSignal()
    log_message = pyqtSignal(str)
    
    def __init__(self, model_name="EEGNet", analysis_key="erp", data_path=""):
        super().__init__()
        self.model_name = model_name
        self.analysis_key = analysis_key
        self.data_path = data_path

    def run(self):
        self.log_message.emit(f"Starting {self.model_name} training with {self.analysis_key} analysis...")
        
        try:
            # Import the appropriate model's main function dynamically
            import subprocess
            import sys
            
            # Determine model directory name
            model_dir_map = {
                "EEGNet": "EEGNet",
                "EEG-Inception": "EEG-Inception",
                "Riemannian": "Riemannian"
            }
            
            model_dir = model_dir_map.get(self.model_name)
            if not model_dir:
                self.log_message.emit(f"Error: Unknown model {self.model_name}")
                self.finished.emit()
                return
            
            # Build path to model's main.py
            current_dir = os.path.dirname(os.path.abspath(__file__))
            main_script = os.path.join(current_dir, "models", model_dir, "main.py")
            
            if not os.path.exists(main_script):
                self.log_message.emit(f"Error: Main script not found at {main_script}")
                self.finished.emit()
                return
            
            self.log_message.emit(f"Running: {main_script} with analysis_key={self.analysis_key}")
            
            # Run the training script as a subprocess with the analysis key as argument
            args = [sys.executable, main_script, self.analysis_key]
            if self.data_path:
                args.append(self.data_path)
            
            process = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            # Stream output to log
            for line in process.stdout:
                self.log_message.emit(line.strip())
            
            process.wait()
            
            if process.returncode == 0:
                self.log_message.emit("Training finished successfully.")
            else:
                self.log_message.emit(f"Training finished with return code: {process.returncode}")
                
        except Exception as e:
            self.log_message.emit(f"Error during training: {str(e)}")
            import traceback
            self.log_message.emit(traceback.format_exc())
        finally:
            self.finished.emit()

class TestWorker(QObject):
    finished = pyqtSignal()
    log_message = pyqtSignal(str)
    test_results = pyqtSignal(str)  # Emits JSON string with test results
    
    def __init__(self, model_name="EEGNet", analysis_key="erp", data_path="", weights_path=""):
        super().__init__()
        self.model_name = model_name
        self.analysis_key = analysis_key
        self.data_path = data_path
        self.weights_path = weights_path
    
    def run(self):
        self.log_message.emit(f"Starting {self.model_name} testing with {self.analysis_key} analysis...")
        
        try:
            import subprocess
            import sys
            
            # Determine model directory name
            model_dir_map = {
                "EEGNet": "EEGNet",
                "EEG-Inception": "EEG-Inception",
                "Riemannian": "Riemannian"
            }
            
            model_dir = model_dir_map.get(self.model_name)
            if not model_dir:
                self.log_message.emit(f"Error: Unknown model {self.model_name}")
                self.finished.emit()
                return
            
            # Build path to model's test script
            current_dir = os.path.dirname(os.path.abspath(__file__))
            test_script = os.path.join(current_dir, "models", model_dir, "test.py")
            
            # If test.py doesn't exist, try using main.py with a test flag
            if not os.path.exists(test_script):
                self.log_message.emit(f"Note: Dedicated test script not found at {test_script}")
                self.log_message.emit(f"Using main training script for evaluation...")
                test_script = os.path.join(current_dir, "models", model_dir, "main.py")
            
            if not os.path.exists(test_script):
                self.log_message.emit(f"Error: Script not found at {test_script}")
                self.finished.emit()
                return
            
            self.log_message.emit(f"Running: {test_script} with analysis_key={self.analysis_key}")
            self.log_message.emit(f"Using weights: {self.weights_path}")
            
            # Run the test script as a subprocess
            args = [sys.executable, test_script, self.analysis_key]
            if self.data_path:
                args.append(self.data_path)
            if self.weights_path:
                args.append(self.weights_path)
            
            process = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            # Stream output to log and capture JSON results
            json_result = None
            for line in process.stdout:
                stripped_line = line.strip()
                self.log_message.emit(stripped_line)
                
                # Check if line contains JSON result
                if stripped_line.startswith("JSON_RESULT:"):
                    try:
                        json_str = stripped_line.replace("JSON_RESULT:", "").strip()
                        json_result = json_str
                    except Exception as e:
                        self.log_message.emit(f"Failed to parse JSON result: {e}")
            
            process.wait()
            
            if process.returncode == 0:
                self.log_message.emit("Testing finished successfully.")
                if json_result:
                    self.test_results.emit(json_result)
            else:
                self.log_message.emit(f"Testing finished with return code: {process.returncode}")
                
        except Exception as e:
            self.log_message.emit(f"Error during testing: {str(e)}")
            import traceback
            self.log_message.emit(traceback.format_exc())
        finally:
            self.finished.emit()

class ClassificationController(QObject):
    def __init__(self):
        super().__init__()
        self.thread = None
        self.worker = None
        self.config_parser = ConfigParser()
        self.data_folder = ""  # Track current data folder

    # Signal to send logs to QML
    logReceived = pyqtSignal(str, arguments=['message'])
    trainingFinished = pyqtSignal()
    testResults = pyqtSignal(str, arguments=['results'])  # JSON string with test results
    testResults = pyqtSignal(str, arguments=['results'])  # JSON string with test results
    
    @pyqtSlot(str)
    def setDataFolder(self, folder_path):
        """Update the data folder path"""
        # Normalize the path and remove file:/// prefix if present
        normalized = folder_path.replace('file:///', '').replace('file://', '').replace('/', '\\')
        self.data_folder = normalized
        self.logReceived.emit(f"Data folder updated to: {self.data_folder}")

    @pyqtSlot(str, result=str)
    def getClassifierConfigs(self, classifierName):
        """Get configuration parameters for a specific classifier as JSON"""
        return self.config_parser.get_classifier_params_as_json(classifierName)
    
    @pyqtSlot(str, result=str)
    def getAvailableAnalyses(self, classifierName):
        """Get available analyses for a specific classifier as JSON array"""
        return self.config_parser.get_available_analyses_as_json(classifierName)

    @pyqtSlot(result=str)
    def getDiagnosisLabels(self):
        """Return diagnosis labels (e.g., HC/Parkinson's) as JSON array."""
        return json.dumps(diagnosis_labels)

    @pyqtSlot(result=int)
    def getDiagnosisLabelCount(self):
        """Return count of diagnosis labels."""
        return len(diagnosis_labels)

    @pyqtSlot(result=str)
    def getConditionLabels(self):
        """Return condition labels (target/standard/novelty) as JSON array."""
        return json.dumps(["target", "standard", "novelty"])

    @pyqtSlot(result=int)
    def getConditionLabelCount(self):
        """Return count of condition labels."""
        return 3

    @pyqtSlot(str, result=str)
    def getAnalysisKey(self, analysisDisplayName: str) -> str:
        """Map an analysis display name to its key (e.g., 'ERP Analysis' -> 'erp')."""
        return self.config_parser.get_analysis_key(analysisDisplayName) or ""
    
    @pyqtSlot(str, str, result=str)
    def getParamsForAnalysis(self, classifierName, analysisName):
        """Get configuration parameters for a specific classifier and analysis as JSON"""
        return self.config_parser.get_params_for_analysis_as_json(classifierName, analysisName)
    
    @pyqtSlot(result=str)
    def getAllClassifierConfigs(self):
        """Get all classifier configurations as JSON"""
        return self.config_parser.get_all_classifiers_as_json()

    @pyqtSlot(str)
    def startTraining(self, modelName):
        if self.thread is not None and self.thread.isRunning():
            self.logReceived.emit("Training is already in progress.")
            return

        self.logReceived.emit(f"Initializing training thread for {modelName}...")
        
        self.thread = QThread()
        self.worker = TrainingWorker(model_name=modelName)
        self.worker.moveToThread(self.thread)
        
        # Connect signals
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        
        # Connect worker log to controller log
        self.worker.log_message.connect(self.logReceived)
        
        # Clean up reference when done
        self.thread.finished.connect(self.on_training_finished)
        
        self.thread.start()

    @pyqtSlot(str, str)
    def startClassification(self, classifierName, analysisDisplayName):
        """Start classification with specific classifier and analysis type"""
        if self.thread is not None and self.thread.isRunning():
            self.logReceived.emit("Training is already in progress.")
            return
        
        # Convert display name to analysis key
        analysis_key = self.config_parser.get_analysis_key(analysisDisplayName)
        if not analysis_key:
            self.logReceived.emit(f"Error: Unknown analysis type '{analysisDisplayName}'")
            return
        
        # Check if data folder is set
        if not self.data_folder:
            self.logReceived.emit("Error: No data folder selected. Please select a folder first.")
            return
        
        self.logReceived.emit(f"Starting {classifierName} with {analysisDisplayName} (key: {analysis_key})...")
        self.logReceived.emit(f"Using data folder: {self.data_folder}")
        
        self.thread = QThread()
        self.worker = TrainingWorker(model_name=classifierName, analysis_key=analysis_key, data_path=self.data_folder)
        self.worker.moveToThread(self.thread)
        
        # Connect signals
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        
        # Connect worker log to controller log
        self.worker.log_message.connect(self.logReceived)
        
        # Clean up reference when done
        self.thread.finished.connect(self.on_training_finished)
        
        self.thread.start()

    def on_training_finished(self):
        self.thread = None
        self.worker = None
        self.trainingFinished.emit()
        self.logReceived.emit("Training thread cleaned up.")

    @pyqtSlot(str, str, str, str, result=str)
    def testErpSubject(self, classifierName: str, analysisDisplayName: str, subjectName: str, weightsPath: str) -> str:
        """Stub ERP testing for a subject. Returns JSON with actual/predicted/accuracy.

        Replace this stub with real testing logic as needed.
        """
        import json

        # Basic validations
        if not classifierName:
            return json.dumps({"error": "classifierName is required"})
        if not analysisDisplayName:
            return json.dumps({"error": "analysisDisplayName is required"})
        if not subjectName:
            return json.dumps({"error": "subjectName is required"})
        if not weightsPath:
            return json.dumps({"error": "weightsPath is required"})

        # Placeholder logic: echo subject and perfect accuracy
        result = {
            "subject": subjectName,
            "actual": "(stub) actual label for " + subjectName,
            "predicted": "(stub) predicted label for " + subjectName,
            "accuracy": 1.0
        }
        return json.dumps(result)

    @pyqtSlot(str, str, str)
    def testClassifier(self, classifierName, analysisDisplayName, weightsPath):
        """Test a trained classifier using the provided weights file."""
        # Check if testing is already in progress
        if self.thread is not None and self.thread.isRunning():
            self.logReceived.emit("Testing or training is already in progress.")
            return
        
        # Validate inputs
        if not classifierName:
            self.logReceived.emit("Error: Classifier name is required for testing.")
            return
        if not analysisDisplayName:
            self.logReceived.emit("Error: Analysis name is required for testing.")
            return
        
        # Normalize weights path
        normalized_weights = weightsPath.replace('file:///', '').replace('file://', '').replace('/', '\\')
        
        if not normalized_weights or not os.path.exists(normalized_weights):
            self.logReceived.emit(f"Error: Weights file not found: {normalized_weights}")
            return

        # Convert display name to analysis key
        analysis_key = self.config_parser.get_analysis_key(analysisDisplayName)
        if not analysis_key:
            self.logReceived.emit(f"Error: Unknown analysis type '{analysisDisplayName}'")
            return
        
        # Check if data folder is set
        if not self.data_folder:
            self.logReceived.emit("Error: No data folder selected. Please select a folder first.")
            return
        
        self.logReceived.emit(f"Starting testing for {classifierName} with {analysisDisplayName} (key: {analysis_key})...")
        self.logReceived.emit(f"Using data folder: {self.data_folder}")
        self.logReceived.emit(f"Using weights: {normalized_weights}")
        
        # Create test worker and thread
        self.thread = QThread()
        self.worker = TestWorker(
            model_name=classifierName, 
            analysis_key=analysis_key, 
            data_path=self.data_folder,
            weights_path=normalized_weights
        )
        self.worker.moveToThread(self.thread)
        
        # Connect signals
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        
        # Connect worker log and test results to controller
        self.worker.log_message.connect(self.logReceived)
        self.worker.test_results.connect(self.testResults)
        
        # Clean up reference when done
        self.thread.finished.connect(self.on_training_finished)
        
        self.thread.start()
