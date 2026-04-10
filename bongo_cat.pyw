import sys
import traceback
import threading
import time
import os
from pynput import keyboard, mouse
import pygame
from PyQt6.QtWidgets import QApplication, QMainWindow, QMenu, QLabel
from PyQt6.QtCore import (Qt, QTimer, QPoint, QEasingCurve,
                           QPropertyAnimation, QSequentialAnimationGroup,
                           pyqtSignal, QObject, QPauseAnimation)
from PyQt6.QtGui import QPixmap, QTransform

def excepthook(type, value, tb):
    with open("C:/Users/surfi/OneDrive/Desktop/Code/BongoBass/crash.log", "w") as f:
        traceback.print_exception(type, value, tb, file=f)

sys.excepthook = excepthook

# --- CONFIG ---
TASKBAR_H = 48        
GRAVITY_STRENGTH = 0.8 
TOSS_POWER_X = 60      
TOSS_POWER_Y = 1.8     
MAX_BOUNCE = 50       
MIN_BOUNCE_DROP = 40  
SAVE_INTERVAL = 30000 
MILESTONE_STEP = 500    
WPM_DECAY_MS = 100
WPM_ALPHA = 0.1
THEMES = {
    "SCV": "SCV",
    "BD": "BD",
    "DRUMSET": "DRUMSET"
}
DEFAULT_THEME = "SCV"

# ---------------------------------------------------------------------------
# Load PNG frames from files
# ---------------------------------------------------------------------------
if getattr(sys, 'frozen', False):
    BASE_DIR = sys._MEIPASS
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SAVE_FILE = os.path.join(BASE_DIR, "drummer_hits.txt")
def _load_png(filename):
    try:
        path = os.path.join(BASE_DIR, "img", filename)
        px = QPixmap(path)
        if px.isNull():
            return None
        return px.scaled(200, 200, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.FastTransformation)    
    except Exception as e:
        print(f"Failed to load {filename}: {e}")
        return None

class GlobalSignals(QObject):
    keystroke = pyqtSignal()
    mouse_click = pyqtSignal()
    mouse_scroll = pyqtSignal()

global_signals = GlobalSignals()

# Backup SVG Generator for fallback drummer (if PNGs fail to load)

