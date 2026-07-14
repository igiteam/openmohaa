#!/usr/bin/env python3
"""
PS3 DualShock 3 - GUI CONTROLLER WITH D-PAD CLICK PRECISION AIMING
Fixed triggers - No spamming!
Scrollable GUI - All buttons visible!
"""

import pygame
import sys
import time
import os
import threading
import queue
import math
import tkinter as tk
from tkinter import ttk
import pyautogui

# Set SDL environment variables BEFORE importing pygame
os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'

try:
    import keyboard
    from pynput.mouse import Controller as MouseController
    from pynput.mouse import Button as MouseButton
except ImportError:
    print("Installing required libraries...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "keyboard", "pynput", "pygame"])
    import keyboard
    from pynput.mouse import Controller as MouseController
    from pynput.mouse import Button as MouseButton

# ============================================
# CONFIGURATION
# ============================================

DEFAULT_SETTINGS = {
    'mouse_sensitivity': 0.18,
    'axis_deadzone': 0.30,
    'trigger_deadzone': 0.35,
    'button_debounce': 0.05,
    'invert_y': False,
    'smoothing': 0.0,
    'boost': 1.0,
    'dpad_step': 5,  # D-pad step size in pixels per click
    'dpad_precision': True,  # Use D-pad for precision mouse
    'dpad_click_mode': False,  # Click mode (True) vs Hold mode (False)
    'mouse_margin': 5,  # ADD THIS - margin from screen edges
}

# ============================================
# PS3 MAPPINGS
# ============================================

PS3_BUTTONS = {
    0: 'CROSS',
    1: 'CIRCLE', 
    2: 'SQUARE',
    3: 'TRIANGLE',
    4: 'SELECT',
    5: 'PS',
    6: 'START',
    7: 'L3',
    8: 'R3',
    9: 'L1', 
    10: 'R1',
    11: 'DPAD_UP',
    12: 'DPAD_DOWN',
    13: 'DPAD_LEFT',
    14: 'DPAD_RIGHT',
}

# Map to Operation Flashpoint keys
# D-pad no longer maps to keys - now controls mouse
BUTTON_MAP = {
    'CROSS': 'v',
    'CIRCLE': 'r',
    'SQUARE': 'e',
    'TRIANGLE': 'space',
    'L1': 'shift',     
    'R1': 'k',              
    'L2': 'q',          
    'R2': 'MOUSE_LEFT', 
    'START': 'esc',
    'SELECT': 'tab',
    'L3': 'up',
    'R3': 'g',
    'PS': '',
}

# ============================================
# QUEUE FOR GUI UPDATES
# ============================================
gui_queue = queue.Queue(maxsize=10)

# ============================================
# PS3 CONTROLLER CLASS
# ============================================
class PS3Controller:
    def __init__(self):
        # Get screen size for mouse constraints
        self.screen_width, self.screen_height = pyautogui.size()
        
        os.environ['SDL_VIDEODRIVER'] = 'dummy'
        pygame.init()
        pygame.joystick.init()
        
        self.mouse = MouseController()
        self.keys_pressed = {}
        self.mouse_left_pressed = False
        self.mouse_right_pressed = False
        
        self.joystick = None
        self.button_count = 0
        # Add after other variables
        self.last_rs_move_time = 0
        self.rs_move_cooldown = 0.02  # 20ms between moves

        # Button states
        self.button_states = {}
        self.button_timestamps = {}
        self.last_button_read = {}
        
        # TRIGGER STATES (L2 and R2)
        self.trigger_states = {'L2': False, 'R2': False}
        self.trigger_values = {'L2': 0.0, 'R2': 0.0}
        self.trigger_timestamps = {'L2': 0, 'R2': 0}
        
        # D-Pad states for mouse movement
        self.dpad_mouse_state = {'UP': False, 'DOWN': False, 'LEFT': False, 'RIGHT': False}
        
        # D-Pad click tracking
        self.dpad_click_count = {'UP': 0, 'DOWN': 0, 'LEFT': 0, 'RIGHT': 0}
        self.dpad_last_click_time = {'UP': 0, 'DOWN': 0, 'LEFT': 0, 'RIGHT': 0}
        self.dpad_click_cooldown = 0.15  # 150ms between clicks
        
        # Calibration
        self.center_x = 0
        self.center_y = 0
        self.calibrated = False
        
        # Settings
        self.settings = DEFAULT_SETTINGS.copy()
        
        # Running flag
        self.running = True
        
        # Debug
        self.debug_mode = False
        self.frame_count = 0
        
        # Controller thread
        self.thread = None
        
        print("🎮 PS3 Controller initialized with D-Pad click precision aiming")

    def set_key_state(self, key, pressed):
        """Set keyboard or mouse state"""
        if key is None or key == '':
            return
        
        # Mouse handling
        if key == 'MOUSE_LEFT':
            if pressed and not self.mouse_left_pressed:
                self.mouse.press(MouseButton.left)
                self.mouse_left_pressed = True
            elif not pressed and self.mouse_left_pressed:
                self.mouse.release(MouseButton.left)
                self.mouse_left_pressed = False
            return
        
        elif key == 'MOUSE_RIGHT':
            if pressed and not self.mouse_right_pressed:
                self.mouse.press(MouseButton.right)
                self.mouse_right_pressed = True
            elif not pressed and self.mouse_right_pressed:
                self.mouse.release(MouseButton.right)
                self.mouse_right_pressed = False
            return
        
        # Keyboard handling
        try:
            if pressed:
                if not self.keys_pressed.get(key, False):
                    keyboard.press(key)
                    self.keys_pressed[key] = True
            else:
                if self.keys_pressed.get(key, False):
                    keyboard.release(key)
                    self.keys_pressed[key] = False
        except Exception as e:
            pass

    def safe_mouse_move(self, dx, dy):
        """Move mouse but keep it within screen bounds with margin"""
        current_x, current_y = self.mouse.position
        new_x = current_x + dx
        new_y = current_y + dy
        
        # Constrain the position
        new_x, new_y = self.constrain_mouse_position(new_x, new_y)
        
        # Only move if position changed
        if new_x != current_x or new_y != current_y:
            self.mouse.position = (new_x, new_y)
            return True
        return False

    def handle_dpad_click(self, direction, pressed):
        """Handle D-pad as click-to-move for precision aiming"""
        if not self.settings.get('dpad_precision', True):
            return
        
        # Update state for display
        self.dpad_mouse_state[direction] = pressed
        
        # Only handle press events (not release) for click mode
        if not pressed:
            return
        
        # Check if in click mode or hold mode
        click_mode = self.settings.get('dpad_click_mode', False)
        
        if click_mode:
            # CLICK MODE - move once per press
            current_time = time.time()
            
            # Check cooldown to prevent rapid clicks
            if current_time - self.dpad_last_click_time.get(direction, 0) < self.dpad_click_cooldown:
                return
            
            # Get step size
            step = self.settings.get('dpad_step', 5)
            
            # Move mouse in the direction
            if direction == 'UP':
                self.safe_mouse_move(0, -step)
                self.dpad_click_count['UP'] += 1
            elif direction == 'DOWN':
                self.safe_mouse_move(0, step)
                self.dpad_click_count['DOWN'] += 1
            elif direction == 'LEFT':
                self.safe_mouse_move(-step, 0)
                self.dpad_click_count['LEFT'] += 1
            elif direction == 'RIGHT':
                self.safe_mouse_move(step, 0)
                self.dpad_click_count['RIGHT'] += 1
            
            # Update last click time
            self.dpad_last_click_time[direction] = current_time
            
            # Auto-release after click (for display purposes)
            def release_dpad():
                self.dpad_mouse_state[direction] = False
            threading.Timer(0.05, release_dpad).start()

    # ===== ADD THIS METHOD - Constrain mouse to screen with margin =====
    def constrain_mouse_position(self, x, y):
        """Constrain mouse position within screen with margin"""
        margin = self.settings.get('mouse_margin', 5)
        
        # Constrain X
        if x < margin:
            x = margin
        elif x > self.screen_width - margin:
            x = self.screen_width - margin
        
        # Constrain Y
        if y < margin:
            y = margin
        elif y > self.screen_height - margin:
            y = self.screen_height - margin
        
        return int(x), int(y)

    def find_controller(self):
        """Find and initialize the PS3 controller"""
        print("🔍 Searching for PS3 controller...")
        
        count = pygame.joystick.get_count()
        if count == 0:
            print("❌ No joystick found!")
            return False
        
        for i in range(count):
            joy = pygame.joystick.Joystick(i)
            joy.init()
            name = joy.get_name()
            print(f"   Found: {name}")
            
            if 'PLAYSTATION' in name or 'PS3' in name or 'Sony' in name or 'Sixaxis' in name:
                self.joystick = joy
                self.button_count = joy.get_numbuttons()
                print(f"✅ Using: {name}")
                print(f"   Axes: {joy.get_numaxes()}, Buttons: {self.button_count}")
                
                # Initialize button states
                for btn_id, btn_name in PS3_BUTTONS.items():
                    if btn_id < self.button_count:
                        self.button_states[btn_name] = False
                        self.button_timestamps[btn_name] = 0
                        self.last_button_read[btn_name] = False
                
                return True
        
        # Fallback to first joystick
        if count > 0:
            self.joystick = pygame.joystick.Joystick(0)
            self.button_count = self.joystick.get_numbuttons()
            print(f"✅ Using first joystick: {self.joystick.get_name()}")
            return True
        
        return False

    def handle_triggers(self):
        """Handle L2 and R2 triggers (axes 4 and 5) - FIXED!"""
        if self.joystick is None or self.joystick.get_numaxes() < 6:
            return
        
        # Get raw trigger values
        l2_raw = self.joystick.get_axis(4)
        r2_raw = self.joystick.get_axis(5)
        
        # Store values for display
        self.trigger_values['L2'] = l2_raw
        self.trigger_values['R2'] = r2_raw
        
        trigger_deadzone = self.settings['trigger_deadzone']
        
        # L2 is 1.0 when IDLE, 0.0 when PRESSED
        l2_pressed = l2_raw > (1.0 - trigger_deadzone)
        r2_pressed = r2_raw > trigger_deadzone
        
        # Only send events when state changes (prevents spamming)
        if l2_pressed != self.trigger_states['L2']:
            self.trigger_states['L2'] = l2_pressed
            self.set_key_state('q', l2_pressed)
        
        if r2_pressed != self.trigger_states['R2']:
            self.trigger_states['R2'] = r2_pressed
            self.set_key_state('MOUSE_LEFT', r2_pressed)

    def handle_buttons(self):
        """Handle all buttons with debouncing - FIXED!"""
        if self.joystick is None:
            return
            
        for btn_id, btn_name in PS3_BUTTONS.items():
            if btn_id >= self.button_count:
                continue
            
            try:
                current_pressed = self.joystick.get_button(btn_id) == 1
                last_pressed = self.last_button_read.get(btn_name, False)
                
                # Only process on state change
                if current_pressed != last_pressed:
                    self.last_button_read[btn_name] = current_pressed
                    
                    # Handle D-pad specially for mouse movement
                    if btn_name.startswith('DPAD_'):
                        direction = btn_name.split('_')[1]
                        self.handle_dpad_click(direction, current_pressed)
                    elif btn_name in BUTTON_MAP:
                        # Normal button mapping
                        self.set_key_state(BUTTON_MAP[btn_name], current_pressed)
            except Exception as e:
                pass

    def handle_dpad_continuous(self):
        """Handle continuous D-pad movement (for hold mode)"""
        click_mode = self.settings.get('dpad_click_mode', False)
        if click_mode:
            return
        
        if not self.settings.get('dpad_precision', True):
            return
        
        step = self.settings.get('dpad_step', 5)
        
        if self.dpad_mouse_state['UP']:
            self.safe_mouse_move(0, -step)
        if self.dpad_mouse_state['DOWN']:
            self.safe_mouse_move(0, step)
        if self.dpad_mouse_state['LEFT']:
            self.safe_mouse_move(-step, 0)
        if self.dpad_mouse_state['RIGHT']:
            self.safe_mouse_move(step, 0)

    def controller_loop(self):
        """Main controller loop - runs in separate thread"""
        if not self.find_controller():
            print("❌ No PS3 controller found!")
            return
        
        print("🎮 PS3 Controller active with D-Pad click precision aiming")
        print("   D-Pad → Click to move mouse incrementally")
        print("   Right Stick → Normal mouse look")
        print("   Left Stick → WASD movement")
        print("   L2 → Zoom | R2 → Shoot")
        
        last_status_update = time.time()
        last_continuous_dpad = time.time()
        
        while self.running:
            pygame.event.pump()
            
            # Handle inputs
            self.handle_triggers()  # FIXED: No spamming!
            self.handle_buttons()
            
            # Handle continuous D-pad movement (hold mode)
            click_mode = self.settings.get('dpad_click_mode', False)
            if not click_mode:
                current_time = time.time()
                if current_time - last_continuous_dpad > 0.02:  # 50Hz for continuous
                    self.handle_dpad_continuous()
                    last_continuous_dpad = current_time
            
            # Left stick - WASD
            if self.joystick is not None:
                lx = self.joystick.get_axis(0)
                ly = self.joystick.get_axis(1)
                
                deadzone = self.settings['axis_deadzone']
                
                self.set_key_state('a', lx < -deadzone)
                self.set_key_state('d', lx > deadzone)
                self.set_key_state('w', ly < -deadzone)
                self.set_key_state('s', ly > deadzone)
                
                # Right stick - Mouse with CIRCULAR DEADZONE (smooth diagonal movement)
                rx = self.joystick.get_axis(2)
                ry = self.joystick.get_axis(3)

                sensitivity = self.settings['mouse_sensitivity']
                invert_y = self.settings['invert_y']
                boost = self.settings['boost']

                # CIRCULAR DEADZONE - smooth diagonal movement
                magnitude = math.sqrt(rx*rx + ry*ry)
                if magnitude > deadzone:
                    # Normalize to keep circular shape
                    norm_rx = rx / magnitude
                    norm_ry = ry / magnitude
                    
                    # Scale from deadzone to 1.0
                    scaled_magnitude = (magnitude - deadzone) / (1 - deadzone)
                    
                    # Apply sensitivity and boost
                    move_x = norm_rx * scaled_magnitude * sensitivity * boost * 200
                    move_y = norm_ry * scaled_magnitude * sensitivity * boost * 200
                    
                    if invert_y:
                        move_y = -move_y
                    
                    # Move mouse if movement is significant
                    if abs(move_x) > 0.5 or abs(move_y) > 0.5:
                        self.safe_mouse_move(int(move_x), int(move_y))
                
                # Send status updates to GUI
                current_time = time.time()
                if current_time - last_status_update > 0.05:  # 20Hz update
                    try:
                        gui_queue.put_nowait({
                            'l2': self.trigger_values['L2'],
                            'r2': self.trigger_values['R2'],
                            'l2_pressed': self.trigger_states['L2'],
                            'r2_pressed': self.trigger_states['R2'],
                            'lx': lx,
                            'ly': ly,
                            'rx': rx,
                            'ry': ry,
                            'dpad': self.dpad_mouse_state.copy(),
                            'dpad_clicks': self.dpad_click_count.copy(),
                            'buttons': {name: self.last_button_read.get(name, False) 
                                       for name in PS3_BUTTONS.values() 
                                       if name in self.last_button_read}
                        })
                    except queue.Full:
                        pass
                    last_status_update = current_time
            
            time.sleep(0.005)  # 200Hz loop

    def start(self):
        """Start the controller in a separate thread"""
        self.running = True
        self.thread = threading.Thread(target=self.controller_loop, daemon=True)
        self.thread.start()

    def stop(self):
        """Stop the controller and clean up"""
        self.running = False
        
        # Release all keyboard keys
        for key in list(self.keys_pressed.keys()):
            if self.keys_pressed.get(key, False):
                try:
                    keyboard.release(key)
                except:
                    pass
        self.keys_pressed.clear()
        
        # Release mouse buttons
        if self.mouse_left_pressed:
            try:
                self.mouse.release(MouseButton.left)
                self.mouse_left_pressed = False
            except:
                pass
        if self.mouse_right_pressed:
            try:
                self.mouse.release(MouseButton.right)
                self.mouse_right_pressed = False
            except:
                pass
        
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)
        
        pygame.quit()

    def update_settings(self, **kwargs):
        """Update controller settings"""
        for key, value in kwargs.items():
            if key in self.settings:
                self.settings[key] = value

