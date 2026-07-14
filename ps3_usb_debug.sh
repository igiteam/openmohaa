#!/bin/bash

echo "=========================================="
echo "  PS3 CONTROLLER - DEBUG & SETUP"
echo "=========================================="
echo ""

# PS3 DualShock 3 uses standard USB HID and Bluetooth
# It works natively on macOS with some setup

echo "⚠️ PS3 DualShock 3 Controller Support:"
echo "  ✅ USB: Works natively on macOS"
echo "  ⚠️  Bluetooth: Requires pairing with Mac"
echo ""

# 1. Check USB connections
echo "1. CHECKING USB CONNECTIONS"
echo "──────────────────────────────────────────"
echo "Checking for PS3 controller..."
system_profiler SPUSBDataType | grep -A 20 -i "PLAYSTATION\|DualShock\|PS3\|Sony" || echo "   No PS3 controller found in USB"
echo ""

# 2. Check Bluetooth devices
echo "2. BLUETOOTH DEVICES"
echo "──────────────────────────────────────────"
echo "Scanning for PS3 controller in Bluetooth..."
sudo system_profiler SPBluetoothDataType | grep -E "PLAYSTATION|DualShock|Sixaxis|Name:|Connected:|Address:" | head -20
echo ""

# 3. Check if controller is detected by system
echo "3. CONTROLLER DETECTION STATUS"
echo "──────────────────────────────────────────"
if system_profiler SPUSBDataType | grep -qi "PLAYSTATION\|DualShock"; then
    echo "✅ PS3 controller detected via USB!"
    echo ""
    echo "Device info:"
    system_profiler SPUSBDataType | grep -A 30 -i "PLAYSTATION\|DualShock" | head -30
else
    echo "❌ No PS3 controller detected"
    echo ""
    echo "Try:"
    echo "  1. Connect PS3 controller via USB cable"
    echo "  2. Press the PS button"
    echo "  3. Try a different USB port"
fi
echo ""

# 4. Check Game Controller framework
echo "4. GAME CONTROLLER FRAMEWORK"
echo "──────────────────────────────────────────"
echo "Checking if PS3 controller is recognized as gamepad..."
if system_profiler SPUSBDataType | grep -qi "PLAYSTATION\|DualShock"; then
    echo "✅ Controller should appear in:"
    echo "   System Preferences > Game Controllers"
    echo ""
    echo "   Also check:"
    echo "   /System/Library/Frameworks/GameController.framework"
else
    echo "⚠️  Controller not recognized by GameController framework"
fi
echo ""

# 5. Python/Pygame detection
echo "5. PYTHON/PYGAME SETUP"
echo "──────────────────────────────────────────"
if command -v python3 &> /dev/null; then
    echo "✅ Python3 found"
    
    # Check if pygame is installed
    if python3 -c "import pygame" 2>/dev/null; then
        echo "✅ Pygame installed"
        echo ""
        echo "  Test with: python3 -c 'import pygame; pygame.init(); pygame.joystick.init(); print(f\"Joysticks: {pygame.joystick.get_count()}\")'"
    else
        echo "❌ Pygame NOT installed"
        echo "  Install: pip3 install pygame"
    fi
else
    echo "❌ Python3 not found"
fi
echo ""

# 6. System logs
echo "6. SYSTEM LOGS (USB events)"
echo "──────────────────────────────────────────"
echo "Recent USB events (last 2 minutes):"
log show --predicate 'subsystem == "com.apple.usb"' --last 2m | grep -i "attach\|detach" | tail -10 || echo "   No recent USB events"
echo ""

echo "=========================================="
echo "  HOW TO CONNECT PS3 CONTROLLER"
echo "=========================================="
echo ""

echo "METHOD 1: USB (Recommended for gaming):"
echo "  1. Plug the PS3 controller into USB port"
echo "  2. Press the PS button"
echo "  3. It should work immediately with our Python script"
echo ""

echo "METHOD 2: Bluetooth (Wireless):"
echo "  1. Go to System Preferences > Bluetooth"
echo "  2. Make sure Bluetooth is ON"
echo "  3. Connect controller via USB (needed for first pairing)"
echo "  4. Disconnect USB"
echo "  5. Press PS button"
echo "  6. If it doesn't connect, pair manually:"
echo "     a. Press and hold PS + SHARE buttons until LED flashes"
echo "     b. Click 'Pair' in Bluetooth preferences"
echo ""

echo "METHOD 3: SixaxisPairTool (For Bluetooth issues):"
echo "  If Bluetooth pairing fails:"
echo "  1. Download SixaxisPairTool for Mac"
echo "  2. Connect PS3 controller via USB"
echo "  3. Change Bluetooth address to match your Mac"
echo "  4. Then connect wirelessly"
echo ""

echo "=========================================="
echo "  TESTING THE CONTROLLER"
echo "=========================================="
echo ""

# Check if pygame is installed to test
if python3 -c "import pygame" 2>/dev/null; then
    echo "Running quick controller test..."
    
    # Create a temporary Python test file
    cat > /tmp/test_ps3_controller.py << 'EOF'
import pygame
import time
import sys
import os

# Suppress pygame welcome message
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'

