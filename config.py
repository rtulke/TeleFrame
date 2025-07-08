# config.py - Enhanced TeleFrame Configuration
"""
Enhanced configuration management with SDL optimization and cursor handling
"""

import logging
import os
import sys
from pathlib import Path
from typing import List, Optional, Dict, Any
import toml


class TeleFrameConfig:
    """Enhanced TeleFrame configuration class with robust SDL handling"""
    
    def __init__(self, **kwargs):
        # Telegram Bot Configuration
        self.bot_token = kwargs.get("bot_token", "bot-disabled")
        self.whitelist_chats = kwargs.get("whitelist_chats", [])
        self.whitelist_admins = kwargs.get("whitelist_admins", [])
        
        # Image Management
        self.image_folder = Path(kwargs.get("image_folder", "images"))
        self.image_count = kwargs.get("image_count", 30)
        self.auto_delete_images = kwargs.get("auto_delete_images", True)
        self.show_videos = kwargs.get("show_videos", True)
        
        # Display Settings
        self.fullscreen = kwargs.get("fullscreen", True)
        self.fade_time = kwargs.get("fade_time", 1500)
        self.interval = kwargs.get("interval", 10000)
        self.random_order = kwargs.get("random_order", True)
        
        # UI Settings
        self.show_sender = kwargs.get("show_sender", True)
        self.show_caption = kwargs.get("show_caption", True)
        self.crop_zoom_images = kwargs.get("crop_zoom_images", False)
        
        # Audio Settings
        self.play_sound_on_receive = kwargs.get("play_sound_on_receive", "sound1.mp3")
        self.play_video_audio = kwargs.get("play_video_audio", False)
        
        # System Settings
        self.toggle_monitor = kwargs.get("toggle_monitor", False)
        self.turn_on_hour = kwargs.get("turn_on_hour", 9)
        self.turn_off_hour = kwargs.get("turn_off_hour", 22)
        
        # Enhanced SDL/Display Configuration
        sdl_config = kwargs.get("sdl", {})
        self.sdl_videodriver = sdl_config.get("videodriver", self._detect_best_driver())
        self.sdl_audiodriver = sdl_config.get("audiodriver", "alsa")
        self.sdl_fbdev = sdl_config.get("fbdev", "/dev/fb0")
        
        # Cursor and Mouse Settings
        self.sdl_nomouse = sdl_config.get("nomouse", True)
        self.hide_cursor = kwargs.get("hide_cursor", True)
        self.disable_screensaver = kwargs.get("disable_screensaver", True)
        
        # Advanced SDL Settings
        self.sdl_extra_env = sdl_config.get("extra_env", {})
        
        # Performance Settings
        perf_config = kwargs.get("performance", {})
        self.target_fps = perf_config.get("target_fps", 60)
        self.vsync = perf_config.get("vsync", True)
        self.hardware_acceleration = perf_config.get("hardware_acceleration", True)
        
        # Security Settings
        self.max_file_size = kwargs.get("max_file_size", 50 * 1024 * 1024)
        self.allowed_file_types = kwargs.get("allowed_file_types", 
                                            [".jpg", ".jpeg", ".png", ".gif", ".mp4"])
        
        # Process Management
        self.enable_process_lock = kwargs.get("enable_process_lock", True)
        self.max_restart_attempts = kwargs.get("max_restart_attempts", 5)
        self.restart_delay = kwargs.get("restart_delay", 10)
        
        # Logging
        self.log_level = kwargs.get("log_level", "INFO")
        self.log_file = kwargs.get("log_file", None)
        if self.log_file:
            self.log_file = Path(self.log_file)
        
        # Error Handling
        self.max_errors_per_hour = kwargs.get("max_errors_per_hour", 100)
        self.enable_crash_recovery = kwargs.get("enable_crash_recovery", True)
        
        # Ensure directories exist
        self._ensure_directories()
        
        # Validate and apply settings
        self._validate()
        self._apply_system_optimizations()
    
    def _detect_best_driver(self) -> str:
        """Auto-detect the best SDL video driver for the system"""
        # Check if we're on Raspberry Pi
        if Path("/proc/device-tree/model").exists():
            try:
                with open("/proc/device-tree/model", "r") as f:
                    model = f.read().lower()
                    
                if "raspberry pi" in model:
                    # Modern Pi with KMS
                    if Path("/dev/dri/card0").exists():
                        return "kmsdrm"
                    # Fallback to framebuffer
                    elif Path("/dev/fb0").exists():
                        return "fbcon"
            except:
                pass
        
        # Check for framebuffer
        if Path("/dev/fb0").exists():
            return "fbcon"
        
        # Check for X11
        if os.environ.get("DISPLAY"):
            return "x11"
        
        # Headless fallback
        return "dummy"
    
    def _ensure_directories(self):
        """Create necessary directories"""
        directories = [
            self.image_folder,
            Path("logs"),
            Path("sounds"),
            Path("cache")
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
    
    def _validate(self):
        """Validate configuration values with enhanced checks"""
        # Validate image count
        if not 1 <= self.image_count <= 1000:
            raise ValueError("image_count must be between 1 and 1000")
        
        # Validate times
        if not 0 <= self.fade_time <= 10000:
            raise ValueError("fade_time must be between 0 and 10000 ms")
        
        if not 1000 <= self.interval <= 300000:
            raise ValueError("interval must be between 1000 and 300000 ms")
        
        # Validate hours
        if not 0 <= self.turn_on_hour <= 23:
            raise ValueError("turn_on_hour must be between 0 and 23")
        
        if not 0 <= self.turn_off_hour <= 23:
            raise ValueError("turn_off_hour must be between 0 and 23")
        
        # Validate FPS
        if not 10 <= self.target_fps <= 120:
            raise ValueError("target_fps must be between 10 and 120")
        
        # Validate log level
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if self.log_level.upper() not in valid_levels:
            raise ValueError(f"log_level must be one of: {valid_levels}")
        self.log_level = self.log_level.upper()
        
        # Validate file size
        if self.max_file_size > 500 * 1024 * 1024:  # 500MB max
            logging.warning("Very large max_file_size - may cause memory issues")
        
        # Normalize file extensions
        self.allowed_file_types = [
            ext.lower() if ext.startswith('.') else f'.{ext.lower()}' 
            for ext in self.allowed_file_types
        ]
        
        # Validate bot token format
        if self.bot_token != "bot-disabled" and self.bot_token != "YOUR_BOT_TOKEN_HERE":
            if not self._validate_bot_token(self.bot_token):
                logging.warning("Bot token format appears invalid")
    
    def _validate_bot_token(self, token: str) -> bool:
        """Validate bot token format"""
        parts = token.split(':')
        if len(parts) != 2:
            return False
        
        try:
            int(parts[0])  # First part should be numeric
            return len(parts[1]) >= 35  # Second part should be long enough
        except ValueError:
            return False
    
    def _apply_system_optimizations(self):
        """Apply system-level optimizations"""
        if sys.platform.startswith('linux'):
            self._apply_linux_optimizations()
    
    def _apply_linux_optimizations(self):
        """Apply Linux-specific optimizations"""
        try:
            # Set process priority (if running as root or with capabilities)
            if os.geteuid() == 0:
                os.nice(-10)  # Higher priority for smoother display
                
            # Set I/O priority (requires ionice)
            try:
                import subprocess
                subprocess.run(['ionice', '-c', '2', '-n', '4', '-p', str(os.getpid())], 
                             check=False, capture_output=True)
            except:
                pass
                
        except Exception as e:
            logging.debug(f"Could not apply system optimizations: {e}")
    
    @classmethod
    def from_file(cls, config_path: str = "config.toml") -> "TeleFrameConfig":
        """Load configuration from TOML file with error handling"""
        config_file = Path(config_path)
        
        if config_file.exists():
            try:
                config_data = toml.load(config_file)
                return cls(**config_data)
            except toml.TomlDecodeError as e:
                logging.error(f"TOML syntax error in {config_path}: {e}")
                logging.info("Using default configuration")
            except Exception as e:
                logging.warning(f"Error loading config file {config_path}: {e}")
                logging.info("Using default configuration")
        else:
            logging.info(f"Config file {config_path} not found, creating default")
            # Create default config file
            default_config = cls()
            default_config.save_to_file(config_path)
        
        return cls()
    
    def save_to_file(self, config_path: str = "config.toml"):
        """Save configuration to TOML file with backup"""
        config_file = Path(config_path)
        
        # Create backup if file exists
        if config_file.exists():
            backup_file = config_file.with_suffix('.toml.backup')
            try:
                import shutil
                shutil.copy2(config_file, backup_file)
            except Exception as e:
                logging.warning(f"Could not create config backup: {e}")
        
        # Convert to dict
        config_dict = self._to_dict()
        
        try:
            with open(config_file, 'w') as f:
                toml.dump(config_dict, f)
            logging.info(f"Configuration saved to {config_path}")
        except Exception as e:
            logging.error(f"Error saving config file: {e}")
    
    def _to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary for saving"""
        config_dict = {}
        
        # Group settings logically
        config_dict.update({
            'bot_token': self.bot_token,
            'whitelist_chats': self.whitelist_chats,
            'whitelist_admins': self.whitelist_admins,
            'image_folder': str(self.image_folder),
            'image_count': self.image_count,
            'auto_delete_images': self.auto_delete_images,
            'show_videos': self.show_videos,
            'fullscreen': self.fullscreen,
            'fade_time': self.fade_time,
            'interval': self.interval,
            'random_order': self.random_order,
            'show_sender': self.show_sender,
            'show_caption': self.show_caption,
            'crop_zoom_images': self.crop_zoom_images,
            'hide_cursor': self.hide_cursor,
            'disable_screensaver': self.disable_screensaver,
            'max_file_size': self.max_file_size,
            'allowed_file_types': self.allowed_file_types,
            'log_level': self.log_level,
        })
        
        if self.log_file:
            config_dict['log_file'] = str(self.log_file)
        
        # SDL configuration
        config_dict['sdl'] = {
            'videodriver': self.sdl_videodriver,
            'audiodriver': self.sdl_audiodriver,
            'fbdev': self.sdl_fbdev,
            'nomouse': self.sdl_nomouse,
            'extra_env': self.sdl_extra_env
        }
        
        # Performance configuration
        config_dict['performance'] = {
            'target_fps': self.target_fps,
            'vsync': self.vsync,
            'hardware_acceleration': self.hardware_acceleration
        }
        
        return config_dict
    
    def setup_sdl_environment(self):
        """Setup SDL environment variables with enhanced cursor handling"""
        # Clear existing SDL environment
        for key in list(os.environ.keys()):
            if key.startswith('SDL_'):
                del os.environ[key]
        
        # Set primary SDL configuration
        os.environ['SDL_VIDEODRIVER'] = self.sdl_videodriver
        os.environ['SDL_AUDIODRIVER'] = self.sdl_audiodriver
        
        # Framebuffer configuration
        if self.sdl_videodriver == 'fbcon':
            os.environ['SDL_FBDEV'] = self.sdl_fbdev
            os.environ['SDL_MOUSE_RELATIVE'] = '0'
        
        # Mouse and cursor configuration
        if self.sdl_nomouse or self.hide_cursor:
            os.environ['SDL_NOMOUSE'] = '1'
        
        # Always hide cursor for kiosk mode
        if self.hide_cursor:
            os.environ['SDL_VIDEO_WINDOW_POS'] = '0,0'
            os.environ['SDL_VIDEO_CENTERED'] = '0'
        
        # Screensaver handling
        if self.disable_screensaver:
            os.environ['SDL_VIDEO_ALLOW_SCREENSAVER'] = '0'
        
        # Performance optimizations
        if self.hardware_acceleration:
            os.environ['SDL_RENDER_DRIVER'] = 'opengles2'
        
        if self.vsync:
            os.environ['SDL_RENDER_VSYNC'] = '1'
        
        # DRM/KMS optimizations
        if self.sdl_videodriver == 'kmsdrm':
            os.environ['SDL_KMSDRM_REQUIRE_DRM_MASTER'] = '0'
        
        # Audio optimizations
        if self.sdl_audiodriver == 'alsa':
            os.environ['SDL_ALSA_PCM_CARD'] = '0'
            os.environ['SDL_ALSA_PCM_DEVICE'] = '0'
        
        # Apply extra environment variables
        for key, value in self.sdl_extra_env.items():
            if key.startswith('SDL_'):
                os.environ[key] = str(value)
        
        # Linux-specific optimizations
        if sys.platform.startswith('linux'):
            self._setup_linux_display_env()
        
        logging.info(f"SDL configured: {self.sdl_videodriver} driver, cursor hidden: {self.hide_cursor}")
    
    def _setup_linux_display_env(self):
        """Setup Linux-specific display environment"""
        # GPU memory split for Raspberry Pi
        if Path("/opt/vc/bin/vcgencmd").exists():
            try:
                import subprocess
                result = subprocess.run(["/opt/vc/bin/vcgencmd", "get_mem", "gpu"], 
                                      capture_output=True, text=True)
                if result.returncode == 0:
                    gpu_mem = result.stdout.strip()
                    logging.debug(f"GPU memory: {gpu_mem}")
            except:
                pass
        
        # Console blanking disable (prevent screen turn off)
        if self.disable_screensaver:
            try:
                for console in ['/sys/class/graphics/fbcon/cursor_blink',
                               '/sys/class/tty/tty0/active']:
                    console_path = Path(console)
                    if console_path.exists():
                        try:
                            with open(console_path, 'w') as f:
                                f.write('0')
                        except PermissionError:
                            pass  # Need root privileges
            except:
                pass
    
    def get_sdl_info(self) -> Dict[str, Any]:
        """Get comprehensive SDL configuration info"""
        return {
            'videodriver': self.sdl_videodriver,
            'audiodriver': self.sdl_audiodriver,
            'fbdev': self.sdl_fbdev,
            'nomouse': self.sdl_nomouse,
            'hide_cursor': self.hide_cursor,
            'disable_screensaver': self.disable_screensaver,
            'hardware_acceleration': self.hardware_acceleration,
            'vsync': self.vsync,
            'target_fps': self.target_fps,
            'extra_env': self.sdl_extra_env
        }
    
    def is_chat_whitelisted(self, chat_id: int) -> bool:
        """Check if chat ID is whitelisted"""
        return not self.whitelist_chats or chat_id in self.whitelist_chats
    
    def is_admin(self, chat_id: int) -> bool:
        """Check if chat ID is admin"""
        return chat_id in self.whitelist_admins
    
    def is_file_allowed(self, filename: str) -> bool:
        """Check if file type is allowed"""
        file_ext = Path(filename).suffix.lower()
        return file_ext in self.allowed_file_types
    
    def get_system_info(self) -> Dict[str, Any]:
        """Get system information for diagnostics"""
        info = {
            'platform': sys.platform,
            'python_version': sys.version,
            'framebuffer_exists': Path("/dev/fb0").exists(),
            'x11_display': os.environ.get('DISPLAY'),
            'user': os.environ.get('USER'),
            'home': os.environ.get('HOME'),
        }
        
        # Raspberry Pi detection
        try:
            if Path("/proc/device-tree/model").exists():
                with open("/proc/device-tree/model", "r") as f:
                    info['device_model'] = f.read().strip()
        except:
            pass
        
        # Memory info
        try:
            if Path("/proc/meminfo").exists():
                with open("/proc/meminfo", "r") as f:
                    for line in f:
                        if line.startswith("MemTotal:"):
                            info['total_memory'] = line.split()[1] + " kB"
                            break
        except:
            pass
        
        return info
    
    def validate_system(self) -> List[str]:
        """Validate system requirements and return warnings"""
        warnings = []
        
        # Check framebuffer permissions
        if Path("/dev/fb0").exists():
            try:
                with open("/dev/fb0", "rb") as f:
                    f.read(4)
            except PermissionError:
                warnings.append("No framebuffer permission - add user to video group")
        
        # Check disk space
        try:
            import shutil
            total, used, free = shutil.disk_usage(self.image_folder)
            free_mb = free // (1024 * 1024)
            if free_mb < 1000:  # Less than 1GB
                warnings.append(f"Low disk space: {free_mb}MB free")
        except:
            pass
        
        # Check memory
        try:
            with open("/proc/meminfo", "r") as f:
                for line in f:
                    if line.startswith("MemAvailable:"):
                        mem_kb = int(line.split()[1])
                        if mem_kb < 512 * 1024:  # Less than 512MB
                            warnings.append(f"Low memory: {mem_kb // 1024}MB available")
                        break
        except:
            pass
        
        return warnings


if __name__ == "__main__":
    # Test configuration loading and validation
    config = TeleFrameConfig.from_file("config.toml")
    
    print("✅ Configuration loaded successfully")
    print(f"📁 Image folder: {config.image_folder}")
    print(f"🎨 SDL driver: {config.sdl_videodriver}")
    print(f"👆 Hide cursor: {config.hide_cursor}")
    
    # System validation
    warnings = config.validate_system()
    if warnings:
        print("\n⚠️  System warnings:")
        for warning in warnings:
            print(f"   • {warning}")
    
    # Display system info
    print("\n📊 System info:")
    info = config.get_system_info()
    for key, value in info.items():
        print(f"   {key}: {value}")