# ============================================
# SCROLLABLE GUI TUNER
# ============================================
class PS3TunerGUI:
    def __init__(self, controller):
        self.controller = controller
        self.root = tk.Tk()
        self.root.title("🎮 PS3 Tuner - D-Pad Click Aiming")
        self.root.geometry("480x750")
        self.root.attributes('-topmost', True)
        
        # Status variable
        self.controller_connected = False
        self.status_text = "🔴 Disconnected"
        
        self.create_widgets()
        self.update_values()
        
    def create_widgets(self):
        # Title
        title = tk.Label(self.root, text="PS3 DUALSHOCK 3 TUNER", 
                         font=("Arial", 14, "bold"))
        title.pack(pady=10)
        
        # Subtitle
        subtitle = tk.Label(self.root, text="D-Pad → Click for Precision Mouse Movement", 
                           font=("Arial", 10), fg="blue")
        subtitle.pack(pady=2)
        
        # Status
        self.status_label = tk.Label(self.root, text=self.status_text, 
                                     font=("Arial", 10))
        self.status_label.pack(pady=5)
        
        # ===== SCROLLABLE FRAME =====
        canvas_frame = ttk.Frame(self.root)
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.canvas = tk.Canvas(canvas_frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.scrollable_frame = ttk.Frame(self.canvas)
        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        
        def configure_scroll_region(event):
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        
        def configure_canvas_width(event):
            self.canvas.itemconfig(self.canvas_window, width=event.width)
        
        self.scrollable_frame.bind("<Configure>", configure_scroll_region)
        self.canvas.bind("<Configure>", configure_canvas_width)
        
        def on_mousewheel(event):
            self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        self.canvas.bind_all("<MouseWheel>", on_mousewheel)
        
        # ===== MAIN CONTENT FRAME =====
        main_frame = self.scrollable_frame
        main_frame.configure(padding="10")
        
        # ===== SENSITIVITY =====
        ttk.Label(main_frame, text="Mouse Sensitivity", font=("Arial", 10, "bold")).grid(row=0, column=0, sticky=tk.W, pady=(10,0))
        self.sensitivity_var = tk.DoubleVar(value=self.controller.settings['mouse_sensitivity'])
        sensitivity_slider = ttk.Scale(main_frame, from_=0.02, to=0.5, orient=tk.HORIZONTAL, 
                                       variable=self.sensitivity_var, command=self.on_sensitivity_change)
        sensitivity_slider.grid(row=1, column=0, sticky=tk.EW, pady=(0,5))
        self.sensitivity_label = ttk.Label(main_frame, text=f"{self.controller.settings['mouse_sensitivity']:.3f}")
        self.sensitivity_label.grid(row=1, column=1, padx=(10,0))
        
        # ===== DEADZONE =====
        ttk.Label(main_frame, text="Axis Deadzone", font=("Arial", 10, "bold")).grid(row=2, column=0, sticky=tk.W, pady=(10,0))
        self.deadzone_var = tk.DoubleVar(value=self.controller.settings['axis_deadzone'])
        deadzone_slider = ttk.Scale(main_frame, from_=0.05, to=0.5, orient=tk.HORIZONTAL,
                                    variable=self.deadzone_var, command=self.on_deadzone_change)
        deadzone_slider.grid(row=3, column=0, sticky=tk.EW, pady=(0,5))
        self.deadzone_label = ttk.Label(main_frame, text=f"{self.controller.settings['axis_deadzone']:.2f}")
        self.deadzone_label.grid(row=3, column=1, padx=(10,0))
        
        # ===== TRIGGER DEADZONE =====
        ttk.Label(main_frame, text="Trigger Deadzone", font=("Arial", 10, "bold")).grid(row=4, column=0, sticky=tk.W, pady=(10,0))
        self.trigger_deadzone_var = tk.DoubleVar(value=self.controller.settings['trigger_deadzone'])
        trigger_slider = ttk.Scale(main_frame, from_=0.1, to=0.5, orient=tk.HORIZONTAL,
                                   variable=self.trigger_deadzone_var, command=self.on_trigger_deadzone_change)
        trigger_slider.grid(row=5, column=0, sticky=tk.EW, pady=(0,5))
        self.trigger_deadzone_label = ttk.Label(main_frame, text=f"{self.controller.settings['trigger_deadzone']:.2f}")
        self.trigger_deadzone_label.grid(row=5, column=1, padx=(10,0))
        
        # ===== D-PAD STEP SIZE =====
        ttk.Label(main_frame, text="D-Pad Step Size (pixels)", font=("Arial", 10, "bold")).grid(row=6, column=0, sticky=tk.W, pady=(10,0))
        self.dpad_step_var = tk.IntVar(value=self.controller.settings.get('dpad_step', 5))
        dpad_step_slider = ttk.Scale(main_frame, from_=1, to=30, orient=tk.HORIZONTAL,
                                      variable=self.dpad_step_var, command=self.on_dpad_step_change)
        dpad_step_slider.grid(row=7, column=0, sticky=tk.EW, pady=(0,5))
        self.dpad_step_label = ttk.Label(main_frame, text=str(self.controller.settings.get('dpad_step', 5)) + "px")
        self.dpad_step_label.grid(row=7, column=1, padx=(10,0))
        
        # ===== D-PAD CLICK MODE =====
        ttk.Label(main_frame, text="D-Pad Mode", font=("Arial", 10, "bold")).grid(row=8, column=0, sticky=tk.W, pady=(10,0))
        self.dpad_click_mode_var = tk.BooleanVar(value=self.controller.settings.get('dpad_click_mode', False))
        click_mode_frame = ttk.Frame(main_frame)
        click_mode_frame.grid(row=9, column=0, columnspan=2, sticky=tk.W, pady=(0,5))
        

        hold_radio = ttk.Radiobutton(click_mode_frame, text="Hold Mode (continuous while held)", 
                                      variable=self.dpad_click_mode_var, value=False,
                                      command=self.on_dpad_click_mode_change)
        hold_radio.pack(anchor=tk.W)


        click_radio = ttk.Radiobutton(click_mode_frame, text="Click Mode (1 click = 1 step)", 
                                       variable=self.dpad_click_mode_var, value=True,
                                       command=self.on_dpad_click_mode_change)
        click_radio.pack(anchor=tk.W)
        

        # ===== D-PAD PRECISION TOGGLE =====
        ttk.Label(main_frame, text="Enable D-Pad Aiming", font=("Arial", 10, "bold")).grid(row=10, column=0, sticky=tk.W, pady=(10,0))
        self.dpad_precision_var = tk.BooleanVar(value=self.controller.settings.get('dpad_precision', True))
        dpad_check = ttk.Checkbutton(main_frame, variable=self.dpad_precision_var, command=self.on_dpad_precision_change)
        dpad_check.grid(row=11, column=0, sticky=tk.W, pady=(0,5))
        
        # ===== INVERT Y =====
        ttk.Label(main_frame, text="Invert Y", font=("Arial", 10, "bold")).grid(row=12, column=0, sticky=tk.W, pady=(10,0))
        self.invert_var = tk.BooleanVar(value=self.controller.settings['invert_y'])
        invert_check = ttk.Checkbutton(main_frame, variable=self.invert_var, command=self.on_invert_change)
        invert_check.grid(row=13, column=0, sticky=tk.W, pady=(0,5))
        
        # ===== BOOST =====
        ttk.Label(main_frame, text="Boost", font=("Arial", 10, "bold")).grid(row=14, column=0, sticky=tk.W, pady=(10,0))
        self.boost_var = tk.DoubleVar(value=self.controller.settings['boost'])
        boost_slider = ttk.Scale(main_frame, from_=0.5, to=3.0, orient=tk.HORIZONTAL,
                                 variable=self.boost_var, command=self.on_boost_change)
        boost_slider.grid(row=15, column=0, sticky=tk.EW, pady=(0,5))
        self.boost_label = ttk.Label(main_frame, text=f"{self.controller.settings['boost']:.1f}x")
        self.boost_label.grid(row=15, column=1, padx=(10,0))
        
        # ===== LIVE VALUES =====
        self.value_frame = ttk.LabelFrame(main_frame, text="Live Values", padding="5")
        self.value_frame.grid(row=16, column=0, columnspan=2, sticky=tk.EW, pady=(10,0))
        
        self.l2_label = ttk.Label(self.value_frame, text="L2: 0.000 [IDLE]")
        self.l2_label.grid(row=0, column=0, sticky=tk.W)
        
        self.r2_label = ttk.Label(self.value_frame, text="R2: 0.000 [IDLE]")
        self.r2_label.grid(row=1, column=0, sticky=tk.W)
        
        self.stick_label = ttk.Label(self.value_frame, text="LS: (0.00, 0.00)  RS: (0.00, 0.00)")
        self.stick_label.grid(row=2, column=0, sticky=tk.W)
        
        self.dpad_label = ttk.Label(self.value_frame, text="D-Pad: None")
        self.dpad_label.grid(row=3, column=0, sticky=tk.W)
        
        self.dpad_clicks_label = ttk.Label(self.value_frame, text="Clicks: ↑0 ↓0 ←0 →0")
        self.dpad_clicks_label.grid(row=4, column=0, sticky=tk.W)
        
        self.button_label = ttk.Label(self.value_frame, text="Buttons: None")
        self.button_label.grid(row=5, column=0, sticky=tk.W)
        
        # ===== PRESETS =====
        ttk.Label(main_frame, text="Presets", font=("Arial", 10, "bold")).grid(row=17, column=0, sticky=tk.W, pady=(10,0))
        preset_frame = ttk.Frame(main_frame)
        preset_frame.grid(row=18, column=0, columnspan=2, sticky=tk.EW, pady=(0,5))
        
        ttk.Button(preset_frame, text="Sniper", command=self.preset_sniper).pack(side=tk.LEFT, padx=2)
        ttk.Button(preset_frame, text="Balanced", command=self.preset_balanced).pack(side=tk.LEFT, padx=2)
        ttk.Button(preset_frame, text="Action", command=self.preset_action).pack(side=tk.LEFT, padx=2)
        ttk.Button(preset_frame, text="Precision", command=self.preset_precision).pack(side=tk.LEFT, padx=2)
        
        # ===== BUTTON MAPPINGS =====
        ttk.Label(main_frame, text="Button Mappings", font=("Arial", 10, "bold")).grid(row=19, column=0, sticky=tk.W, pady=(10,0))
        mapping_frame = ttk.Frame(main_frame)
        mapping_frame.grid(row=20, column=0, columnspan=2, sticky=tk.EW, pady=(0,5))
        
        mapping_text = "D-Pad=Precision Aim | L2=Q | R2=Shoot | L1=Aim | Cross=V | Circle=R | Square=E"
        ttk.Label(mapping_frame, text=mapping_text, font=("Arial", 8)).pack()
        
        # ===== CONTROL BUTTONS =====
        control_frame = ttk.Frame(main_frame)
        control_frame.grid(row=21, column=0, columnspan=2, pady=10)
        
        self.start_btn = ttk.Button(control_frame, text="▶ Start Controller", command=self.start_controller)
        self.start_btn.pack(side=tk.LEFT, padx=5)
        
        self.stop_btn = ttk.Button(control_frame, text="⏹ Stop Controller", command=self.stop_controller, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(control_frame, text="🔄 Connect", command=self.check_controller).pack(side=tk.LEFT, padx=5)
        
        main_frame.columnconfigure(0, weight=1)
        
        # Check controller status
        self.root.after(500, self.check_controller)
    
    # ===== Callbacks =====
    def on_sensitivity_change(self, val):
        self.controller.update_settings(mouse_sensitivity=self.sensitivity_var.get())
        self.sensitivity_label.config(text=f"{self.controller.settings['mouse_sensitivity']:.3f}")
    
    def on_deadzone_change(self, val):
        self.controller.update_settings(axis_deadzone=self.deadzone_var.get())
        self.deadzone_label.config(text=f"{self.controller.settings['axis_deadzone']:.2f}")
    
    def on_trigger_deadzone_change(self, val):
        self.controller.update_settings(trigger_deadzone=self.trigger_deadzone_var.get())
        self.trigger_deadzone_label.config(text=f"{self.controller.settings['trigger_deadzone']:.2f}")
    
    def on_dpad_step_change(self, val):
        self.controller.update_settings(dpad_step=self.dpad_step_var.get())
        self.dpad_step_label.config(text=str(self.controller.settings['dpad_step']) + "px")
    
    def on_dpad_precision_change(self):
        self.controller.update_settings(dpad_precision=self.dpad_precision_var.get())
    
    def on_dpad_click_mode_change(self):
        self.controller.update_settings(dpad_click_mode=self.dpad_click_mode_var.get())
        mode = "Click" if self.dpad_click_mode_var.get() else "Hold"
        print(f"🔄 D-Pad mode changed to: {mode}")
    
    def on_invert_change(self):
        self.controller.update_settings(invert_y=self.invert_var.get())
    
    def on_boost_change(self, val):
        self.controller.update_settings(boost=self.boost_var.get())
        self.boost_label.config(text=f"{self.controller.settings['boost']:.1f}x")
    
    # ===== Presets =====
    def apply_preset(self, sensitivity, deadzone, trigger_deadzone, boost, dpad_step=5, click_mode=True, invert=False):
        self.sensitivity_var.set(sensitivity)
        self.deadzone_var.set(deadzone)
        self.trigger_deadzone_var.set(trigger_deadzone)
        self.boost_var.set(boost)
        self.dpad_step_var.set(dpad_step)
        self.dpad_click_mode_var.set(click_mode)
        self.invert_var.set(invert)
        
        self.controller.update_settings(
            mouse_sensitivity=sensitivity,
            axis_deadzone=deadzone,
            trigger_deadzone=trigger_deadzone,
            boost=boost,
            dpad_step=dpad_step,
            dpad_click_mode=click_mode,
            invert_y=invert
        )
        
        self.sensitivity_label.config(text=f"{sensitivity:.3f}")
        self.deadzone_label.config(text=f"{deadzone:.2f}")
        self.trigger_deadzone_label.config(text=f"{trigger_deadzone:.2f}")
        self.boost_label.config(text=f"{boost:.1f}x")
        self.dpad_step_label.config(text=str(dpad_step) + "px")
    
    def preset_sniper(self):
        self.apply_preset(0.06, 0.35, 0.40, 1.0, 2, True)
    
    def preset_balanced(self):
        self.apply_preset(0.18, 0.30, 0.35, 1.5, 5, True)
    
    def preset_action(self):
        self.apply_preset(0.25, 0.25, 0.30, 2.0, 8, False)
    
    def preset_turbo(self):
        self.apply_preset(0.35, 0.20, 0.25, 2.5, 12, False)
    
    def preset_precision(self):
        """Ultra precision preset - tiny D-pad steps"""
        self.apply_preset(0.04, 0.40, 0.45, 1.0, 1, True)
    
    # ===== Controller Management =====
    def check_controller(self):
        """Check if controller is connected"""
        try:
            # Re-initialize pygame joystick if needed
            if self.controller.joystick is None:
                pygame.joystick.quit()
                pygame.joystick.init()
                self.controller.find_controller()
            elif self.controller.joystick is not None:
                # Check if joystick still valid
                try:
                    self.controller.joystick.get_name()
                except:
                    pygame.joystick.quit()
                    pygame.joystick.init()
                    self.controller.find_controller()
        except:
            pygame.joystick.quit()
            pygame.joystick.init()
            self.controller.find_controller()
        
        if self.controller.joystick is not None:
            self.controller_connected = True
            self.status_text = f"✅ Connected: {self.controller.joystick.get_name()}"
            self.status_label.config(text=self.status_text, fg="green")
        else:
            self.controller_connected = False
            self.status_text = "🔴 No controller found"
            self.status_label.config(text=self.status_text, fg="red")
        
        if not self.controller_connected:
            self.root.after(2000, self.check_controller)
    
    def start_controller(self):
        if not self.controller_connected:
            self.check_controller()
            if not self.controller_connected:
                return
        
        self.controller.start()
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.status_text = "🟢 Controller Running"
        self.status_label.config(text=self.status_text, fg="green")
    
    def stop_controller(self):
        self.controller.stop()
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.status_text = "⏸ Controller Stopped"
        self.status_label.config(text=self.status_text, fg="orange")
    
    def update_values(self):
        """Update live values from queue"""
        try:
            while not gui_queue.empty():
                data = gui_queue.get_nowait()
                
                l2_val = data.get('l2', 0)
                r2_val = data.get('r2', 0)
                l2_pressed = data.get('l2_pressed', False)
                r2_pressed = data.get('r2_pressed', False)
                
                l2_status = "🔴 PRESSED" if l2_pressed else "⚪ IDLE"
                r2_status = "🔴 PRESSED" if r2_pressed else "⚪ IDLE"
                
                self.l2_label.config(text=f"L2: {l2_val:+.3f} [{l2_status}]")
                self.r2_label.config(text=f"R2: {r2_val:+.3f} [{r2_status}]")
                
                lx = data.get('lx', 0)
                ly = data.get('ly', 0)
                rx = data.get('rx', 0)
                ry = data.get('ry', 0)
                self.stick_label.config(text=f"LS: ({lx:+.2f}, {ly:+.2f})  RS: ({rx:+.2f}, {ry:+.2f})")
                
                dpad = data.get('dpad', {})
                dpad_active = [d for d, pressed in dpad.items() if pressed]
                if dpad_active:
                    self.dpad_label.config(text=f"D-Pad: {', '.join(dpad_active)}")
                else:
                    self.dpad_label.config(text="D-Pad: None")
                
                clicks = data.get('dpad_clicks', {'UP': 0, 'DOWN': 0, 'LEFT': 0, 'RIGHT': 0})
                self.dpad_clicks_label.config(
                    text=f"Clicks: ↑{clicks.get('UP', 0)} ↓{clicks.get('DOWN', 0)} ←{clicks.get('LEFT', 0)} →{clicks.get('RIGHT', 0)}"
                )
                
                buttons = data.get('buttons', {})
                pressed_buttons = [name for name, pressed in buttons.items() if pressed and not name.startswith('DPAD_')]
                if pressed_buttons:
                    self.button_label.config(text=f"Buttons: {', '.join(pressed_buttons)}")
                else:
                    self.button_label.config(text="Buttons: None")
        except:
            pass
        
        self.root.after(50, self.update_values)
    
    def run(self):
        """Start the GUI main loop"""
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.mainloop()
    
    def on_closing(self):
        """Handle window close"""
        self.stop_controller()
        self.root.destroy()

# ============================================
# MAIN
# ============================================
if __name__ == "__main__":
    print("🎮 PS3 DualShock 3 - D-Pad Click Precision Aiming")
    print("=" * 60)
    print("  D-Pad → Click for pixel-perfect mouse movement")
    print("  Right Stick → Normal mouse look")
    print("  Left Stick → WASD movement")
    print("  L2 → Zoom | R2 → Shoot")
    print("=" * 60)
    print("Starting GUI...")
    print("💡 Use mouse wheel to scroll up/down")
    
    controller = PS3Controller()
    gui = PS3TunerGUI(controller)
    gui.run()