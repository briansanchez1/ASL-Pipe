import sys
import time
from typing import Optional, cast

import cv2
import mediapipe as mp
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap, QImage, QColorConstants
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QLabel, QPushButton
from cv2_enumerate_cameras import enumerate_cameras
from mediapipe.framework.formats import landmark_pb2
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils
mp_drawing_styles = mp.solutions.drawing_styles


class MotionTracker:
    def __init__(self, history_len=20):
        self.history: list[tuple[int, int]] = []  # list of (x, y) normalized coords
        self.history_len: int = history_len

    def update(self, x, y):
        self.history.append((x, y))
        if len(self.history) > self.history_len:
            self.history.pop(0)

    def get_directions(self, threshold=0.015) -> list[str]:
        """Returns list of direction strings from recent movement"""
        dirs = []
        for i in range(1, len(self.history)):
            dx = self.history[i][0] - self.history[i - 1][0]
            dy = self.history[i][1] - self.history[i - 1][1]
            if abs(dx) < threshold and abs(dy) < threshold:
                continue
            if abs(dy) > abs(dx):
                dirs.append("down" if dy > 0 else "up")
            elif abs(dx) > abs(dy) * 1.5:
                dirs.append("right" if dx > 0 else "left")
            else:
                dirs.append("down-left" if (dy > 0 and dx < 0) else
                            "down-right" if (dy > 0 and dx > 0) else "other")
        return dirs

    def detect_j(self) -> bool:
        """
        Detect J: deliberate downward stroke followed immediately by a
        leftward/down-left hook.
        """
        dirs = self.get_directions()

        if len(dirs) < 4:
            return False

        collapsed = [dirs[i] for i in range(len(dirs)) if i == 0 or dirs[i] != dirs[i - 1]]

        # Look for down -> (left | down-left) as *consecutive* collapsed steps
        for i in range(len(collapsed) - 1):
            if collapsed[i] == "down" and collapsed[i + 1] in ("left", "down-left"):
                total_dy = self.history[-1][1] - self.history[0][1]
                if total_dy > 0.18:  # must have moved down at least 8% of frame height
                    return True

        return False

    def detect_z(self) -> bool:
        """Detect Z: right -> down-left -> right as consecutive collapsed steps."""
        dirs = self.get_directions()
        collapsed = [dirs[i] for i in range(len(dirs)) if i == 0 or dirs[i] != dirs[i - 1]]
        try:
            r1 = collapsed.index("right")
            dl = collapsed.index("down-left", r1 + 1)
            collapsed.index("right", dl + 1)
            return True
        except ValueError:
            pass
        return False

    def reset(self):
        self.history.clear()


