//
// Copyright (c) 2021 vit9696.  All Rights Reserved.
// SPDX-License-Identifier: BSD-3-Clause
//
#include <IOKit/hid/IOHIDLib.h>
#include <CoreFoundation/CoreFoundation.h>
#include <stdio.h>//
// Xbox 360 Controller Activator for macOS
// Based on the DualShock 3 code structure
//
#include <IOKit/hid/IOHIDLib.h>
#include <CoreFoundation/CoreFoundation.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

static void activate_xbox360(void *device) {
  IOReturn r = IOHIDDeviceOpen(device, kIOHIDOptionsTypeNone);
  if (r != kIOReturnSuccess) {
    printf("  Failed to open device - %d\n", r);
    return;
  }
  
  // Xbox 360 initialization sequence
  // Different controllers may need different commands
  
  // Method 1: Standard Xbox 360 init
  uint8_t initBlob1[] = { 0x00, 0x00, 0x00, 0x00 };
  IOHIDDeviceSetReport(device, kIOHIDReportTypeFeature, 0x00, initBlob1, sizeof(initBlob1));
  printf("  Sending init command 1...\n");
  usleep(100000);
  
  // Method 2: Alternative init for some controllers
  uint8_t initBlob2[] = { 0x01, 0x00, 0x00, 0x00 };
  IOHIDDeviceSetReport(device, kIOHIDReportTypeFeature, 0x01, initBlob2, sizeof(initBlob2));
  printf("  Sending init command 2...\n");
  usleep(100000);
  
  // Method 3: Wireless receiver init
  uint8_t initBlob3[] = { 0x13, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00 };
  IOHIDDeviceSetReport(device, kIOHIDReportTypeFeature, 0xF0, initBlob3, sizeof(initBlob3));
  printf("  Sending init command 3 (wireless)...\n");
  usleep(100000);
  
  // Method 4: Try LED control
  uint8_t ledBlob[] = { 0x01, 0x00, 0x00, 0x00, 0x00, 0x00 };
  IOHIDDeviceSetReport(device, kIOHIDReportTypeOutput, 0x00, ledBlob, sizeof(ledBlob));
  printf("  Sending LED command...\n");
  usleep(100000);

  // Try to read a report to verify it's working
  uint8_t report[32] = {0};
  CFIndex reportSize = 32;
  r = IOHIDDeviceGetReport(device, kIOHIDReportTypeFeature, 0x00, report, &reportSize);
  if (r == kIOReturnSuccess && reportSize >= 20) {
    printf("  Got response: ");
    for (int i = 0; i < reportSize && i < 20; i++) {
      printf("%02x ", report[i]);
    }
    printf("\n");
  } else {
    printf("  Could not read initial report\n");
  }
  
  IOHIDDeviceClose(device, kIOHIDOptionsTypeNone);
  printf("  Device activated!\n");
}

