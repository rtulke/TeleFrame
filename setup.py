#!/usr/bin/env python3
# setup.py - TeleFrame Installation and Setup - FIXED VERSION
"""
TeleFrame setup and installation script with corrected configuration
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path


def check_system():
    """Check system requirements"""
    print("🔍 Checking system requirements...")

    # Check Python version
    if sys.version_info < (3, 10):
        print("❌ Python 3.10+ required")
        sys.exit(1)
    print(f"✅ Python {sys.version}")

    # Check if running on Raspberry Pi
    is_pi = Path("/proc/device-tree/model").exists()
    if is_pi:
        try:
            with open("/proc/device-tree/model", "r") as f:
                model = f.read().strip()
            print(f"✅ Detected: {model}")
        except:
            print("✅ Raspberry Pi detected")

    # Check framebuffer
    if Path("/dev/fb0").exists():
        print("✅ Framebuffer available: /dev/fb0")
    else:
        print("⚠️  Framebuffer not found - desktop testing mode")

    return is_pi


def install_system_dependencies():
    """Install system dependencies for Raspberry Pi"""
    print("\n📦 Installing system dependencies...")

    try:
        # Update package list
        subprocess.run(["sudo", "apt", "update"], check=True)

        # Install required packages
        packages = [
            "python3-dev",
            "python3-pip",
            "python3-venv",
            "libsdl2-dev",
            "libsdl2-image-dev",
            "libsdl2-mixer-dev",
            "libsdl2-ttf-dev",
            "libfreetype6-dev",
            "libportmidi-dev",
            "libmagic1",
            "libjpeg-dev",
            "zlib1g-dev"
        ]

        subprocess.run(["sudo", "apt", "install", "-y"] + packages, check=True)
        print("✅ System dependencies installed")

    except subprocess.CalledProcessError as e:
        print(f"❌ Error installing system dependencies: {e}")
        sys.exit(1)


def setup_virtual_environment():
    """Create and setup Python virtual environment"""
    print("\n🐍 Setting up Python virtual environment...")

    venv_path = Path("venv")

    if venv_path.exists():
        print("📁 Virtual environment already exists")
        return venv_path

    try:
        # Create virtual environment
        subprocess.run([sys.executable, "-m", "venv", "venv"], check=True)

        # Upgrade pip
        pip_path = venv_path / "bin" / "pip"
        subprocess.run([str(pip_path), "install", "--upgrade", "pip"], check=True)

        print("✅ Virtual environment created")
        return venv_path

    except subprocess.CalledProcessError as e:
        print(f"❌ Error creating virtual environment: {e}")
        sys.exit(1)


def install_python_dependencies(venv_path: Path):
    """Install Python dependencies"""
    print("\n📚 Installing Python dependencies...")

    pip_path = venv_path / "bin" / "pip"
    requirements_file = Path("requirements.txt")

    if not requirements_file.exists():
        print("❌ requirements.txt not found")
        sys.exit(1)

    try:
        subprocess.run([
            str(pip_path), "install", "-r", str(requirements_file)
        ], check=True)

        print("✅ Python dependencies installed")

    except subprocess.CalledProcessError as e:
        print(f"❌ Error installing Python dependencies: {e}")
        sys.exit(1)


def create_default_config():
    """Create default configuration file with CORRECT image_order parameter"""
    print("\n⚙️  Creating default configuration...")

    config_file = Path("config.toml")

    if config_file.exists():
        print("📄 Configuration file already exists")
        return

    # FIXED: Use correct image_order instead of random_order
    default_config = '''# TeleFrame Configuration File
# Configure your digital picture frame settings

# Telegram Bot Settings
bot_token = "YOUR_BOT_TOKEN_HERE"  # Get from @BotFather
whitelist_chats = []               # Add chat IDs to restrict access: [-123456789, 987654321]
whitelist_admins = []              # Add admin chat IDs: [123456789]

# Image Management
image_folder = "images"            # Folder to store received images
image_count = 30                   # Maximum number of images in slideshow rotation
auto_delete_images = true          # Automatically delete old images when limit reached
show_videos = true                 # Display video files in slideshow

# Display Settings
fullscreen = true                  # Run in fullscreen mode
fade_time = 1500                   # Fade transition time in milliseconds, default 1500
interval = 10000                   # Time each image is displayed in milliseconds (10 seconds)
image_order = "random"             # "random", "latest", "oldest", "sequential"

# UI Settings
show_sender = true                 # Display sender name on images
show_caption = true                # Display image captions
crop_zoom_images = false           # Crop/zoom images to fill screen (vs letterbox)

# Audio Settings
play_sound_on_receive = "sound1.mp3"  # Sound file to play when receiving images
play_video_audio = false           # Play audio when displaying videos

# System Settings
toggle_monitor = false             # Automatically turn monitor on/off
turn_on_hour = "09:00"             # Hour to turn monitor on (HH:MM format)
turn_off_hour = "22:00"            # Hour to turn monitor off (HH:MM format)

# SDL/Display Configuration
[sdl]
# Video driver configuration for different Raspberry Pi setups
videodriver = "kmsdrm"             # Options: "kmsdrm" (modern Pi), "fbcon" (legacy), "x11" (desktop)
audiodriver = "alsa"               # Audio driver: "alsa", "pulse", "dummy"
fbdev = "/dev/fb0"                 # Framebuffer device (only used with fbcon driver)
nomouse = true                     # Hide mouse cursor

# Advanced SDL settings (optional)
[sdl.extra_env]
# SDL_VIDEODRIVER_OPTIONS = "fbcon"      # Additional video driver options
# SDL_FBDEV_MOUSE = "/dev/input/mice"    # Mouse device for framebuffer
# SDL_MOUSE_RELATIVE = "0"               # Disable relative mouse mode

# Bot Rate Limiting Configuration
[bot_rate_limiting]
enabled = true                     # Enable rate limiting
window_seconds = 60                # Time window for rate limiting
max_messages = 10                  # Maximum messages per window
whitelist_exempt = true            # Exempt whitelisted chats from rate limiting
admin_exempt = true                # Exempt admin chats from rate limiting
ban_duration_minutes = 5           # Duration of temporary ban

# Security Settings
max_file_size = 52428800           # 50MB in bytes (or 10MB = 10485760)
allowed_file_types = [".jpg", ".jpeg", ".png", ".gif", ".mp4"]  # Allowed file extensions

# Logging Configuration
log_level = "INFO"                 # Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL
# log_file = "logs/teleframe.log"   # Uncomment to enable file logging

# Performance Settings
[performance]
target_fps = 60                    # Target frame rate
vsync = true                       # Enable vertical sync
hardware_acceleration = true       # Use hardware acceleration if available

# Hardware-specific configurations:
#
# Modern Raspberry Pi 4/5 with DRM/KMS:
# [sdl]
# videodriver = "kmsdrm"
# audiodriver = "alsa"
# nomouse = true
#
# Legacy Raspberry Pi or older systems:
# [sdl]
# videodriver = "fbcon"
# audiodriver = "alsa"
# fbdev = "/dev/fb0"
# nomouse = true
#
# Desktop development/testing:
# [sdl]
# videodriver = "x11"
# audiodriver = "pulse"
# nomouse = false
#
# Headless testing:
# [sdl]
# videodriver = "dummy"
# audiodriver = "dummy"
# nomouse = true
'''

    try:
        with open(config_file, "w") as f:
            f.write(default_config)

        print(f"✅ Created configuration file: {config_file}")
        print("📝 Edit config.toml to set your bot token and preferences")
        print("🔄 Note: Using new 'image_order' parameter (replaces old 'random_order')")

    except Exception as e:
        print(f"❌ Error creating configuration: {e}")


def create_systemd_service():
    """Create systemd service file"""
    print("\n🔧 Creating systemd service...")

    service_content = f'''[Unit]
Description=TeleFrame Digital Picture Frame
After=network.target

[Service]
Type=simple
User={os.getenv("USER", "pi")}
WorkingDirectory={Path.cwd()}
Environment=SDL_VIDEODRIVER=kmsdrm
Environment=SDL_AUDIODRIVER=alsa
Environment=DISPLAY=:0
ExecStart={Path.cwd()}/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
'''

    service_file = Path("teleframe.service")

    try:
        with open(service_file, "w") as f:
            f.write(service_content)

        print(f"✅ Created service file: {service_file}")
        print("📋 To install system service:")
        print(f"   sudo cp {service_file} /etc/systemd/system/")
        print("   sudo systemctl enable teleframe")
        print("   sudo systemctl start teleframe")

    except Exception as e:
        print(f"❌ Error creating service file: {e}")


def create_directories():
    """Create necessary directories"""
    print("\n📁 Creating directories...")

    directories = ["images", "logs", "sounds", "cache", "data"]

    for directory in directories:
        dir_path = Path(directory)
        dir_path.mkdir(exist_ok=True)
        print(f"✅ Created directory: {directory}")


def validate_config():
    """Validate the created configuration"""
    print("\n🧪 Validating configuration...")
    
    try:
        # Try to import and test the config
        sys.path.insert(0, str(Path.cwd()))
        from config import TeleFrameConfig
        
        config = TeleFrameConfig.from_file("config.toml")
        
        print(f"✅ Configuration validation successful")
        print(f"   Image order: {config.get_image_order_mode()}")
        print(f"   Description: {config.get_image_order_description()}")
        print(f"   SDL driver: {config.sdl_videodriver}")
        print(f"   Monitor control: {'Enabled' if config.toggle_monitor else 'Disabled'}")
        
    except ImportError as e:
        print(f"⚠️  Could not import config module: {e}")
        print("   This is normal during initial setup")
    except Exception as e:
        print(f"❌ Configuration validation failed: {e}")
        print("   Please check your config.toml file manually")


def main():
    """Main setup function"""
    print("🖼️  TeleFrame Python Setup - Enhanced Version")
    print("=" * 60)

    # Check if we're root (not recommended)
    if os.geteuid() == 0:
        print("⚠️  Warning: Running as root is not recommended")
        response = input("Continue anyway? (y/N): ")
        if response.lower() != 'y':
            sys.exit(1)

    # Check system
    is_pi = check_system()

    # Install system dependencies on Raspberry Pi
    if is_pi:
        response = input("\n📦 Install system dependencies? (Y/n): ")
        if response.lower() != 'n':
            install_system_dependencies()

    # Setup virtual environment
    venv_path = setup_virtual_environment()

    # Install Python dependencies
    install_python_dependencies(venv_path)

    # Create configuration (if it doesn't exist)
    create_default_config()

    # Validate configuration
    validate_config()

    # Create directories
    create_directories()

    # Create systemd service
    if is_pi:
        response = input("\n🔧 Create systemd service? (Y/n): ")
        if response.lower() != 'n':
            create_systemd_service()

    print("\n🎉 Setup complete!")
    print("\n📋 Next steps:")
    print("1. Edit config.toml and set your bot token")
    print("2. Configure image_order: 'random', 'latest', 'oldest', or 'sequential'")
    print("3. Test with: ./venv/bin/python main.py")
    print("4. Install systemd service (on Pi) for auto-start")

    if not is_pi:
        print("\n💻 Desktop testing:")
        print("   Export SDL_VIDEODRIVER=x11 for X11 display")

    print("\n🆕 New Features:")
    print("   • Image order control: random, latest, oldest, sequential")
    print("   • Bot rate limiting with configurable settings")
    print("   • Monitor control with time scheduling")
    print("   • Enhanced configuration with validation")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Setup interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Setup failed: {e}")
        sys.exit(1)
