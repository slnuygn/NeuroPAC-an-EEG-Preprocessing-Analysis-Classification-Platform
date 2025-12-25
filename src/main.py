import sys
import os

# Set Qt Quick Controls style to Fusion (supports customization)
os.environ['QT_QUICK_CONTROLS_STYLE'] = 'Fusion'

# Enable QML XMLHttpRequest to read local files for dynamic parameter loading
os.environ['QML_XHR_ALLOW_FILE_READ'] = '1'

# Add the project root to Python path so we can import from features/
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot, QUrl
from PyQt6.QtWidgets import QApplication  # Changed from QGuiApplication
from PyQt6.QtQml import QQmlApplicationEngine, qmlRegisterType
from PyQt6.QtCore import QStandardPaths
import features

# Import our custom classes
from file_browser import FileBrowser
# from features.classification.python.config_manager import ClassificationConfig
from matlab_executor import MatlabExecutor
from features.classification.python.classification_controller import ClassificationController

# Function to get the resource path (works for both development and PyInstaller)
def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

app = QApplication(sys.argv)  # Changed to QApplication for widget support

# Register classes with QML
qmlRegisterType(MatlabExecutor, "MatlabExecutor", 1, 0, "MatlabExecutor")
qmlRegisterType(FileBrowser, "FileBrowser", 1, 0, "FileBrowser")


# Create instances
matlab_executor = MatlabExecutor()
file_browser = FileBrowser()
classification_controller = ClassificationController()
# classification_config = ClassificationConfig()

# Keep MATLAB data_dir in sync whenever the file browser loads a folder
file_browser.folderLoaded.connect(matlab_executor.updateDataDirectory)
file_browser.folderLoaded.connect(classification_controller.setDataFolder)

engine = QQmlApplicationEngine()
engine.quit.connect(app.quit)

# Add import paths for QML
engine.addImportPath(os.path.join(project_root, "features", "preprocessing", "qml"))
engine.addImportPath(os.path.join(project_root, "features", "analysis", "qml"))
engine.addImportPath(os.path.join(project_root, "ui"))

# Make instances available to QML
engine.rootContext().setContextProperty("matlabExecutor", matlab_executor)
engine.rootContext().setContextProperty("fileBrowser", file_browser)
engine.rootContext().setContextProperty("classificationController", classification_controller)
# engine.rootContext().setContextProperty("classificationConfig", classification_config)

engine.load(QUrl.fromLocalFile(os.path.join(project_root, 'ui', 'main.qml')))

# Initialize file browser with the current data directory from MATLAB script
current_data_dir = matlab_executor.getCurrentDataDirectory()
if current_data_dir:
    file_browser.initializeWithPath(current_data_dir)

sys.exit(app.exec())