int main() {
  // Xbox 360 Vendor/Product IDs
  // Try multiple IDs since Xbox 360 controllers have different variants
  
  // First try the most common ones
  static const SInt32 VendorId1 = 0x045e;
  static const SInt32 ProductId1 = 0x028f;  // Xbox 360 Wired
  
  static const SInt32 VendorId2 = 0x045e;
  static const SInt32 ProductId2 = 0x028e;  // Xbox 360 Wireless Receiver
  
  static const SInt32 VendorId3 = 0x045e;
  static const SInt32 ProductId3 = 0x02a1;  // Xbox 360 Wireless (newer)
  
  static const SInt32 VendorId4 = 0x045e;
  static const SInt32 ProductId4 = 0x02d1;  // Xbox 360 Wireless with Chatpad
  
  // Also try some common clone controllers
  static const SInt32 VendorId5 = 0x0e6f;
  static const SInt32 ProductId5 = 0x0201;  // Mad Catz Wired
  
  static const SInt32 VendorId6 = 0x0e6f;
  static const SInt32 ProductId6 = 0x0202;  // Mad Catz Wireless
  
  static const SInt32 VendorId7 = 0x1bad;
  static const SInt32 ProductId7 = 0xf010;  // F710
  
  static const SInt32 VendorId8 = 0x1bad;
  static const SInt32 ProductId8 = 0xf016;  // F310
  
  // Try each device ID one at a time
  struct { SInt32 vendor; SInt32 product; const char* name; } ids[] = {
    {VendorId1, ProductId1, "Xbox 360 Wired"},
    {VendorId2, ProductId2, "Xbox 360 Wireless Receiver"},
    {VendorId3, ProductId3, "Xbox 360 Wireless (newer)"},
    {VendorId4, ProductId4, "Xbox 360 Wireless with Chatpad"},
    {VendorId5, ProductId5, "Mad Catz Wired"},
    {VendorId6, ProductId6, "Mad Catz Wireless"},
    {VendorId7, ProductId7, "Logitech F710"},
    {VendorId8, ProductId8, "Logitech F310"},
  };
  
  for (int i = 0; i < sizeof(ids)/sizeof(ids[0]); i++) {
    SInt32 VendorId = ids[i].vendor;
    SInt32 ProductId = ids[i].product;
    
    CFNumberRef vendorIdNum = CFNumberCreate(kCFAllocatorDefault, kCFNumberSInt32Type, &VendorId);
    CFNumberRef productIdNum = CFNumberCreate(kCFAllocatorDefault, kCFNumberSInt32Type, &ProductId);
    
    const void *keys[2] = {
      CFSTR(kIOHIDVendorIDKey),
      CFSTR(kIOHIDProductIDKey),
    };

    const void *values[2] = {
      vendorIdNum,
      productIdNum
    };

    IOHIDManagerRef manager = IOHIDManagerCreate(kCFAllocatorDefault, kIOHIDOptionsTypeNone);  
    CFDictionaryRef matching = CFDictionaryCreate(NULL, keys, values, 2, NULL, NULL);
    IOHIDManagerSetDeviceMatching(manager, matching);

    CFSetRef deviceSet = IOHIDManagerCopyDevices(manager);
    if (deviceSet != NULL) {
      CFIndex count = CFSetGetCount(deviceSet);
      if (count > 0) {
        printf("Found %ld Xbox 360 controller(s) (%s)\n", count, ids[i].name);
        void **gamepads = calloc(count, sizeof(void *));
        CFSetGetValues(deviceSet, (const void **)gamepads);
        for (CFIndex j = 0; j < count; j++) {
          printf("Handling device %ld:\n", j);
          activate_xbox360(gamepads[j]);
        }
        free(gamepads);
        CFRelease(deviceSet);
        CFRelease(productIdNum);
        CFRelease(vendorIdNum);
        CFRelease(matching);
        CFRelease(manager);
        return 0; // Stop after finding one
      }
      CFRelease(deviceSet);
    }
    CFRelease(productIdNum);
    CFRelease(vendorIdNum);
    CFRelease(matching);
    CFRelease(manager);
  }
  
  printf("No Xbox 360 controllers found!\n");
  printf("\nTroubleshooting:\n");
  printf("  1. Check USB connection\n");
  printf("  2. For wireless, press the sync button\n");
  printf("  3. Try: sudo killall usbd\n");
  printf("  4. Try a different USB port\n");
  return 0;
}
#include <stdlib.h>

