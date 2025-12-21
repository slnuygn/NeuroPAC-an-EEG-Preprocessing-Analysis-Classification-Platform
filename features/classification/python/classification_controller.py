import sys
import os
from PyQt6.QtCore import QObject, pyqtSlot, pyqtSignal, QThread

# Ensure the current directory is in sys.path so we can import from 'models'
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

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

class TrainingWorker(QObject):
    finished = pyqtSignal()
    log_message = pyqtSignal(str)
    
    def run(self):
        if run_eegnet_training is None:
            self.log_message.emit("Error: Could not import training script.")
            self.finished.emit()
            return

        self.log_message.emit("Starting EEGNet training...")
        try:
            # Run the training function
            # Note: This will print to stdout/stderr. 
            # To capture output in the UI, we would need to redirect stdout 
            # or modify the training script to emit signals.
            run_eegnet_training()
            
            self.log_message.emit("Training finished successfully.")
        except Exception as e:
            self.log_message.emit(f"Error during training: {str(e)}")
            import traceback
            self.log_message.emit(traceback.format_exc())
        finally:
            self.finished.emit()

class ClassificationController(QObject):
    def __init__(self):
        super().__init__()
        self.thread = None
        self.worker = None

    # Signal to send logs to QML
    logReceived = pyqtSignal(str, arguments=['message'])
    trainingFinished = pyqtSignal()

    @pyqtSlot()
    def startEEGNetTraining(self):
        if self.thread is not None and self.thread.isRunning():
            self.logReceived.emit("Training is already in progress.")
            return

        self.logReceived.emit("Initializing training thread...")
        
        self.thread = QThread()
        self.worker = TrainingWorker()
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
