import sys
from PySide6.QtWidgets import QApplication,QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QLabel, QPushButton
from PySide6.QtMultimedia import QCamera, QMediaCaptureSession, QMediaDevices
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtCore import Qt

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ASL Pipe")
        self.setMinimumSize(600, 600)
        
        # Dropdown Selection
        self.camera_dropdown = QComboBox()
        self.camera_dropdown.setPlaceholderText("Select a camera")
        self.camera_devices = QMediaDevices.videoInputs()
        self.populate_cameras()
        self.camera_dropdown.currentIndexChanged.connect(
            self.on_camera_changed
        )
        
        # Refresh Button
        self.refresh_button = QPushButton()
        self.refresh_button.setText(("Refresh list"))
        self.refresh_button.clicked.connect(self.populate_cameras)
        
        # Camera Output - Placeholder for now until MediaPipe and OpenCV are integrated
        self.camera = None
        self.capture_session = QMediaCaptureSession()
        self.video_widget = QVideoWidget()
        self.capture_session.setVideoOutput(self.video_widget)
        self.video_widget.setMinimumSize(400, 400)

        # MediaPipe Model Output - also placeholder for now
        self.output_label = QLabel("MediaPipe output will appear here")
        self.output_label.setAlignment(Qt.AlignCenter)
        self.output_label.setStyleSheet("font-size: 14px;")

        top = QHBoxLayout()
        top.addWidget(self.camera_dropdown)
        top.addWidget(self.refresh_button)
        
        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(self.video_widget)
        layout.addWidget(self.output_label)

    def populate_cameras(self):
        """
        Fill the camera list dropdown with available camera devices
        """
        self.camera_dropdown.clear()

        if not self.camera_devices:
            self.camera_dropdown.addItem("No cameras found")
            return
        
        self.camera_devices = QMediaDevices.videoInputs()
        for device in self.camera_devices:
            self.camera_dropdown.addItem(device.description())

    def start_camera(self, index: int):
        """
        Start the camera based on the selected index
        """
        if self.camera:
            self.camera.stop()

        device = self.camera_devices[index]
        self.camera = QCamera(device)
        
        self.camera_dropdown.setPlaceholderText(self.camera_devices[index].description())
        self.capture_session.setCamera(self.camera)
        self.camera.start()

    def on_camera_changed(self, index: int):
        """ 
        Handle camera selection changes from the dropdown
        """
        if index < 0 or index >= len(self.camera_devices):
            return

        self.start_camera(index)
        self.camera_dropdown.setPlaceholderText(self.camera_devices[index].description())

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
