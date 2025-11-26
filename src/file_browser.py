import os
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot, pyqtProperty, QStandardPaths


class FileBrowser(QObject):
    """Class to handle file browser functionality"""
    
    # Signals for drive files (upper pane)
    folderContentsChanged = pyqtSignal(list)
    currentFolderChanged = pyqtSignal(str)
    
    # Signals for RAM files (lower pane)
    ramContentsChanged = pyqtSignal(list)
    
    def __init__(self):
        super().__init__()
        self._current_folder = ""
        self._folder_contents = []
        self._ram_contents = []
    
    @pyqtProperty(str, notify=currentFolderChanged)
    def currentFolder(self):
        return self._current_folder
    
    @currentFolder.setter
    def currentFolder(self, value):
        if self._current_folder != value:
            self._current_folder = value
            self.currentFolderChanged.emit(value)
    
    @pyqtProperty(list, notify=folderContentsChanged)
    def folderContents(self):
        return self._folder_contents
    
    @folderContents.setter
    def folderContents(self, value):
        if self._folder_contents != value:
            self._folder_contents = value
            self.folderContentsChanged.emit(value)
    
    @pyqtSlot(str)
    def initializeWithPath(self, initial_path):
        """Initialize the file browser with a path from the MATLAB script"""
        if initial_path and initial_path.strip():
            self.loadFolder(initial_path)
    
    @pyqtSlot()
    def clearFolder(self):
        """Clear the current folder selection"""
        self.currentFolder = ""  # Use property setter
        self._folder_contents = []
        self.folderContentsChanged.emit([])
    
    @pyqtSlot()
    def refreshCurrentFolder(self):
        """Refresh the contents of the current folder"""
        if self._current_folder:
            self.loadFolder(self._current_folder)
    
    @pyqtSlot(str)
    def loadFolder(self, folder_path):
        """Load contents of the specified folder"""
        try:
            # Convert QML URL to local path if needed
            if folder_path.startswith("file:///"):
                folder_path = folder_path[8:]  # Remove file:/// prefix
                # Fix any remaining forward slashes on Windows
                folder_path = folder_path.replace('/', '\\')
            
            # Clean up any double backslashes
            folder_path = folder_path.replace('\\\\', '\\')
            
            self.currentFolder = folder_path  # Use property setter
            
            contents = []
            for item in os.listdir(folder_path):
                item_path = os.path.join(folder_path, item)
                if os.path.isdir(item_path):
                    contents.append(f"📁 {item}")
                else:
                    contents.append(f"📄 {item}")
            
            self._folder_contents = contents
            self.folderContentsChanged.emit(contents)
            
        except Exception as e:
            print(f"Error reading folder: {e}")
            self.folderContentsChanged.emit([f"Error: {str(e)}"])
    
    @pyqtSlot(result=str)
    def getCurrentFolder(self):
        """Get the currently selected folder path"""
        return self.currentFolder
    
    @pyqtSlot(list)
    def updateRamContents(self, filenames):
        """Update RAM contents (lower pane) with processed filenames"""
        try:
            ram_contents = []
            for filename in filenames:
                ram_contents.append(f"🧠 {filename}")  # Brain emoji for RAM files
            
            self._ram_contents = ram_contents
            self.ramContentsChanged.emit(ram_contents)
            
        except Exception as e:
            print(f"Error updating RAM contents: {e}")
            self.ramContentsChanged.emit([f"Error: {str(e)}"])
    
    @pyqtSlot()
    def clearRamContents(self):
        """Clear RAM contents"""
        self._ram_contents = []
        self.ramContentsChanged.emit([])
    
    @pyqtSlot(result=str)
    def getDesktopPath(self):
        """Get the desktop path as a starting point"""
        try:
            desktop_path = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DesktopLocation)
            return desktop_path
        except:
            return os.path.expanduser("~")
