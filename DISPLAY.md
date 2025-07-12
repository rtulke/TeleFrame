# 🖥️ TeleFrame Display Configuration

## Overview

TeleFrame now supports configurable display resolution instead of hardcoded values. The system automatically detects your display and optimizes performance based on resolution.

## Features

- **Auto-detection** - Automatically detects display resolution
- **Presets** - Common resolution presets (FHD, HD, 4K, Pi Touch, etc.)
- **Custom resolutions** - Support for any resolution
- **Performance optimization** - Automatic FPS and fade time adjustment
- **Hardware detection** - Raspberry Pi specific optimizations
- **Multiple formats** - String format, separate width/height, presets

## Configuration

### Basic Configuration

```toml
[display]
resolution = "auto"  # Auto-detect system resolution
```

### Resolution Presets

```toml
[display]
resolution = "fhd"        # Full HD 1920x1080
resolution = "hd"         # HD 1280x720
resolution = "pi_touch"   # Pi Touch Display 800x480
resolution = "xga"        # XGA 1024x768
resolution = "svga"       # SVGA 800x600
resolution = "4k"         # 4K UHD 3840x2160
```

### Custom Resolutions

```toml
[display]
resolution = "1366x768"   # Custom laptop resolution
resolution = "1440x900"   # Custom widescreen
resolution = "2560x1440"  # QHD
```

### Separate Width/Height

```toml
[display]
width = 1920
height = 1080
```

## Available Presets

| Preset | Resolution | Description |
|--------|------------|-------------|
| `auto` | Detected | Auto-detect system resolution |
| `fhd` | 1920x1080 | Full HD / 1080p |
| `hd` | 1280x720 | HD / 720p |
| `pi_touch` | 800x480 | Raspberry Pi Touch Display |
| `xga` | 1024x768 | XGA 4:3 aspect ratio |
| `svga` | 800x600 | SVGA 4:3 aspect ratio |
| `sxga` | 1280x1024 | SXGA 5:4 aspect ratio |
| `4k` | 3840x2160 | 4K UHD / 2160p |

## Hardware-Specific Examples

### Raspberry Pi 4/5 with Full HD Monitor

```toml
[display]
resolution = "fhd"

[sdl]
videodriver = "kmsdrm"
audiodriver = "alsa"
nomouse = true

[performance]
target_fps = 60
vsync = true
hardware_acceleration = true
```

### Raspberry Pi with Official Touch Display

```toml
[display]
resolution = "pi_touch"

[sdl]
videodriver = "kmsdrm"
audiodriver = "alsa"
nomouse = true

[performance]
target_fps = 60
vsync = true
```

### Custom 4K Setup

```toml
[display]
resolution = "4k"

[sdl]
videodriver = "kmsdrm"
audiodriver = "alsa"
nomouse = true

[performance]
target_fps = 30          # Reduced for 4K
vsync = true
hardware_acceleration = true
```

### Legacy VGA Monitor

```toml
[display]
resolution = "svga"      # 800x600

[sdl]
videodriver = "fbcon"
audiodriver = "alsa"
fbdev = "/dev/fb0"
nomouse = true

[performance]
target_fps = 60
```

### Desktop Development

```toml
[display]
resolution = "auto"      # Use desktop resolution

[sdl]
videodriver = "x11"
audiodriver = "pulse"
nomouse = false          # Keep mouse for debugging

[performance]
target_fps = 60
```

## Auto-Detection Methods

The system tries multiple methods to detect your display resolution:

1. **fbset** - Framebuffer information (Linux)
2. **xrandr** - X11 display information
3. **vcgencmd** - Raspberry Pi GPU information
4. **sysfs** - Linux graphics subsystem information

## Performance Optimization

Resolution-based optimizations are automatically applied:

### High Resolution (4K+)
- Target FPS: 30
- Fade time: 2000ms
- Hardware acceleration: Required