def get_svg_frame(frame_type, count):
    if count >= 1000000: display_count = f"{count/1000000:.2f}M"
    elif count >= 1000: display_count = f"{count/1000:.1f}k"
    else: display_count = str(count)
    
    counter_xml = f'<text x="70" y="182" font-family="Arial" font-size="10" font-weight="bold" fill="#EEEDFE" opacity="0.5" text-anchor="middle">{display_count}</text>'
    
    round_eyes = '<circle cx="62" cy="71" r="3" fill="#333"/><circle cx="78" cy="71" r="3" fill="#333"/>'
    squinty_eyes = '<path d="M58 70 Q62 66 66 70" fill="none" stroke="#333" stroke-width="2" stroke-linecap="round"/><path d="M74 70 Q78 66 82 70" fill="none" stroke="#333" stroke-width="2" stroke-linecap="round"/>'
    smile = '<path d="M61 81 Q70 90 79 81" fill="none" stroke="#333" stroke-width="2" stroke-linecap="round"/>'
    frown = '<path d="M61 85 Q70 76 79 85" fill="none" stroke="#333" stroke-width="2" stroke-linecap="round"/>'
    big_exclaim = '<text x="70" y="25" font-family="Arial Rounded MT Bold, Arial, sans-serif" font-size="40" font-weight="bold" fill="#FFD700" text-anchor="middle">!</text>'
    
    l_up = '<line x1="46" y1="105" x2="18" y2="82" stroke="#534AB7" stroke-width="6" stroke-linecap="round"/><line x1="18" y1="82" x2="7" y2="60" stroke="#8B7355" stroke-width="3.5" stroke-linecap="round"/>'
    r_up = '<line x1="94" y1="105" x2="122" y2="82" stroke="#534AB7" stroke-width="6" stroke-linecap="round"/><line x1="122" y1="82" x2="133" y2="60" stroke="#8B7355" stroke-width="3.5" stroke-linecap="round"/>'
    l_down = '<line x1="46" y1="105" x2="26" y2="135" stroke="#534AB7" stroke-width="6" stroke-linecap="round"/><line x1="26" y1="135" x2="20" y2="155" stroke="#8B7355" stroke-width="3.5" stroke-linecap="round"/>'
    r_down = '<line x1="94" y1="105" x2="114" y2="130" stroke="#534AB7" stroke-width="6" stroke-linecap="round"/><line x1="114" y1="130" x2="124" y2="140" stroke="#8B7355" stroke-width="3.5" stroke-linecap="round"/>'

    cymbals = """
        <ellipse cx="14" cy="135" rx="16" ry="4" fill="#BA7517" opacity="0.85"/>
        <line x1="14" y1="139" x2="14" y2="200" stroke="#777" stroke-width="1.5"/>
        <ellipse cx="126" cy="135" rx="16" ry="4" fill="#BA7517" opacity="0.85"/>
        <line x1="126" y1="139" x2="126" y2="200" stroke="#777" stroke-width="1.5"/>
    """

    svg_base = f"""<svg width="140" height="200" viewBox="0 0 140 200" xmlns="http://www.w3.org/2000/svg">
        <ellipse cx="70" cy="165" rx="52" ry="52" fill="#3C3489" opacity="0.92"/>
        <ellipse cx="70" cy="165" rx="37" ry="37" fill="none" stroke="#EEEDFE" stroke-width="1.5" opacity="0.5"/>
        <circle cx="70" cy="165" r="5" fill="#EEEDFE" opacity="0.4"/>
        {counter_xml}
        {cymbals}
        <rect x="46" y="92" width="48" height="50" rx="10" fill="#534AB7"/>
        <circle cx="70" cy="74" r="22" fill="#FAC775"/>"""

    if frame_type == "IDLE": content = round_eyes + smile + l_up + r_up
    elif frame_type == "LEFT": content = round_eyes + smile + l_down + r_up
    elif frame_type == "RIGHT": content = round_eyes + smile + l_up + r_down
    elif frame_type == "IMPACT": content = squinty_eyes + frown + l_down + r_down
    elif frame_type == "CEL_UP": content = squinty_eyes + smile + l_up + r_up + big_exclaim
    elif frame_type == "CEL_DOWN": content = squinty_eyes + smile + l_down + r_down + big_exclaim
    
    return svg_base + content + "</svg>"

class DrummerWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet("background: transparent;")
        self.setFixedSize(200, 200)

        # Context Menu for quitting
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        self._show_counter = True
        self._is_flipped = False 
        self.current_theme = "SCV"       
        self._load_hits()

        # --- WPM Tracking ---
        self.keystroke_times = [] 
        self.current_wpm = 0
        self.wpm_timer = QTimer()
        self.wpm_timer.timeout.connect(self._calculate_wpm)
        self.wpm_timer.start(WPM_DECAY_MS)

        # --- CELEBRATION & ANIMATION STATE ---
        self._is_dirty = False 
        self._is_celebrating = False
        self._last_milestone = (self.hit_count // MILESTONE_STEP) * MILESTONE_STEP
        self.hit_right_next = False
        
        self._desktop = QApplication.primaryScreen().virtualGeometry()
        primary_geo = QApplication.primaryScreen().geometry()
        self._rest_y = primary_geo.height() - TASKBAR_H - self.height()
        self.move(primary_geo.width() - self.width(), self._rest_y)

        self.img_label = QLabel(self)
        self.img_label.setGeometry(0, 0, 200, 200)
        self.img_label.setStyleSheet("background: transparent;")
        self.img_label.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.counter_label = QLabel(self)
        if self._is_flipped:
            self.counter_label.setGeometry(50, 185, 80, 50)
        else:
            self.counter_label.setGeometry(110, 185, 80, 50)
        self.counter_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter )
        self.counter_label.setStyleSheet("""
            color: white;
            font-family: Arial Black, Arial;
            font-size: 9px;
            font-weight: 900;
            line-height: 0.8;
            background: transparent;
            letter-spacing: 1px;
        """)
        self.counter_label.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.counter_label.setAutoFillBackground(False)
        self._update_counter()

        self.reset_timer = QTimer(); self.reset_timer.setSingleShot(True)
        self.reset_timer.timeout.connect(self._idle)
        self.save_timer = QTimer(); self.save_timer.timeout.connect(self._save_hits)
        self.save_timer.start(SAVE_INTERVAL)

        global_signals.keystroke.connect(self._on_key)
        global_signals.mouse_click.connect(self._on_click)
        global_signals.mouse_scroll.connect(self._on_scroll)

        self._drag_pos = None; self._anim_group = None; self._velocity = QPoint(0, 0)
        self._is_tacet = False
        self._errors = []
        self._update_assets()
        self._idle()

    # Menu with options to turn, toggle tacet mode, and quit

    def _show_context_menu(self, pos):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background-color: #3C3489; color: white; border: 1px solid #534AB7; padding: 5px; }
            QMenu::item:selected { background-color: #534AB7; }
            QMenu::item:disabled { color: #FF5555; }
            QMenu::indicator { width: 13px; height: 13px; }
        """)

        if self._errors:
            for err in self._errors:
                # Show just the last line of each traceback — most useful part
                short = [l.strip() for l in err.strip().splitlines() if l.strip()][-1]
                err_action = menu.addAction(f"⚠ {short}")
                err_action.setEnabled(False)
                err_action.setData(err)
            
            clear_action = menu.addAction("Clear Errors")
            menu.addSeparator()

        turn_action = menu.addAction("Turn (180°)")
        menu.addSeparator()

        tacet_action = menu.addAction("Tacet")
        tacet_action.setCheckable(True)
        tacet_action.setChecked(self._is_tacet)

        counter_action = menu.addAction("Show Counter")
        counter_action.setCheckable(True)
        counter_action.setChecked(self._show_counter)        
        menu.addSeparator()
        
        theme_menu = menu.addMenu("Theme")
        theme_menu.setStyleSheet(menu.styleSheet())
        
        scv_act = theme_menu.addAction("SCV")
        bd_act = theme_menu.addAction("BD")
        ds_act = theme_menu.addAction("DRUMSET")
        
        # Make them checkable to show which is active
        scv_act.setCheckable(True); scv_act.setChecked(self.current_theme == "SCV")
        bd_act.setCheckable(True); bd_act.setChecked(self.current_theme == "BD")
        ds_act.setCheckable(True); ds_act.setChecked(self.current_theme == "DRUMSET")
        
        menu.addSeparator()

        reset_action = menu.addAction("Reset Counter")
        menu.addSeparator()
        quit_action = menu.addAction("Quit Drummer")

        action = menu.exec(self.mapToGlobal(pos))

        if action == clear_action if self._errors else None:
            self._errors.clear()
            return
        
        # --- THEME SELECTION ---
        if action == scv_act:
            self._set_theme("SCV")
        elif action == bd_act:
            self._set_theme("BD")
        elif action == ds_act:
            self._set_theme("DRUMSET")

        if action == turn_action:
            self._is_flipped = not self._is_flipped
            self._update_counter()  # Move counter to other side
            self._idle()
        elif action == tacet_action:
            self._is_tacet = not self._is_tacet
            self._idle()
        elif action == counter_action:
            self._show_counter = not self._show_counter
            self._update_counter()
        elif action == reset_action:
            self.hit_count = 0
            self._last_milestone = 0
            self._is_dirty = True
            self._save_hits()
            self._update_counter()
        elif action == quit_action:
            self._save_hits()
            QApplication.quit()

    def _calculate_wpm(self):
        now = time.time()
        # Look back 2 seconds
        self.keystroke_times = [t for t in self.keystroke_times if now - t < 2]
        
        if not self.keystroke_times:
            instant_wpm = 0
        else:
            keys = len(self.keystroke_times)
            # (Keys / 5) / (2 / 60 minutes)
            instant_wpm = (keys / 5) / (2 / 60)

        self.current_wpm = (instant_wpm * WPM_ALPHA) + (self.current_wpm * (1 - WPM_ALPHA))
        
        if self.current_wpm < 0.5: self.current_wpm = 0
        self._update_counter()

    def _update_counter(self):
        if not hasattr(self, 'counter_label') or not self._show_counter:
            return
        
        # ... (Your existing count formatting: 1.2k, etc.) ...
        count = self.hit_count
        if count >= 1000: display = f"{count/1000:.2f}k"
        else: display = str(count)

        # Add the WPM to the label
        full_text = f"{display}\n{int(self.current_wpm)} WPM"
        self.counter_label.setText(full_text)
        
        # Adjust label height to fit two lines
        self.counter_label.setFixedHeight(40)

    def _load_hits(self):
        try:
            if os.path.exists(SAVE_FILE):
                with open(SAVE_FILE, "r") as f: self.hit_count = int(f.read().strip())
            else: self.hit_count = 0
        except: self.hit_count = 0

    def _save_hits(self):
        if self._is_dirty:
            try:
                with open(SAVE_FILE, "w") as f: f.write(str(self.hit_count))
                self._is_dirty = False
            except: pass

    def _update_assets(self):
            """Reloads PNGs based on the current theme prefix."""
            if self.current_theme == "DRUMSET":
                # Clear PNGs so the logic falls back to SVG
                self.PNG_IDLE = self.PNG_LEFT = self.PNG_RIGHT = self.PNG_DOWN = None
            else:
                prefix = self.current_theme
                self.PNG_IDLE  = _load_png(f"{prefix}set.png")
                self.PNG_LEFT  = _load_png(f"{prefix}left.png")
                self.PNG_RIGHT = _load_png(f"{prefix}right.png")
                self.PNG_DOWN  = _load_png(f"{prefix}down.png")
            
            self._idle() # Refresh the visual immediately

    def _set_theme(self, theme_name):
        self.current_theme = theme_name
        self._update_assets()

    def _set_frame(self, frame_type):
        if self._is_tacet and frame_type not in ("CEL_UP", "CEL_DOWN"):
            px = self.PNG_DOWN or self.PNG_IDLE
        elif frame_type in ("IDLE", "CEL_UP"):
            px = self.PNG_IDLE
        elif frame_type == "LEFT":
            px = self.PNG_LEFT
        elif frame_type in ("RIGHT", "IMPACT", "CEL_DOWN"):
            px = self.PNG_RIGHT
        else:
            px = self.PNG_IDLE

        if px is not None:
            if self._is_flipped:
                px = px.transformed(QTransform().scale(-1, 1))
            self.img_label.setPixmap(px)
        else:
            self._set_svg_frame(frame_type)
            
    def _set_svg_frame(self, frame_type):
        from PyQt6.QtSvg import QSvgRenderer
        from PyQt6.QtCore import QByteArray
        from PyQt6.QtGui import QPainter

        svg_data = get_svg_frame(frame_type, self.hit_count)
        renderer = QSvgRenderer(QByteArray(svg_data.encode('utf-8')))

        px = QPixmap(200, 200)
        px.fill(Qt.GlobalColor.transparent)
        painter = QPainter(px)
        renderer.render(painter)
        painter.end()

        if self._is_flipped:
            px = px.transformed(QTransform().scale(-1, 1))

        self.img_label.setPixmap(px)
        
    def _on_key(self):
        self.hit_count += 1
        self.keystroke_times.append(time.time())
        self._update_counter()

        self._is_dirty = True
        if self.hit_count >= self._last_milestone + MILESTONE_STEP:
            self._last_milestone = (self.hit_count // MILESTONE_STEP) * MILESTONE_STEP
            self._trigger_celebration()
        
        if not self._is_celebrating:
            self._set_frame("RIGHT" if self.hit_right_next else "LEFT")
            self.hit_right_next = not self.hit_right_next
            self.reset_timer.start(150)

    def _trigger_celebration(self):
        if self._is_celebrating: return
        self._is_celebrating = True
        if self._anim_group: self._anim_group.stop()

        self.cel_anim = QSequentialAnimationGroup()
        base_x = self.x()

        # One full 720 = 4 half-turns (each half-turn = one up/down bounce)
        # Flipping between normal and flipped simulates rotation
        spin_states = [False, True, False, True, False]  # start and end facing same way

        for i, flipped in enumerate(spin_states[:-1]):
            self._is_flipped = flipped
            frame_up = "CEL_UP" if not self._is_tacet else "IDLE"
            frame_down = "CEL_DOWN" if not self._is_tacet else "IMPACT"

            up = QPropertyAnimation(self, b"pos")
            up.setStartValue(QPoint(base_x, self._rest_y))
            up.setEndValue(QPoint(base_x, self._rest_y - 30))
            up.setDuration(100)
            up.setEasingCurve(QEasingCurve.Type.OutQuad)

            up.finished.connect(lambda ft=frame_up, f=flipped: (
                setattr(self, '_is_flipped', f) or self._set_frame(ft)
            ))

            down = QPropertyAnimation(self, b"pos")
            down.setStartValue(QPoint(base_x, self._rest_y - 30))
            down.setEndValue(QPoint(base_x, self._rest_y))
            down.setDuration(90)
            down.setEasingCurve(QEasingCurve.Type.InQuad)

            next_flip = spin_states[i + 1]
            down.finished.connect(lambda fd=frame_down, f=next_flip: (
                setattr(self, '_is_flipped', f) or self._set_frame(fd)
            ))

            self.cel_anim.addAnimation(up)
            self.cel_anim.addAnimation(down)
            self.cel_anim.addAnimation(QPauseAnimation(40))

        # Final hold then land
        final_hold = QPauseAnimation(600)
        self.cel_anim.addAnimation(final_hold)
        self.cel_anim.finished.connect(self._stop_celebration)
        self.cel_anim.start()

    def _stop_celebration(self):
        self._is_celebrating = False
        self._is_flipped = False  # Always land facing original direction
        self._idle()

    def _on_click(self):
        self._on_key()

    def _on_scroll(self):
        if not self._is_celebrating:
            self._set_frame("RIGHT" if self.hit_right_next else "LEFT")
            self.hit_right_next = not self.hit_right_next
            self.reset_timer.start(40)

    def _update_counter(self):
        if not hasattr(self, 'counter_label') or not self._show_counter:
            self.counter_label.hide()
            return
            
        self.counter_label.show()
        
        # 1. Format the Total Hits (Existing logic)
        count = self.hit_count
        if count >= 1000000: display_hits = f"{count/1000000:.2f}M"
        elif count >= 1000: display_hits = f"{count/1000:.1f}k"
        else: display_hits = str(count)
        
        # 2. Format the WPM (New logic)
        # We'll use int() to keep it from flickering with decimals
        display_wpm = f"{int(self.current_wpm)} WPM"
        
        # 3. Push to UI
        # This creates two lines: The total count on top, WPM on bottom
        self.counter_label.setText(f"{display_hits}\n{display_wpm}")
        
        # Ensure the position is correct based on flip
        if self._is_flipped:
            self.counter_label.move(50, 165)
        else:
            self.counter_label.move(110, 165)

    def _idle(self):
        if not self._is_celebrating:
            self._set_frame("IDLE")

    def _drop_and_settle(self):
        horiz_flick = self._velocity.x() * TOSS_POWER_X
        vert_boost = self._velocity.y() * TOSS_POWER_Y if self._velocity.y() < 0 else 0
        final_x = max(self._desktop.left(), min(self.x() + horiz_flick, self._desktop.right() - self.width()))
        peak_y = self.y() + vert_boost
        self._last_drop_dist = self._rest_y - peak_y
        total_ms = max(200, min(800, int(self._last_drop_dist * GRAVITY_STRENGTH)))

        if self._anim_group: self._anim_group.stop()
        start_pos = self.pos(); peak_pos = QPoint(int(self.x() + (horiz_flick * 0.6)), int(peak_y))
        settle_pos = QPoint(final_x, self._rest_y)

        self._anim_group = QSequentialAnimationGroup()
        if vert_boost < -5 or abs(horiz_flick) > 10:
            up = QPropertyAnimation(self, b"pos")
            up.setStartValue(start_pos); up.setEndValue(peak_pos); up.setDuration(int(total_ms * 0.4)); up.setEasingCurve(QEasingCurve.Type.OutQuad)
            self._anim_group.addAnimation(up)

        down = QPropertyAnimation(self, b"pos")
        down.setStartValue(peak_pos if self._anim_group.animationCount() > 0 else start_pos)
        down.setEndValue(settle_pos); down.setDuration(total_ms); down.setEasingCurve(QEasingCurve.Type.InCubic)
        self._anim_group.addAnimation(down)
        self._anim_group.finished.connect(self._handle_landing); self._anim_group.start()

    def _handle_landing(self):
        try: self._anim_group.finished.disconnect()
        except: pass
        if self._last_drop_dist > MIN_BOUNCE_DROP:
            self._start_impact_bounce()
        else: self._idle()

    def _start_impact_bounce(self):
        self._set_frame("IMPACT") 
        self.bounce_group = QSequentialAnimationGroup()
        bounce_peak = QPoint(self.x(), self._rest_y - MAX_BOUNCE)
        b_up = QPropertyAnimation(self, b"pos"); b_up.setStartValue(self.pos()); b_up.setEndValue(bounce_peak); b_up.setDuration(120); b_up.setEasingCurve(QEasingCurve.Type.OutQuad)
        b_down = QPropertyAnimation(self, b"pos"); b_down.setStartValue(bounce_peak); b_down.setEndValue(QPoint(self.x(), self._rest_y)); b_down.setDuration(100); b_down.setEasingCurve(QEasingCurve.Type.InQuad)
        self.bounce_group.addAnimation(b_up); self.bounce_group.addAnimation(b_down)
        self.bounce_group.finished.connect(lambda: QTimer.singleShot(50, self._idle)); self.bounce_group.start()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self._anim_group: self._anim_group.stop()
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self._last_mouse_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() == Qt.MouseButton.LeftButton:
            current_pos = event.globalPosition().toPoint()
            self._velocity = current_pos - self._last_mouse_pos
            self._last_mouse_pos = current_pos
            self.move(current_pos - self._drag_pos)

    def mouseReleaseEvent(self, event):
        if self._drag_pos: self._drop_and_settle(); self._drag_pos = None

def start_controller_listener():
    pygame.init()
    pygame.joystick.init()
    
    if pygame.joystick.get_count() == 0:
        return

    # Find first actual joystick/gamepad, skip mice and other HID devices
    joystick = None
    for i in range(pygame.joystick.get_count()):
        j = pygame.joystick.Joystick(i)
        j.init()
        name = j.get_name().lower()
        # Skip if it looks like a mouse or non-gamepad HID device
        if any(x in name for x in ("mouse", "trackpad", "touchpad", "keyboard")):
            j.quit()
            continue
        joystick = j
        break

    if joystick is None:
        return

    held_buttons = set()

    while True:
        # Use event queue instead of polling — much more precise
        for event in pygame.event.get():
            # Button press only — not release
            if event.type == pygame.JOYBUTTONDOWN:
                if event.button not in held_buttons:
                    held_buttons.add(event.button)
                    global_signals.keystroke.emit()

            elif event.type == pygame.JOYBUTTONUP:
                held_buttons.discard(event.button)

            # Analog triggers only (not thumbsticks)
            elif event.type == pygame.JOYAXISMOTION:
                # Only care about trigger axes (2 = L2, 5 = R2 on PS4)
                if event.axis in (2, 5):
                    if event.value > 0.5 and event.axis not in held_buttons:
                        held_buttons.add(event.axis)
                        global_signals.keystroke.emit()
                    elif event.value <= 0.5 and event.axis in held_buttons:
                        held_buttons.discard(event.axis)

        pygame.time.wait(16)

held_keys = set()
def start_listeners():
    def on_press(key):
        if key not in held_keys: held_keys.add(key); global_signals.keystroke.emit()
    def on_release(key):
        if key in held_keys: held_keys.remove(key)
    def on_click(x, y, button, pressed):
        if pressed: global_signals.mouse_click.emit()
    def on_scroll(x, y, dx, dy): global_signals.mouse_scroll.emit()
    with keyboard.Listener(on_press=on_press, on_release=on_release) as k, mouse.Listener(on_click=on_click, on_scroll=on_scroll) as m:
        k.join(); m.join()

if __name__ == "__main__":
    try:
        app = QApplication(sys.argv)
        win = DrummerWindow()
        win.show()
        def handle_exception(exc_type, exc_value, exc_traceback):
            import traceback
            msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
            win._errors.append(msg)

        sys.excepthook = handle_exception
        threading.Thread(target=start_listeners, daemon=True).start()
        threading.Thread(target=start_controller_listener, daemon=True).start()
        sys.exit(app.exec())

    except Exception:
        with open("C:/Users/surfi/OneDrive/Desktop/Code/BongoBass/crash.log", "w") as f:
            traceback.print_exc(file=f)