static void activate_gamepad(void *device) {
  IOReturn r = IOHIDDeviceOpen(device, kIOHIDOptionsTypeNone);
  if (r != kIOReturnSuccess) {
    printf("  Failed to open device - %d\n", r);
    return;
  }
  uint8_t controlBlob[] = { 0x42, 0x0C, 0x00, 0x00};
  IOHIDDeviceSetReport(device, kIOHIDReportTypeFeature, 0xF4, controlBlob, sizeof(controlBlob));

  printf("  Activating device...\n");
  sleep(1);

  uint8_t rumbleBlob[] = {
    0x01,
    0x00,
    0x00,
    0x00,
    0x00,
    0x00, // rumble values [0x00, right-timeout, right-force, left-timeout, left-force]
    0x00,
    0x00, // Gyro
    0x00,
    0x00,
    0x00, // 0x02=LED1 .. 0x10=LED4
    /*
     * the total time the led is active (0xff means forever)
     * |     duty_length: how long a cycle is in deciseconds:
     * |     |                              (0 means "blink very fast")
     * |     |     ??? (Maybe a phase shift or duty_length multiplier?)
     * |     |     |     % of duty_length led is off (0xff means 100%)
     * |     |     |     |     % of duty_length led is on (0xff is 100%)
     * |     |     |     |     |
     * 0xff, 0x27, 0x10, 0x00, 0x32,
     */
    0xff,
    0x27,
    0x10,
    0x00,
    0x32, // LED 4
    0xff,
    0x27,
    0x10,
    0x00,
    0x32, // LED 3
    0xff,
    0x27,
    0x10,
    0x00,
    0x32, // LED 2
    0xff,
    0x27,
    0x10,
    0x00,
    0x32, // LED 1
    0x00,
    0x00,
    0x00,
    0x00,
    0x00,
    // Necessary for Fake DS3
    0x00,
    0x00,
    0x00,
    0x00,
    0x00,
    0x00,
    0x00,
    0x00,
    0x00,
    0x00,
    0x00,
    0x00,
    0x00,
  };
  static const size_t RumbleLengthL = 4;
  static const size_t RumblePowerL = 5;
  static const size_t RumbleLengthR = 2;
  static const size_t RumblePowerR = 3;
  rumbleBlob[RumbleLengthL] = rumbleBlob[RumbleLengthR] = 80;
  rumbleBlob[RumblePowerL]                              = 255;
  rumbleBlob[RumblePowerR]                              = 1;
  IOHIDDeviceSetReport(device, kIOHIDReportTypeOutput, 1, rumbleBlob, sizeof(rumbleBlob));
  IOHIDDeviceClose(device, kIOHIDOptionsTypeNone);
  printf("  Should be rumbling!\n");
}

int main() {
  static const SInt32 VendorId = 0x054C;
  static const SInt32 ProductId = 0x0268;

  CFNumberRef vendorIdNum = CFNumberCreate(kCFAllocatorDefault, kCFNumberSInt32Type, &VendorId);
  CFNumberRef productIdNum = CFNumberCreate(kCFAllocatorDefault, kCFNumberSInt32Type, &ProductId);
  
  const void *keys[2] = {
    CFSTR(kIOHIDVendorIDKey),
    CFSTR(kIOHIDProductIDKey),
  };

  const void *values[2] = {
    vendorIdNum,
    productIdNum
  };

  IOHIDManagerRef manager = IOHIDManagerCreate(kCFAllocatorDefault, kIOHIDOptionsTypeNone);  
  CFDictionaryRef matching = CFDictionaryCreate(NULL, keys, values, 2, NULL, NULL);
  IOHIDManagerSetDeviceMatching(manager, matching);

  CFSetRef deviceSet = IOHIDManagerCopyDevices(manager);
  if (deviceSet != NULL) {
    CFIndex count = CFSetGetCount(deviceSet);
    if (count > 0) {
      printf("Discovered %ld DualShock 3 gamepads\n", count);
      void **gamepads = calloc(count, sizeof(void *));
      CFSetGetValues(deviceSet, (const void **)gamepads);
      for (CFIndex i = 0; i < count; i++) {
        printf("Handling device %ld:\n", i);
        activate_gamepad(gamepads[i]);
      }
      free(gamepads);
    } else {
      printf("No DualShock 3 gamepads found!\n");
    }
    CFRelease(deviceSet);
  }
  CFRelease(productIdNum);
  CFRelease(vendorIdNum);
  CFRelease(matching);
  CFRelease(manager);
}