### Full HD (1920x1080)
- Target FPS: 60
- Fade time: 1500ms
- Hardware acceleration: Recommended

### Low Resolution (≤800x600)
- Target FPS: 60
- Fade time: 1000ms
- Hardware acceleration: Optional

## Testing

### Test Display Detection

```bash
python3 test_display.py
```

### Test Configuration

```bash
python3 -c "
from config import TeleFrameConfig
config = TeleFrameConfig.from_file()
print(f'Resolution: {config.display_width}x{config.display_height}')
print(f'Display info: {config.get_display_info()}')
"
```

### Test Presets

```bash
python3 -c "
from config import TeleFrameConfig
config = TeleFrameConfig()
presets = config.get_available_presets()
for name, (w, h) in presets.items():
    print(f'{name}: {w}x{h}')
"
```

## Troubleshooting

### Common Issues

**1. Resolution not detected**
```toml
[display]
resolution = "fhd"  # Use specific preset instead of auto
```

**2. Performance issues with high resolution**
```toml
[display]
resolution = "hd"   # Use lower resolution

[performance]
target_fps = 30     # Reduce FPS
```

**3. Display doesn't fit screen**
```toml
[display]
resolution = "auto"  # Let system detect optimal resolution
```

### Debug Information

Enable debug logging:
```toml
log_level = "DEBUG"
```

Check detected information:
```bash
python3 -c "
from config import TeleFrameConfig
config = TeleFrameConfig()
info = config.get_system_info()
for key, value in info.items():
    print(f'{key}: {value}')
"
```

### Validation

The system validates resolutions:
- Minimum: 320x240
- Maximum: 7680x4320
- Warns about unusual aspect ratios
- Optimizes for detected hardware

## Migration from Hardcoded Resolution

If you previously had hardcoded resolution in your main application:

### Before
```python
# Hardcoded in main.py
SCREEN_WIDTH = 1920
SCREEN_HEIGHT = 1080
```

### After
```python
# Use from config
from config import TeleFrameConfig
config = TeleFrameConfig.from_file()
SCREEN_WIDTH = config.display_width
SCREEN_HEIGHT = config.display_height
```

Or directly:
```python
width, height = config.get_display_resolution()
```

## API Reference

### Configuration Methods

```python
# Get current resolution
width, height = config.get_display_resolution()

# Set resolution
config.set_display_resolution(1920, 1080)

# Set resolution by preset
config.set_display_resolution_preset("fhd")

# Get available presets
presets = config.get_available_presets()

# Get display information
display_info = config.get_display_info()

# Optimize for current resolution
config.optimize_for_resolution()
```

### Display Information

```python
display_info = config.get_display_info()
# Returns:
# {
#     "width": 1920,
#     "height": 1080,
#     "resolution_string": "1920x1080",
#     "aspect_ratio": 1.78,
#     "aspect_name": "16:9",
#     "pixel_count": 2073600,
#     "density_category": "Full HD",
#     "fullscreen": true,
#     "sdl_driver": "kmsdrm",
#     "hardware_acceleration": true,
#     "is_raspberry_pi": true,
#     "is_pi_touch": false
# }
```

## Examples

### Complete Configuration

```toml
# TeleFrame Configuration with Display Settings
bot_token = "YOUR_BOT_TOKEN"
whitelist_chats = []
whitelist_admins = []

# Image settings
image_folder = "images"
image_count = 30
image_order = "random"

# Display configuration
[display]
resolution = "auto"

# System settings
fullscreen = true
fade_time = 1500
interval = 10000
hide_cursor = true
disable_screensaver = true

# SDL configuration
[sdl]
videodriver = "kmsdrm"
audiodriver = "alsa"
nomouse = true

# Performance settings
[performance]
target_fps = 60
vsync = true
hardware_acceleration = true
```

This configuration provides a flexible, auto-detecting display system that works across different Raspberry Pi models and desktop environments.
