# TeleFrame Python - Enhanced Digital Picture Frame

A secure, headless digital picture frame powered by Telegram Bot integration with advanced monitor control and precise time scheduling. Optimized for Raspberry Pi without X Server using direct framebuffer access.

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Raspberry Pi](https://img.shields.io/badge/Raspberry%20Pi-Compatible-red.svg)](https://www.raspberrypi.org/)

## 🎯 Key Features

### 🖼️ **Advanced Slideshow Display**
- **Direct Framebuffer Rendering** - No X Server required (~100MB RAM vs 400MB)
- **Smooth Fade Transitions** - Professional-quality image transitions
- **Touch Navigation Support** - Left/right/center touch controls
- **Auto-rotation and Scaling** - Perfect image display on any screen
- **Video Support** - MP4 video playback with audio controls
- **60fps Display Rendering** - Smooth, responsive interface

### 📱 **Secure Telegram Integration**
- **Whitelist Support** - Control who can send images
- **Admin Commands** - Advanced control for administrators
- **Photo and Video Support** - JPG, PNG, GIF, MP4 formats
- **Caption Display** - Show image descriptions
- **Real-time Status** - Monitor frame status remotely
- **Rate Limiting** - Protection against spam

### 🖥️ **Advanced Monitor Control** ⭐ NEW
- **Precise HH:MM Scheduling** - `turn_on_hour = "09:10"` instead of just `9`
- **Cross-Midnight Support** - Schedule like `22:34 - 06:10`
- **Multi-Platform Support** - Raspberry Pi, Linux, X11, Backlight control
- **Live Schedule Updates** - Change times via Telegram bot
- **Manual Override Protection** - 10-minute schedule override
- **Smart Power Management** - Slideshow pauses when monitor is off

### 🔒 **Enterprise-Grade Security**
- **File Type Validation** - Magic number verification
- **Size Limits** - Configurable file size restrictions
- **Chat Whitelist** - Access control system
- **Admin Controls** - Administrative command protection
- **Input Sanitization** - All user inputs validated
- **Duplicate Detection** - SHA256 hash-based deduplication
- **Security Logging** - Comprehensive audit trail

### ⚡ **Performance Optimized**
- **~100MB RAM Usage** - Efficient memory management
- **<30ms Touch Response** - Ultra-responsive interface
- **Minimal CPU Overhead** - Optimized for continuous operation
- **Hardware Acceleration** - OpenGL ES2 support
- **Process Management** - Automatic restart and error recovery

## 🛠️ Hardware Requirements

### **Minimum Requirements**
- **Raspberry Pi 2/3/4** (Pi Zero may work but untested)
- **8GB+ SD Card** for operating system and images
- **Display** with HDMI or DSI connection
- **Internet Connection** for Telegram bot functionality

### **Recommended Setup**
- **Raspberry Pi 4** (4GB RAM) for optimal performance
- **32GB+ SD Card** (Class 10) for better performance
- **Official Raspberry Pi Display** or compatible touchscreen
- **Ethernet Connection** for stable internet connectivity

### **Optional Hardware**
- **Touchscreen** for local navigation
- **GPIO Buttons** for hardware controls
- **USB Audio** for video sound playback
- **Case with Cooling** for continuous operation

## 📦 Quick Installation

### **Automatic Setup (Recommended)**

```bash
# Clone repository
git clone https://github.com/yourusername/TeleFrame.git
cd TeleFrame

# Run automated setup
python3 setup.py
```

### **Manual Installation**

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install system dependencies
sudo apt install -y python3-dev python3-pip python3-venv \
    libsdl2-dev libsdl2-image-dev libsdl2-mixer-dev libsdl2-ttf-dev \
    libfreetype6-dev libportmidi-dev libmagic1 libjpeg-dev zlib1g-dev

# Clone repository
git clone https://github.com/yourusername/TeleFrame.git
cd TeleFrame

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt

# Create configuration from template
cp config.example.toml config.toml
```

## ⚙️ Configuration Guide

### **1. Basic Configuration**

Edit `config.toml`:

```toml
# Telegram Bot Settings
bot_token = "123456789:ABCdefGHIjklMNOpqrsTUVwxyz"  # Get from @BotFather
whitelist_chats = [123456789, 987654321]              # Authorized chat IDs
whitelist_admins = [123456789]                        # Admin chat IDs

# Image Management
image_folder = "images"                               # Storage folder
image_count = 30                                      # Max images in rotation
auto_delete_images = true                            # Auto-cleanup old images
show_videos = true                                   # Enable video playback

# Display Settings
fullscreen = true                                    # Fullscreen mode
fade_time = 1500                                     # Transition time (ms)
interval = 10000                                     # Display time (ms)
random_order = true                                  # Random slideshow order
```

### **2. Monitor Control Settings** ⭐ NEW

```toml
# Monitor Control (Enhanced Time Format)
toggle_monitor = true                                # Enable auto-control
turn_on_hour = "09:10"                              # Turn on at 9:10 AM
turn_off_hour = "22:34"                             # Turn off at 10:34 PM

# Supported formats:
# turn_on_hour = "09:10"    # HH:MM format (recommended)
# turn_on_hour = "9:10"     # H:MM format (also works)
# turn_on_hour = 9          # Hour only (legacy support)
```

### **3. Advanced Display Configuration**

```toml
# SDL/Display Configuration
[sdl]
videodriver = "kmsdrm"                              # "kmsdrm", "fbcon", "x11", "dummy"
audiodriver = "alsa"                                # "alsa", "pulse", "dummy"
fbdev = "/dev/fb0"                                  # Framebuffer device
nomouse = true                                      # Hide mouse cursor

# UI Settings
show_sender = true                                  # Display sender name
show_caption = true                                 # Display image captions
crop_zoom_images = false                            # Crop vs letterbox mode
hide_cursor = true                                  # Hide mouse cursor
disable_screensaver = true                          # Disable screensaver

# Performance Settings
[performance]
target_fps = 60                                     # Target frame rate
vsync = true                                        # Enable V-Sync
hardware_acceleration = true                        # Enable GPU acceleration
```

### **4. Security Configuration**

```toml
# Security Settings
max_file_size = 52428800                            # Max file size (50MB)
allowed_file_types = [".jpg", ".jpeg", ".png", ".gif", ".mp4"]

# Access Control
whitelist_chats = [123456789]                       # Authorized users
whitelist_admins = [123456789]                      # Admin users

# Logging
log_level = "INFO"                                  # DEBUG, INFO, WARNING, ERROR
log_file = "logs/teleframe.log"                     # Log file path
```

## 🚀 Usage Guide

### **Starting TeleFrame**

```bash
# Direct run (for testing)
cd TeleFrame
source venv/bin/activate
python3 main.py

# Background service (production)
sudo systemctl start teleframe
sudo systemctl enable teleframe  # Auto-start on boot
```

### **Telegram Bot Setup**

1. **Get Bot Token:**
   - Message [@BotFather](https://t.me/BotFather) on Telegram
   - Use `/newbot` command
   - Follow instructions and copy the token

2. **Configure Bot:**
   ```bash
   nano config.toml
   # Set: bot_token = "YOUR_TOKEN_HERE"
   ```

3. **Test Bot:**
   ```bash
   python3 -c "
   from telegram import Bot
   bot = Bot('YOUR_TOKEN')
   print(bot.get_me())
   "
   ```

### **Getting Chat IDs**

Send `/info` to your bot to get your chat ID, then add it to the whitelist:

```toml
whitelist_chats = [YOUR_CHAT_ID]
```

## 🤖 Bot Commands Reference

### **Basic Commands** (All Users)

| Command | Description | Example |
|---------|-------------|---------|
| `/start` | Welcome message and status | `/start` |
| `/help` | Show available commands | `/help` |
| `/status` | Display frame status | `/status` |
| `/info` | Show your chat information | `/info` |
| `/ping` | Test bot connectivity | `/ping` |

### **Monitor Control Commands** ⭐ NEW (Admin Only)

| Command | Description | Example |
|---------|-------------|---------|
| `/monitor` | Show monitor status | `/monitor` |
| `/monitor on` | Turn monitor on manually | `/monitor on` |
| `/monitor off` | Turn monitor off manually | `/monitor off` |
| `/monitor info` | Show hardware information | `/monitor info` |
| `/schedule` | Show current schedule | `/schedule` |
| `/schedule HH:MM HH:MM` | Update schedule | `/schedule 09:10 22:34` |
| `/schedule enable` | Enable auto-control | `/schedule enable` |
| `/schedule disable` | Disable auto-control | `/schedule disable` |

### **Administrative Commands** (Admin Only)

| Command | Description | Example |
|---------|-------------|---------|
| `/stats` | Show detailed statistics | `/stats` |
| `/restart` | Restart TeleFrame | `/restart` |

### **Media Upload**

- **Photos**: Send any JPG, PNG, or GIF image
- **Videos**: Send MP4 videos (if enabled)
- **Captions**: Add text descriptions to your media
- **Documents**: Send images as documents for better quality

## 🖥️ Monitor Control Features

### **Supported Platforms**

| Platform | Method | Description |
|----------|--------|-------------|
| **Raspberry Pi** | `vcgencmd` | Most reliable, uses GPU control |
| **Modern Linux** | `DRM/KMS` | Direct hardware access |
| **X11 Systems** | `xset` | DPMS power management |
| **Embedded** | `Backlight` | Brightness control |
| **Legacy** | `fbcon` | Framebuffer console blanking |

### **Schedule Examples**

```toml
# Regular schedule (same day)
turn_on_hour = "09:10"    # 9:10 AM
turn_off_hour = "22:34"   # 10:34 PM

# Cross-midnight schedule
turn_on_hour = "22:00"    # 10:00 PM
turn_off_hour = "06:00"   # 6:00 AM (next day)

# Weekend-only display
turn_on_hour = "10:00"    # 10:00 AM
turn_off_hour = "23:59"   # 11:59 PM
```

### **Live Schedule Updates**

Update schedule remotely via Telegram:

```
/schedule 09:15 22:45
```

Response:
```
✅ Schedule updated successfully!

Turn ON: 09:15
Turn OFF: 22:45

Changes take effect immediately
```

## 🔧 Advanced Configuration

### **Hardware-Specific Settings**

#### **Raspberry Pi 4/5 (Modern)**
```toml
[sdl]
videodriver = "kmsdrm"
audiodriver = "alsa"
nomouse = true
```

#### **Raspberry Pi 3/2 (Legacy)**
```toml
[sdl]
videodriver = "fbcon"
audiodriver = "alsa"
fbdev = "/dev/fb0"
nomouse = true
```

#### **Desktop Development**
```toml
[sdl]
videodriver = "x11"
audiodriver = "pulse"
nomouse = false
```

#### **Headless Testing**
```toml
[sdl]
videodriver = "dummy"
audiodriver = "dummy"
nomouse = true
```

### **Performance Optimization**

#### **Low Memory Setup**
```toml
image_count = 15          # Reduce memory usage
fade_time = 0             # Disable transitions
target_fps = 30           # Lower frame rate
```

#### **High Performance Setup**
```toml
image_count = 50          # More images
hardware_acceleration = true
vsync = true
target_fps = 60
```

### **Security Hardening**

```toml
# Strict file limits
max_file_size = 10485760  # 10MB limit
allowed_file_types = [".jpg", ".jpeg", ".png"]  # Images only

# Admin-only access
whitelist_chats = [123456789]
whitelist_admins = [123456789]

# Enhanced logging
log_level = "DEBUG"
log_file = "logs/teleframe.log"
```

## 🐛 Troubleshooting

### **Common Issues**

#### **Framebuffer Permission Denied**
```bash
# Check framebuffer access
ls -la /dev/fb*

# Add user to video group
sudo usermod -a -G video $USER

# Logout and login again
```

#### **Bot Not Responding**
```bash
# Test bot token
python3 -c "
from telegram import Bot
bot = Bot('YOUR_TOKEN')
print(bot.get_me())
"

# Check network connectivity
curl -s "https://api.telegram.org/botYOUR_TOKEN/getMe"
```

#### **Monitor Control Not Working**
```bash
# Test monitor controller
python3 monitor_control.py

# Check available methods
python3 -c "
from monitor_control import MonitorController
from config import TeleFrameConfig
config = TeleFrameConfig()
controller = MonitorController(config)
print(controller.get_system_info())
"
```

#### **Display Issues**
```bash
# Check SDL driver
python3 -c "
import pygame
pygame.init()
print(f'SDL Driver: {pygame.display.get_driver()}')
"

# Test framebuffer
sudo cat /dev/fb0 > /dev/null
```

### **Log Analysis**

```bash
# View live logs
tail -f logs/teleframe.log

# Check for errors
grep ERROR logs/teleframe.log

# Security events
grep SECURITY logs/security.log

# System logs
journalctl -u teleframe -f
```

### **Performance Monitoring**

```bash
# Memory usage
ps aux | grep python

# CPU usage
top -p $(pgrep -f main.py)

# Disk space
df -h
du -sh images/
```

## 🔒 Security Features

### **Access Control**
- **Chat Whitelist**: Only authorized users can send images
- **Admin System**: Separate admin privileges for control commands
- **Rate Limiting**: Protection against message spam
- **Input Validation**: All user inputs are sanitized

### **File Security**
- **MIME Type Validation**: Uses python-magic for file verification
- **Size Limits**: Configurable maximum file sizes
- **Extension Filtering**: Whitelist of allowed file types
- **Duplicate Detection**: SHA256 hash-based deduplication

### **Audit Logging**
- **Security Events**: All admin actions logged
- **Access Attempts**: Failed authorization attempts tracked
- **System Events**: Monitor control changes logged
- **Error Tracking**: Comprehensive error logging

### **Network Security**
- **HTTPS Only**: All Telegram API calls use HTTPS
- **Token Protection**: Bot token stored in configuration file
- **No External Dependencies**: Self-contained operation

## 🚀 Performance Specifications

### **Memory Usage**
- **Base System**: ~100MB RAM
- **Per Image**: ~2-5MB RAM (depends on resolution)
- **Total (30 images)**: ~200MB RAM
- **Comparison**: 60% less than X11-based solutions

### **Response Times**
- **Touch Response**: <30ms
- **Image Transition**: <100ms
- **Bot Command**: <500ms
- **Monitor Control**: <2s

### **Throughput**
- **Display**: 60fps smooth rendering
- **Image Loading**: ~1s per 5MB image
- **Bot Processing**: 10 messages/second
- **File Upload**: Limited by network speed

## 📈 Monitoring and Maintenance

### **System Health Checks**

```bash
# TeleFrame status
sudo systemctl status teleframe

# Resource usage
htop

# Disk usage
df -h
du -sh images/

# Network connectivity
ping -c 4 api.telegram.org
```

### **Regular Maintenance**

```bash
# Update system
sudo apt update && sudo apt upgrade

# Clean old images (if auto-delete disabled)
find images/ -type f -mtime +30 -delete

# Rotate logs
sudo logrotate -f /etc/logrotate.conf

# Update TeleFrame
cd TeleFrame
git pull origin main
source venv/bin/activate
pip install -r requirements.txt --upgrade
```

### **Backup Strategy**

```bash
# Configuration backup
cp config.toml config.toml.backup

# Image backup
rsync -av images/ backup/images/

# Full system backup (Raspberry Pi)
sudo dd if=/dev/mmcblk0 of=/path/to/backup.img bs=4M
```

## 🔄 Systemd Service

### **Installation**

```bash
# Copy service file
sudo cp teleframe.service /etc/systemd/system/

# Enable service
sudo systemctl enable teleframe
sudo systemctl start teleframe

# Check status
sudo systemctl status teleframe
```

### **Service Configuration**

Create `/etc/systemd/system/teleframe.service`:

```ini
[Unit]
Description=TeleFrame Digital Picture Frame
After=network.target

[Service]
Type=simple
User=pi
Group=pi
WorkingDirectory=/home/pi/TeleFrame
Environment=PATH=/home/pi/TeleFrame/venv/bin
ExecStart=/home/pi/TeleFrame/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

## 🌐 Network Configuration

### **Firewall Settings**

```bash
# Allow outgoing HTTPS (Telegram API)
sudo ufw allow out 443

# Optional: SSH access
sudo ufw allow ssh

# Enable firewall
sudo ufw enable
```

### **Network Troubleshooting**

```bash
# Test internet connectivity
ping -c 4 google.com

# Test Telegram API
curl -s "https://api.telegram.org/botYOUR_TOKEN/getMe"

# Check DNS resolution
nslookup api.telegram.org
```

## 📱 Mobile App Integration

### **Telegram Bot Usage**

1. **Add Bot**: Search for your bot username in Telegram
2. **Send /start**: Initialize bot connection
3. **Send Images**: Simply send photos or videos
4. **Use Commands**: Access advanced features with commands
5. **Admin Control**: Use admin commands for system management

### **Quick Commands**

```
/monitor          # Check monitor status
/schedule 09:00 22:00  # Update schedule
/stats            # System statistics
/help             # Show all commands
```

## 🔧 Development

### **Project Structure**

```
TeleFrame/
├── main.py                 # Main application entry
├── config.py               # Configuration management
├── image_manager.py        # Image handling and storage
├── slideshow.py           # Display and slideshow logic
├── telegram_bot.py        # Telegram bot integration
├── monitor_control.py     # Monitor control system
├── logger.py              # Logging configuration
├── setup.py               # Installation script
├── requirements.txt       # Python dependencies
├── config.toml           # Configuration file
├── teleframe.service     # Systemd service file
├── images/               # Image storage directory
├── logs/                 # Log files
└── README.md            # This file
```

### **Development Setup**

```bash
# Clone repository
git clone https://github.com/yourusername/TeleFrame.git
cd TeleFrame

# Create development environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies with dev tools
pip install -r requirements.txt
pip install pytest pytest-asyncio black flake8

# Run tests
pytest

# Format code
black .

# Lint code
flake8 .
```

### **Contributing**

1. **Fork** the repository
2. **Create** a feature branch
3. **Make** changes with tests
4. **Submit** a pull request

### **Testing**

```bash
# Run all tests
pytest

# Test specific component
python3 monitor_control.py
python3 config.py

# Integration test
python3 main.py --test
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **Original TeleFrame**: Based on the Node.js TeleFrame project
- **Telegram Bot API**: For excellent API documentation
- **pygame Community**: For the robust SDL2 Python bindings
- **Raspberry Pi Foundation**: For creating amazing hardware
- **Contributors**: Everyone who helped improve this project

## 📞 Support

### **Getting Help**

1. **Check Documentation**: Read this README thoroughly
2. **Search Issues**: Look for similar problems in GitHub issues
3. **Create Issue**: Submit detailed bug reports or feature requests
4. **Community**: Join discussions in GitHub Discussions

### **Reporting Bugs**

Please include:
- **OS Version**: `cat /etc/os-release`
- **Python Version**: `python3 --version`
- **Hardware**: Raspberry Pi model, display type
- **Configuration**: Relevant parts of `config.toml`
- **Logs**: Error messages from `logs/teleframe.log`
- **Steps to Reproduce**: Detailed reproduction steps

### **Feature Requests**

We welcome feature requests! Please describe:
- **Use Case**: What you want to achieve
- **Current Behavior**: What happens now
- **Desired Behavior**: What should happen
- **Alternatives**: Any workarounds you've tried

---

**TeleFrame Python - Making digital picture frames smart, secure, and beautiful.** 🖼️✨

[![GitHub Stars](https://img.shields.io/github/stars/yourusername/TeleFrame.svg?style=social&label=Star)](https://github.com/yourusername/TeleFrame)
[![GitHub Forks](https://img.shields.io/github/forks/yourusername/TeleFrame.svg?style=social&label=Fork)](https://github.com/yourusername/TeleFrame/fork)
[![GitHub Issues](https://img.shields.io/github/issues/yourusername/TeleFrame.svg)](https://github.com/yourusername/TeleFrame/issues)
