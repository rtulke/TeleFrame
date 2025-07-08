#!/usr/bin/env python3
# setup.py - TeleFrame Installation and Setup
"""
TeleFrame setup and installation script
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
    """Create default configuration file"""
    print("\n⚙️  Creating default configuration...")

    config_file = Path("config.toml")

    if config_file.exists():
        print("📄 Configuration file already exists")
        return

    default_config = '''# TeleFrame Configuration

# Telegram Bot Settings
bot_token = "YOUR_BOT_TOKEN_HERE"  # Get from @BotFather
whitelist_chats = []  # Add chat IDs to restrict access: [123456789, 987654321]
whitelist_admins = []  # Add admin chat IDs: [123456789]

# Image Management
image_folder = "images"
image_count = 30
auto_delete_images = true
show_videos = true

# Display Settings
fullscreen = true
fade_time = 1500  # milliseconds
interval = 10000  # milliseconds (10 seconds)
random_order = true

# UI Settings
show_sender = true
show_caption = true
crop_zoom_images = false

# Audio Settings
play_sound_on_receive = "sound1.mp3"
play_video_audio = false

# System Settings
toggle_monitor = false
turn_on_hour = 9
turn_off_hour = 22

# Security Settings
max_file_size = 52428800  # 50MB in bytes
allowed_file_types = [".jpg", ".jpeg", ".png", ".gif", ".mp4"]

# Logging
log_level = "INFO"
# log_file = "teleframe.log"  # Uncomment to enable file logging
'''

    try:
        with open(config_file, "w") as f:
            f.write(default_config)

        print(f"✅ Created configuration file: {config_file}")
        print("📝 Edit config.toml to set your bot token and preferences")

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
Environment=SDL_VIDEODRIVER=fbcon
Environment=SDL_FBDEV=/dev/fb0
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

    directories = ["images", "logs", "sounds"]

    for directory in directories:
        dir_path = Path(directory)
        dir_path.mkdir(exist_ok=True)
        print(f"✅ Created directory: {directory}")


def main():
    """Main setup function"""
    print("🖼️  TeleFrame Python Setup")
    print("=" * 50)

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

    # Create configuration
    create_default_config()

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
    print("2. Test with: ./venv/bin/python main.py")
    print("3. Install systemd service (on Pi) for auto-start")

    if not is_pi:
        print("\n💻 Desktop testing:")
        print("   Export SDL_VIDEODRIVER=x11 for X11 display")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Setup interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Setup failed: {e}")
        sys.exit(1)