try:
    pygame.init()
    pygame.joystick.init()
    
    count = pygame.joystick.get_count()
    print(f'Joysticks found: {count}')
    
    if count == 0:
        print('❌ No joystick found')
        print('Try:')
        print('  1. Press the PS button on the controller')
        print('  2. Unplug and replug the USB cable')
        print('  3. Try a different USB port')
        sys.exit(0)
    
    # Try to initialize the first joystick
    try:
        joy = pygame.joystick.Joystick(0)
        joy.init()
        print(f'Controller: {joy.get_name()}')
        print(f'  Axes: {joy.get_numaxes()}')
        print(f'  Buttons: {joy.get_numbuttons()}')
        print(f'  Hats: {joy.get_numhats()}')
        print()
        print('Testing for 5 seconds - move sticks and press buttons...')
        
        start = time.time()
        had_input = False
        
        while time.time() - start < 5:
            pygame.event.pump()
            
            # Read axes
            axes = []
            for i in range(joy.get_numaxes()):
                val = joy.get_axis(i)
                if abs(val) > 0.1:  # Only show meaningful movement
                    axes.append(f'{i}:{val:.2f}')
            
            # Read buttons
            buttons = []
            for i in range(min(joy.get_numbuttons(), 16)):
                if joy.get_button(i):
                    buttons.append(str(i))
                    had_input = True
            
            # Read hats
            hats = []
            for i in range(joy.get_numhats()):
                hat = joy.get_hat(i)
                if hat != (0, 0):
                    hats.append(f'H{i}:{hat}')
                    had_input = True
            
            # Build status message
            status_parts = []
            if axes:
                status_parts.append('Axes: ' + ' '.join(axes[:4]))
            if buttons:
                status_parts.append('Buttons: ' + ' '.join(buttons[:4]))
            if hats:
                status_parts.append('Hats: ' + ' '.join(hats))
            
            if status_parts:
                print('\r' + ' | '.join(status_parts), end='')
            elif had_input:
                print('\rWaiting for input... (move sticks or press buttons)', end='')
            
            time.sleep(0.05)
        
        print('\n\n✅ Test complete!')
        if had_input:
            print('✅ Controller input detected! Your PS3 controller is working!')
        else:
            print('⚠️  No controller input detected.')
            print('Try pressing buttons or moving the sticks during the test.')
            print('Also make sure the PS button is pressed to activate the controller.')
        
    except Exception as e:
        print(f'⚠️  Error initializing controller: {e}')
        print('This is common with PS3 controllers on macOS.')
        print('Try these solutions:')
        print('  1. Install SixaxisPairTool')
        print('  2. Use the controller in Bluetooth mode instead')
        print('  3. Try a different USB cable')
        
except Exception as e:
    print(f'⚠️  Error: {e}')
    print('Pygame may have issues with PS3 controllers on this macOS version.')
EOF

    # Run the test script
    python3 /tmp/test_ps3_controller.py
    
    # Clean up
    rm -f /tmp/test_ps3_controller.py
    
else
    echo "Pygame not installed - can't test"
    echo "Install with: pip3 install pygame"
fi

echo ""
echo "=========================================="
echo "  TROUBLESHOOTING"
echo "=========================================="
echo ""

echo "If controller is not detected:"
echo "  1. Unplug/replug the USB cable"
echo "  2. Try a different USB port"
echo "  3. Press the PS button"
echo "  4. Restart your Mac"
echo "  5. Check System Information > USB"
echo ""

echo "If controller is detected but not working in game:"
echo "  1. Make sure you have Accessibility permission:"
echo "     System Preferences > Security & Privacy > Accessibility"
echo "     Add Terminal and your game"
echo "  2. Run our Python script:"
echo "     python3 ps3_controller.py"
echo "  3. Test with joypad.ai or Game Controller tester"
echo ""

echo "If Bluetooth pairing fails:"
echo "  1. Make sure no other device is connected"
echo "  2. Reset the controller: press the reset button (small hole on back)"
echo "  3. Try SixaxisPairTool"
echo "  4. Use USB instead (it's more reliable)"
echo ""

echo "=========================================="
echo "  ALTERNATIVE: Using GameController Framework"
echo "=========================================="
echo ""

echo "Since Pygame segfaults with PS3 controllers, try using the native GameController framework:"
echo ""
echo "Option 1: Use the built-in macOS Game Controller tester"
echo "  Open /System/Library/CoreServices/GameControllerTester.app"
echo ""
echo "Option 2: Create a simple Python script using PyObjC:"
echo "  pip3 install pyobjc-framework-GameController"
echo "  Then use the GameController framework directly"
echo ""
echo "Option 3: Use a different controller library:"
echo "  pip3 install inputs (for Linux/Windows style input)"
echo "  pip3 install evdev (for event device access)"
echo ""

echo "=========================================="
echo "  RECOMMENDED SETUP"
echo "=========================================="
echo ""

echo "For Operation Flashpoint, this setup works best:"
echo "  ✅ USB connection (reliable, no lag)"
echo "  ✅ Python with Pygame (works with our script)"
echo "  ✅ Accessibility permissions granted"
echo ""
echo "Run: python3 ps3_controller.py"
echo ""

# Ask if they want to install pygame
echo "Do you want to install pygame now? (y/n)"
read -r answer
if [[ $answer == "y" || $answer == "Y" ]]; then
    echo "Installing pygame..."
    pip3 install pygame
    echo "✅ Pygame installed!"
fi

echo ""
echo "=========================================="
echo "  DONE!"
echo "=========================================="