class MainWindow(QWidget):
    # Visualization parameters
    row_size = 50  # pixels
    left_margin = 24  # pixels
    text_color = (0, 0, 0)  # black
    font_size = 1
    font_thickness = 1

    # Label box parameters
    label_text_color = (255, 255, 255)  # white
    label_font_size = 1
    label_thickness = 2

    def __init__(self):
        super().__init__()
        self.setWindowTitle("ASL Pipe")
        self.setMinimumSize(600, 600)

        # Dropdown Selection
        self.camera_dropdown = QComboBox()
        self.camera_dropdown.setPlaceholderText("Select a camera")
        self.camera_dropdown.currentIndexChanged.connect(self.start_camera)

        # Refresh Button
        self.refresh_button = QPushButton()
        self.refresh_button.setText("Refresh list")
        self.refresh_button.clicked.connect(self.populate_cameras)

        # Clear Output Button
        self.clear_button = QPushButton()
        self.clear_button.setText("Clear Output")
        self.clear_button.clicked.connect(self.clear_output)

        # Camera Output
        self.camera: Optional[cv2.VideoCapture] = None
        self.image_label = QLabel()
        self.image_label.setMinimumSize(400, 400)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Let the label grow to fill available space
        self.image_label.setSizePolicy(
            self.image_label.sizePolicy().horizontalPolicy(),
            self.image_label.sizePolicy().verticalPolicy(),
        )

        self.populate_cameras()

        # MediaPipe Model Output
        self.output_label = QLabel()
        self.output_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.output_label.setStyleSheet("font-size: 14px;")

        top = QHBoxLayout()
        top.addWidget(self.camera_dropdown)
        top.addWidget(self.refresh_button)
        top.addWidget(self.clear_button)

        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(self.image_label, stretch=1)  # stretch=1 so it fills space
        layout.addWidget(self.output_label)

        self.timer = QTimer()
        self.timer.timeout.connect(self.display_video_stream)
        self.timer.start(30)  # ~30 fps

        self.recognition_frame: Optional[cv2.typing.MatLike] = None
        self.recognition_result_list: list[vision.GestureRecognizerResult] = []

        def save_result(result: vision.GestureRecognizerResult,
                        unused_output_image: mp.Image, timestamp_ms: int):
            self.recognition_result_list.append(result)

        # Initialize the gesture recognizer model
        base_options = python.BaseOptions(model_asset_path="Model Training/exported_model/gesture_recognizer.task")
        options = vision.GestureRecognizerOptions(base_options=base_options,
                                                  running_mode=vision.RunningMode.LIVE_STREAM,
                                                  num_hands=1,
                                                  min_hand_detection_confidence=0.5,
                                                  min_hand_presence_confidence=0.5,
                                                  min_tracking_confidence=0.5,
                                                  result_callback=save_result)
        self.recognizer = vision.GestureRecognizer.create_from_options(options)
        self.j_tracker = MotionTracker(history_len=25)
        self.z_tracker = MotionTracker(history_len=40)
        self.motion_cooldown: int = 3  # prevent spam

    def append_text(self, new_text: str):
        """Append new letter to output"""
        self.output_label.setText(self.output_label.text() + new_text)

    def clear_output(self):
        """Clear the output generated by user"""
        self.output_label.setText("")

    def populate_cameras(self):
        """Fill the camera list dropdown with available camera devices"""
        if self.camera:
            self.camera.release()
        self.camera = None
        self.camera_dropdown.clear()
        cameras = enumerate_cameras()

        if not cameras:
            self.camera_dropdown.addItem("No cameras found")
            return

        for camera in cameras:
            self.camera_dropdown.addItem(camera.name, camera.index)

    def start_camera(self):
        """Start the camera based on the selected index"""
        index = self.camera_dropdown.currentData()

        if index is None or index < 0:
            return

        if self.camera:
            self.camera.release()

        self.camera = cv2.VideoCapture(index)

    confidence_timer: float = 0
    prev_time: float = time.time()
    prev_category_name: Optional[str] = None

    def display_video_stream(self):
        """Read frame from camera and repaint QLabel widget."""
        cur_time = time.time()
        if self.camera:
            _, frame = self.camera.read()
            frame = cv2.flip(frame, 1)
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
            self.recognizer.recognize_async(mp_image, time.time_ns() // 1_000_000)

            current_frame = frame

            if self.recognition_result_list:
                for hand_index, hand_landmarks in enumerate(
                        self.recognition_result_list[0].hand_landmarks):
                    # Track pinky tip for J and index tip for Z
                    pinky_tip = hand_landmarks[20]
                    index_tip = hand_landmarks[8]
                    self.j_tracker.update(pinky_tip.x, pinky_tip.y)
                    self.z_tracker.update(index_tip.x, index_tip.y)

                    # Check motion letters with cooldown so no spam
                    if self.motion_cooldown <= 0:
                        if self.j_tracker.detect_j():
                            self.append_text("j")
                            self.j_tracker.reset()
                            self.motion_cooldown = 30
                        elif self.z_tracker.detect_z():
                            self.append_text("z")
                            self.z_tracker.reset()
                            self.motion_cooldown = 30
                    else:
                        self.motion_cooldown -= 1

                    # Calculate the bounding box of the hand
                    x_min = min([cast(float, landmark.x) for landmark in hand_landmarks])
                    y_min = min([cast(float, landmark.y) for landmark in hand_landmarks])
                    y_max = max([cast(float, landmark.z) for landmark in hand_landmarks])

                    # Convert normalized coordinates to pixel values
                    frame_height, frame_width = current_frame.shape[:2]
                    x_min_px = int(x_min * frame_width)
                    y_min_px = int(y_min * frame_height)
                    y_max_px = int(y_max * frame_height)

                    # Get gesture classification results
                    if self.recognition_result_list[0].gestures:
                        gesture = self.recognition_result_list[0].gestures[hand_index]
                        category_name = cast(str, gesture[0].category_name)
                        score = cast(float, gesture[0].score)
                        score_rounded = round(score, 2)
                        result_text = f'{category_name} ({score_rounded})'.capitalize()

                        # Reset confidence timer if gesture changed
                        if category_name != self.prev_category_name:
                            self.prev_category_name = category_name
                            self.confidence_timer = 0

                        # Color text based on confidence level
                        text_color = self.label_text_color
                        if score >= 0.8:
                            gradient_factor = (score - 0.8) / 0.2
                            text_color = (0, 255, int(255 * (1 - gradient_factor)))  # green

                            self.confidence_timer += cur_time - self.prev_time

                            if self.confidence_timer >= 1:
                                self.append_text(category_name)
                                self.confidence_timer = 0
                        elif score >= 0.6:
                            gradient_factor = (score - 0.6) / 0.2
                            db = self.label_text_color[0]
                            dg = self.label_text_color[1]
                            dr = self.label_text_color[2]
                            text_color = (
                                int(db * (1 - gradient_factor)),
                                int(dg + (255 - dg) * gradient_factor),
                                int(dr + (255 - dr) * gradient_factor),
                            )  # yellow
                            self.confidence_timer = 0
                        else:
                            self.confidence_timer = 0

                        # Compute and draw label text above hand
                        text_size = cv2.getTextSize(result_text, cv2.FONT_HERSHEY_DUPLEX,
                                                    self.label_font_size, self.label_thickness)[0]
                        text_x = x_min_px
                        text_y = y_min_px - 10
                        if text_y < 0:
                            text_y = y_max_px + text_size[1]

                        cv2.putText(current_frame, result_text, (text_x, text_y),
                                    cv2.FONT_HERSHEY_DUPLEX, self.label_font_size,
                                    text_color, self.label_thickness, cv2.LINE_AA)

                    # Draw hand landmarks
                    hand_landmarks_proto = landmark_pb2.NormalizedLandmarkList()
                    hand_landmarks_proto.landmark.extend([
                        landmark_pb2.NormalizedLandmark(x=lm.x, y=lm.y, z=lm.z)
                        for lm in hand_landmarks
                    ])
                    mp_drawing.draw_landmarks(
                        current_frame,
                        hand_landmarks_proto,
                        mp_hands.HAND_CONNECTIONS,
                        mp_drawing_styles.get_default_hand_landmarks_style(),
                        mp_drawing_styles.get_default_hand_connections_style())

                self.recognition_frame = current_frame
                self.recognition_result_list.clear()

            if self.recognition_frame is not None:
                # Scale the frame to fill the label while keeping aspect ratio
                label_w = self.image_label.width()
                label_h = self.image_label.height()
                image = QImage(
                    self.recognition_frame.data,
                    self.recognition_frame.shape[1],
                    self.recognition_frame.shape[0],
                    self.recognition_frame.strides[0],
                    QImage.Format.Format_BGR888,
                )
                pixmap = QPixmap.fromImage(image).scaled(
                    label_w, label_h,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self.image_label.setPixmap(pixmap)
        else:
            blank = QPixmap(self.image_label.size())
            blank.fill(QColorConstants.Black)
            self.image_label.setPixmap(blank)

        self.prev_time = cur_time


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())