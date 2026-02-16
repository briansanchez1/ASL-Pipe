import sys
import cv2
from cv2_enumerate_cameras import enumerate_cameras
from PySide6.QtCore import Qt, QSize, QTimer
from PySide6.QtGui import QPixmap, QImage, QColor
from PySide6.QtMultimedia import QMediaDevices
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QLabel, QPushButton


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ASL Pipe")
        self.setMinimumSize(600, 600)

        # Dropdown Selection
        self.camera_dropdown = QComboBox()
        self.camera_dropdown.setPlaceholderText("Select a camera")
        self.populate_cameras()
        self.camera_dropdown.currentIndexChanged.connect(
            self.on_camera_changed
        )

        # Refresh Button
        self.refresh_button = QPushButton()
        self.refresh_button.setText("Refresh list")
        self.refresh_button.clicked.connect(self.populate_cameras)

        # Camera Output - Placeholder for now until MediaPipe and OpenCV are integrated
        self.camera = None
        self.video_size = QSize(400, 400)
        self.image_label = QLabel()
        self.image_label.setMinimumSize(self.video_size)

        # MediaPipe Model Output - also placeholder for now
        self.output_label = QLabel("MediaPipe output will appear here")
        self.output_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.output_label.setStyleSheet("font-size: 14px;")

        top = QHBoxLayout()
        top.addWidget(self.camera_dropdown)
        top.addWidget(self.refresh_button)

        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(self.image_label)
        layout.addWidget(self.output_label)

        self.timer = QTimer()
        self.timer.timeout.connect(self.display_video_stream)
        self.timer.start(30)

    def populate_cameras(self):
        """
        Fill the camera list dropdown with available camera devices
        """
        self.camera = None
        self.camera_dropdown.clear()
        cameras = enumerate_cameras()
        
        if not cameras:
            self.camera_dropdown.addItem("No cameras found")
            return

        for camera in cameras:
            self.camera_dropdown.addItem(
                f"{camera.name}",
                camera.index,
            )
            

    def start_camera(self, index: int):
        """
        Start the camera based on the selected index
        """
        self.camera = None
        if self.camera:
            self.camera.release()

        self.camera = cv2.VideoCapture(index)
        self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, self.video_size.width())
        self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, self.video_size.height())


    def on_camera_changed(self, index: int):
        """ 
        Handle camera selection changes from the dropdown
        """
        if index < 0:
            return
        self.start_camera(index)
        
    def display_video_stream(self):
        """Read frame from camera and repaint QLabel widget.
        """
        if self.camera:
            _, frame = self.camera.read()
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frame = cv2.flip(frame, 1)
            image = QImage(frame, frame.shape[1], frame.shape[0],
                           frame.strides[0], QImage.Format.Format_RGB888)
            self.image_label.setPixmap(QPixmap.fromImage(image))
        else:
            image = QPixmap(self.image_label.size())
            QPixmap.fill(image, QColor())
            self.image_label.setPixmap(image)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
