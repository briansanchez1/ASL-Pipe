import sys
import time

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

# Global variables to calculate FPS
COUNTER, FPS = 0, 0
START_TIME = time.time()

class MotionTracker:
    def __init__(self, history_len=20):
        self.history = []  # list of (x, y) normalized coords
        self.history_len = history_len

    def update(self, x, y):
        self.history.append((x, y))
        if len(self.history) > self.history_len:
            self.history.pop(0)

    def get_directions(self, threshold=0.015):
        """Returns list of direction strings from recent movement"""
        dirs = []
        for i in range(1, len(self.history)):
            dx = self.history[i][0] - self.history[i-1][0]
            dy = self.history[i][1] - self.history[i-1][1]
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

    def detect_j(self):
        """Detect J using hand landmarks and motion detection sequences"""
        dirs = self.get_directions()
        collapsed = [dirs[i] for i in range(len(dirs)) if i == 0 or dirs[i] != dirs[i-1]]
        # down (left or down-left)
        try:
            d_idx = collapsed.index("down")
            rest = collapsed[d_idx+1:]
            if any(d in rest for d in ["left", "down-left"]):
                return True
        except ValueError:
            pass
        return False

    def detect_z(self):
        """Detect Z using hand landmarks and motion detection sequences"""
        dirs = self.get_directions()
        collapsed = [dirs[i] for i in range(len(dirs)) if i == 0 or dirs[i] != dirs[i-1]]
        # right -> down left ->right
        try:
            r1 = collapsed.index("right")
            dl = collapsed.index("down-left", r1+1)
            r2 = collapsed.index("right", dl+1)
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
    fps_avg_frame_count = 10

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
        self.camera = None
        self.image_label = QLabel()
        self.image_label.setMinimumSize(400, 400)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

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
        layout.addWidget(self.image_label)
        layout.addWidget(self.output_label)

        self.timer = QTimer()
        self.timer.timeout.connect(self.display_video_stream)
        self.timer.start(30)

        self.recognition_frame = None
        self.recognition_result_list = []

        def save_result(result: vision.GestureRecognizerResult,
                        unused_output_image: mp.Image, timestamp_ms: int):
            global FPS, COUNTER, START_TIME

            # Calculate the FPS
            if COUNTER % self.fps_avg_frame_count == 0:
                FPS = self.fps_avg_frame_count / (time.time() - START_TIME)
                START_TIME = time.time()

            self.recognition_result_list.append(result)
            COUNTER += 1

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
        self.motion_cooldown = 0  # prevent spam


    def append_text(self, new_text):
        """Append new letter to output"""
        self.output_label.setText(self.output_label.text() + new_text)
        
    def clear_output(self):
        """Clear the output generated by user"""
        self.output_label.setText("")
    
    def populate_cameras(self):
        """
        Fill the camera list dropdown with available camera devices
        """
        if self.camera:
            self.camera.release()
        self.camera = None
        self.camera_dropdown.clear()
        cameras = enumerate_cameras()

        if not cameras:
            self.camera_dropdown.addItem("No cameras found")
            return

        for camera in cameras:
            self.camera_dropdown.addItem(
                camera.name,
                camera.index,
            )

    def start_camera(self):
        """Start the camera based on the selected index"""
        index = self.camera_dropdown.currentData()

        if index is None or index < 0:
            return

        if self.camera:
            self.camera.release()

        self.camera = cv2.VideoCapture(index)

    confidence_timer = 0
    prev_time = time.time()
    prev_category_name = None

    def display_video_stream(self):
        """Read frame from camera and repaint QLabel widget."""
        cur_time = time.time()
        if self.camera:
            _, frame = self.camera.read()
            frame = cv2.flip(frame, 1)
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

            # Run gesture recognizer using the model.
            self.recognizer.recognize_async(mp_image, time.time_ns() // 1_000_000)

            # Show the FPS
            fps_text = 'FPS = {:.1f}'.format(FPS)
            text_location = (self.left_margin, self.row_size)
            current_frame = frame
            cv2.putText(current_frame, fps_text, text_location, cv2.FONT_HERSHEY_DUPLEX,
                        self.font_size, self.text_color, self.font_thickness, cv2.LINE_AA)

            if self.recognition_result_list:
                # Draw landmarks and write the text for each hand.
                for hand_index, hand_landmarks in enumerate(
                        self.recognition_result_list[0].hand_landmarks):
                    # Track pinky tip for J and index tip for Z
                    pinky = hand_landmarks[20]
                    index = hand_landmarks[8]
                    self.j_tracker.update(pinky.x, pinky.y)
                    self.z_tracker.update(index.x, index.y)

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
                    x_min = min([landmark.x for landmark in hand_landmarks])
                    y_min = min([landmark.y for landmark in hand_landmarks])
                    y_max = max([landmark.y for landmark in hand_landmarks])

                    # Convert normalized coordinates to pixel values
                    frame_height, frame_width = current_frame.shape[:2]
                    x_min_px = int(x_min * frame_width)
                    y_min_px = int(y_min * frame_height)
                    y_max_px = int(y_max * frame_height)

                    # Get gesture classification results
                    if self.recognition_result_list[0].gestures:
                        gesture = self.recognition_result_list[0].gestures[hand_index]
                        category_name = gesture[0].category_name
                        score = gesture[0].score
                        score_rounded = round(score, 2)
                        result_text = f'{category_name} ({score_rounded})'.capitalize()

                        # If the hand sign has changed since the previous recognition, reset the confidence timer
                        if category_name != self.prev_category_name:
                            self.prev_category_name = category_name
                            self.confidence_timer = 0

                        # Color the on-screen confidence text based on how high the confidence is
                        text_color = self.label_text_color
                        if score >= 0.8:
                            # When score = 0.8, factor = 0.0, and the text color is yellow
                            # When score = 1.0, factor = 1.0, and the text color is green
                            gradient_factor = (score - 0.8) / 0.2
                            text_color = (0, 255, 255 * (1 - gradient_factor))  # Green - high accuracy

                            self.confidence_timer += cur_time - self.prev_time

                            # If the confidence score has been >= 0.8 for at least 1 second,
                            # append the symbol to the output and reset the confidence timer
                            if self.confidence_timer >= 1:
                                self.append_text(category_name)
                                self.confidence_timer = 0
                        elif score >= 0.6:
                            # When score = 0.6, factor = 0.0, and the text color is self.label_text_color
                            # When score = 0.79999, factor = 1.0, and the text color is yellow
                            gradient_factor = (score - 0.6) / 0.2

                            default_color_b = self.label_text_color[0]
                            default_color_g = self.label_text_color[1]
                            default_color_r = self.label_text_color[2]

                            text_color = (default_color_b * (1 - gradient_factor),
                                          default_color_g + (255 - default_color_g) * gradient_factor,
                                          default_color_r + (255 - default_color_r) * gradient_factor)  # Yellow - medium accuracy

                            # Confidence isn't high enough, so reset the confidence timer
                            self.confidence_timer = 0
                        else:
                            # Confidence isn't high enough, so reset the confidence timer
                            self.confidence_timer = 0

                        # Compute text size
                        text_size = \
                            cv2.getTextSize(result_text, cv2.FONT_HERSHEY_DUPLEX, self.label_font_size,
                                            self.label_thickness)[0]
                        text_width, text_height = text_size

                        # Calculate text position (above the hand)
                        text_x = x_min_px
                        text_y = y_min_px - 10  # Adjust this value as needed

                        # Make sure the text is within the frame boundaries
                        if text_y < 0:
                            text_y = y_max_px + text_height

                        # Draw the text
                        cv2.putText(current_frame, result_text, (text_x, text_y),
                                    cv2.FONT_HERSHEY_DUPLEX, self.label_font_size,
                                    text_color, self.label_thickness, cv2.LINE_AA)

                    # Draw hand landmarks on the frame
                    hand_landmarks_proto = landmark_pb2.NormalizedLandmarkList()
                    hand_landmarks_proto.landmark.extend([
                        landmark_pb2.NormalizedLandmark(x=landmark.x, y=landmark.y,
                                                        z=landmark.z) for landmark in
                        hand_landmarks
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
                image = QImage(self.recognition_frame, self.recognition_frame.shape[1],
                               self.recognition_frame.shape[0],
                               self.recognition_frame.strides[0], QImage.Format.Format_BGR888)
                self.image_label.setPixmap(QPixmap.fromImage(image))
        else:
            image = QPixmap(self.image_label.size())
            QPixmap.fill(image, QColorConstants.Black)
            self.image_label.setPixmap(image)
        self.prev_time = cur_time


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
