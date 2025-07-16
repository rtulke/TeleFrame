# config.py - Enhanced TeleFrame Configuration with Display Resolution and Time Methods
"""
Enhanced configuration management with display resolution and missing time methods
"""

import logging
import os
import re
import sys
import subprocess
from datetime import time, datetime, timedelta
from pathlib import Path
from typing import List, Optional, Dict, Any, Union, Tuple
import toml


class TeleFrameConfig:
    """Enhanced TeleFrame configuration class with display resolution and time methods"""
    
    def __init__(self, **kwargs):
        # Telegram Bot Configuration
        self.bot_token = kwargs.get("bot_token", "bot-disabled")
        self.whitelist_chats = kwargs.get("whitelist_chats", [])
        self.whitelist_admins = kwargs.get("whitelist_admins", [])
        
        # Bot Rate Limiting Configuration
        rate_limiting_config = kwargs.get("bot_rate_limiting", {})
        self.rate_limiting_enabled = rate_limiting_config.get("enabled", True)
        self.rate_limit_window = rate_limiting_config.get("window_seconds", 60)
        self.rate_limit_max_messages = rate_limiting_config.get("max_messages", 10)
        self.rate_limit_whitelist_exempt = rate_limiting_config.get("whitelist_exempt", True)
        self.rate_limit_admin_exempt = rate_limiting_config.get("admin_exempt", True)
        self.rate_limit_ban_duration = rate_limiting_config.get("ban_duration_minutes", 5)
        
        # Image Management
        self.image_folder = Path(kwargs.get("image_folder", "images"))
        self.image_count = kwargs.get("image_count", 30)
        self.auto_delete_images = kwargs.get("auto_delete_images", True)
        self.show_videos = kwargs.get("show_videos", True)
        
        # Display Settings
        self.fullscreen = kwargs.get("fullscreen", True)
        self.fade_time = kwargs.get("fade_time", 1500)
        self.interval = kwargs.get("interval", 10000)
        
        # ENHANCED: Display Resolution Configuration
        self.display_resolution = self._parse_display_resolution(kwargs)
        self.display_width = self.display_resolution[0]
        self.display_height = self.display_resolution[1]
        
        # Image Order Configuration
        self.image_order = self._parse_image_order(kwargs)
        
        # UI Settings
        self.show_sender = kwargs.get("show_sender", True)
        self.show_sender_time = kwargs.get("show_sender_time", 0)      # seconds, 0 = permanent
        
        self.show_caption = kwargs.get("show_caption", True)
        self.show_caption_time = kwargs.get("show_caption_time", 0)    # seconds, 0 = permanent
        
        self.show_order_indicator = kwargs.get("show_order_indicator", True)  
        self.crop_zoom_images = kwargs.get("crop_zoom_images", False)

        # Audio Settings
        self.play_sound_on_receive = kwargs.get("play_sound_on_receive", "sound1.mp3")
        self.play_video_audio = kwargs.get("play_video_audio", False)
        
        # System Settings
        self.toggle_monitor = kwargs.get("toggle_monitor", False)
        
        # Parse time settings (FIXED: Use proper attribute names to avoid conflicts)
        self.turn_on_time = self._parse_time(kwargs.get("turn_on_hour", "09:00"))
        self.turn_off_time = self._parse_time(kwargs.get("turn_off_hour", "22:00"))
        
        # Backward compatibility attributes
        self.turn_on_hour = self.turn_on_time.hour
        self.turn_on_minute = self.turn_on_time.minute
        self.turn_off_hour = self.turn_off_time.hour
        self.turn_off_minute = self.turn_off_time.minute
        
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
       
        # Validation of the text settings
        self._validate_ui_text_settings()

        # Error Handling
        self.max_errors_per_hour = kwargs.get("max_errors_per_hour", 100)
        self.enable_crash_recovery = kwargs.get("enable_crash_recovery", True)
        
        # Ensure directories exist
        self._ensure_directories()
        
        # Validate and apply settings
        self._validate()
        self._validate_time_config()
        self._validate_rate_limiting()
        self._validate_image_order()
        self._validate_display_resolution()
        self._apply_system_optimizations()
    
    # FIXED: Add missing time methods that monitor_control.py expects
    def get_turn_on_time(self) -> time:
        """Get turn on time as time object"""
        return self.turn_on_time
    
    def get_turn_off_time(self) -> time:
        """Get turn off time as time object"""
        return self.turn_off_time
    
    def format_time(self, time_obj: time) -> str:
        """Format time object as HH:MM string"""
        return time_obj.strftime("%H:%M")
    
    def update_schedule(self, turn_on_time: str, turn_off_time: str) -> bool:
        """Update monitor schedule with new times"""
        try:
            new_on_time = self._parse_time(turn_on_time)
            new_off_time = self._parse_time(turn_off_time)
            
            # Validate new times
            if new_on_time == new_off_time:
                raise ValueError("Turn on and turn off times cannot be the same")
            
            # Update time objects
            self.turn_on_time = new_on_time
            self.turn_off_time = new_off_time
            
            # Update backward compatibility values
            self.turn_on_hour = new_on_time.hour
            self.turn_on_minute = new_on_time.minute
            self.turn_off_hour = new_off_time.hour
            self.turn_off_minute = new_off_time.minute
            
            return True
            
        except ValueError as e:
            logging.error(f"Invalid schedule update: {e}")
            return False
    
    def _parse_display_resolution(self, kwargs: Dict[str, Any]) -> Tuple[int, int]:
        """Parse display resolution from various formats with auto-detection"""
        display_config = kwargs.get("display", {})
        
        # Check for resolution in display config
        if "resolution" in display_config:
            resolution = display_config["resolution"]
            logging.debug(f"Found display resolution in config: {resolution}")
            return self._parse_resolution_string(resolution)
        
        # Check for separate width/height
        if "width" in display_config and "height" in display_config:
            width = int(display_config["width"])
            height = int(display_config["height"])
            logging.debug(f"Found display width/height: {width}x{height}")
            return (width, height)
        
        # Legacy compatibility - top level resolution
        if "resolution" in kwargs:
            resolution = kwargs["resolution"]
            logging.debug(f"Found legacy resolution: {resolution}")
            return self._parse_resolution_string(resolution)
        
        # Auto-detect resolution
        logging.info("No display resolution specified, attempting auto-detection")
        return self._auto_detect_resolution()
    
    def _parse_resolution_string(self, resolution: str) -> Tuple[int, int]:
        """Parse resolution string in various formats"""
        resolution = resolution.strip().lower()
        
        # Handle preset names
        presets = {
            "auto": self._auto_detect_resolution(),
            "fhd": (1920, 1080),
            "fullhd": (1920, 1080),
            "1080p": (1920, 1080),
            "hd": (1280, 720),
            "720p": (1280, 720),
            "pi_touch": (800, 480),
            "pi_7inch": (800, 480),
            "xga": (1024, 768),
            "svga": (800, 600),
            "sxga": (1280, 1024),
            "uxga": (1600, 1200),
            "4k": (3840, 2160),
            "2160p": (3840, 2160),
        }
        
        if resolution in presets:
            if resolution == "auto":
                return presets[resolution]
            else:
                logging.info(f"Using preset resolution '{resolution}': {presets[resolution]}")
                return presets[resolution]
        
        # Parse WIDTHxHEIGHT format
        if 'x' in resolution:
            try:
                width_str, height_str = resolution.split('x', 1)
                width = int(width_str.strip())
                height = int(height_str.strip())
                
                if 320 <= width <= 7680 and 240 <= height <= 4320:
                    logging.info(f"Using custom resolution: {width}x{height}")
                    return (width, height)
                else:
                    raise ValueError(f"Resolution {width}x{height} outside valid range")
                    
            except ValueError as e:
                logging.error(f"Invalid resolution format: {resolution}")
                raise ValueError(f"Invalid resolution format: {resolution} - {e}")
        
        # Parse single dimension (assume 16:9)
        try:
            single_dim = int(resolution)
            if single_dim == 1080:
                return (1920, 1080)
            elif single_dim == 720:
                return (1280, 720)
            elif single_dim == 480:
                return (800, 480)
            else:
                # Calculate 16:9 aspect ratio
                height = single_dim
                width = int(height * 16 / 9)
                return (width, height)
        except ValueError:
            pass
        
        raise ValueError(f"Unsupported resolution format: {resolution}")
    
    def _auto_detect_resolution(self) -> Tuple[int, int]:
        """Auto-detect display resolution from system"""
        detected_resolution = None
        
        # Method 1: Try fbset for framebuffer
        if Path("/dev/fb0").exists():
            try:
                result = subprocess.run(
                    ["fbset", "-s"], 
                    capture_output=True, 
                    text=True, 
                    timeout=5
                )
                
                if result.returncode == 0:
                    for line in result.stdout.split('\n'):
                        if 'geometry' in line:
                            parts = line.split()
                            if len(parts) >= 3:
                                width = int(parts[1])
                                height = int(parts[2])
                                detected_resolution = (width, height)
                                logging.info(f"Detected framebuffer resolution: {width}x{height}")
                                break
            except (subprocess.TimeoutExpired, FileNotFoundError, ValueError):
                pass
        
        # Method 2: Try xrandr for X11
        if not detected_resolution and os.environ.get('DISPLAY'):
            try:
                result = subprocess.run(
                    ["xrandr", "--current"], 
                    capture_output=True, 
                    text=True, 
                    timeout=5
                )
                
                if result.returncode == 0:
                    for line in result.stdout.split('\n'):
                        if '*' in line and 'x' in line:
                            # Parse format like "1920x1080    59.93*+"
                            parts = line.split()
                            for part in parts:
                                if 'x' in part and part.replace('x', '').replace('.', '').isdigit():
                                    width_str, height_str = part.split('x')
                                    width = int(width_str)
                                    height = int(height_str)
                                    detected_resolution = (width, height)
                                    logging.info(f"Detected X11 resolution: {width}x{height}")
                                    break
                            if detected_resolution:
                                break
            except (subprocess.TimeoutExpired, FileNotFoundError, ValueError):
                pass
        
        # Method 3: Try vcgencmd for Raspberry Pi
        if not detected_resolution and Path("/opt/vc/bin/vcgencmd").exists():
            try:
                result = subprocess.run(
                    ["/opt/vc/bin/vcgencmd", "get_lcd_info"], 
                    capture_output=True, 
                    text=True, 
                    timeout=5
                )
                
                if result.returncode == 0:
                    # Parse output like "800 480 24"
                    parts = result.stdout.strip().split()
                    if len(parts) >= 2:
                        width = int(parts[0])
                        height = int(parts[1])
                        detected_resolution = (width, height)
                        logging.info(f"Detected Pi LCD resolution: {width}x{height}")
            except (subprocess.TimeoutExpired, FileNotFoundError, ValueError):
                pass
        
        # Default fallbacks
        if not detected_resolution:
            if self._is_raspberry_pi():
                if self._is_pi_touch_display():
                    detected_resolution = (800, 480)
                    logging.info("Detected Pi Touch Display: 800x480")
                else:
                    detected_resolution = (1920, 1080)
                    logging.info("Default Pi resolution: 1920x1080")
            else:
                detected_resolution = (1920, 1080)
                logging.info("Default desktop resolution: 1920x1080")
        
        return detected_resolution
    
    def _is_raspberry_pi(self) -> bool:
        """Check if running on Raspberry Pi"""
        try:
            if Path("/proc/device-tree/model").exists():
                with open("/proc/device-tree/model", "r") as f:
                    model = f.read().lower()
                return "raspberry pi" in model
        except:
            pass
        return False
    
    def _is_pi_touch_display(self) -> bool:
        """Check if Pi Touch Display is connected"""
        touch_indicators = [
            "/sys/class/backlight/rpi_backlight",
            "/sys/class/graphics/fb0/name",
        ]
        
        for indicator in touch_indicators:
            path = Path(indicator)
            if path.exists():
                try:
                    if "name" in indicator:
                        with open(path, 'r') as f:
                            content = f.read().lower()
                        if "bcm2708" in content or "vc4" in content:
                            return True
                    else:
                        return True
                except:
                    continue
        return False
    
    def _validate_display_resolution(self):
        """Validate display resolution configuration"""
        width, height = self.display_resolution
        
        if width < 320 or height < 240:
            raise ValueError(f"Resolution {width}x{height} too small (minimum: 320x240)")
        
        if width > 7680 or height > 4320:
            raise ValueError(f"Resolution {width}x{height} too large (maximum: 7680x4320)")
        
        aspect_ratio = width / height
        if aspect_ratio < 0.5 or aspect_ratio > 4.0:
            logging.warning(f"Unusual aspect ratio: {aspect_ratio:.2f} ({width}x{height})")
        
        logging.info(f"Display resolution validated: {width}x{height}")
    
    def get_display_resolution(self) -> Tuple[int, int]:
        """Get current display resolution"""
        return self.display_resolution
    
    def get_display_info(self) -> Dict[str, Any]:
        """Get comprehensive display information"""
        width, height = self.display_resolution
        aspect_ratio = width / height
        
        # Determine common aspect ratio name
        aspect_name = "Custom"
        if abs(aspect_ratio - 16/9) < 0.01:
            aspect_name = "16:9"
        elif abs(aspect_ratio - 4/3) < 0.01:
            aspect_name = "4:3"
        elif abs(aspect_ratio - 16/10) < 0.01:
            aspect_name = "16:10"
        elif abs(aspect_ratio - 5/4) < 0.01:
            aspect_name = "5:4"
        elif abs(aspect_ratio - 21/9) < 0.01:
            aspect_name = "21:9"
        
        # Calculate pixel density category
        pixel_count = width * height
        if pixel_count >= 3840 * 2160:
            density_category = "4K/UHD"
        elif pixel_count >= 1920 * 1080:
            density_category = "Full HD"
        elif pixel_count >= 1280 * 720:
            density_category = "HD"
        elif pixel_count >= 800 * 600:
            density_category = "SD"
        else:
            density_category = "Low"
        
        return {
            "width": width,
            "height": height,
            "resolution_string": f"{width}x{height}",
            "aspect_ratio": round(aspect_ratio, 2),
            "aspect_name": aspect_name,
            "pixel_count": pixel_count,
            "density_category": density_category,
            "fullscreen": self.fullscreen,
            "sdl_driver": self.sdl_videodriver,
            "hardware_acceleration": self.hardware_acceleration,
            "is_raspberry_pi": self._is_raspberry_pi(),
            "is_pi_touch": self._is_pi_touch_display(),
        }
    
    def set_display_resolution(self, width: int, height: int) -> bool:
        """Set display resolution with validation"""
        try:
            if width < 320 or height < 240:
                logging.error(f"Resolution {width}x{height} too small (minimum: 320x240)")
                return False
            
            if width > 7680 or height > 4320:
                logging.error(f"Resolution {width}x{height} too large (maximum: 7680x4320)")
                return False
            
            self.display_resolution = (width, height)
            self.display_width = width
            self.display_height = height
            
            logging.info(f"Display resolution updated: {width}x{height}")
            return True
            
        except Exception as e:
            logging.error(f"Failed to set display resolution: {e}")
            return False
    
    def optimize_for_resolution(self):
        """Optimize settings based on current resolution"""
        width, height = self.display_resolution
        pixel_count = width * height
        
        if pixel_count >= 3840 * 2160:  # 4K+
            logging.info("Optimizing for 4K resolution")
            if self.target_fps > 30:
                logging.info("Reducing target FPS for 4K display")
                self.target_fps = 30
        elif pixel_count >= 1920 * 1080:  # Full HD
            logging.info("Optimizing for Full HD resolution")
            if self.target_fps > 60:
                self.target_fps = 60
        elif pixel_count <= 800 * 600:  # Low resolution
            logging.info("Optimizing for low resolution display")
            if self.target_fps < 60:
                self.target_fps = 60
        
        if pixel_count >= 3840 * 2160 and self.fade_time < 2000:
            logging.info("Increasing fade time for high resolution")
            self.fade_time = 2000
        elif pixel_count <= 800 * 600 and self.fade_time > 1000:
            logging.info("Reducing fade time for low resolution")
            self.fade_time = 1000
    
    # Keep existing methods for image_order, rate_limiting, etc.
    def _parse_image_order(self, kwargs: Dict[str, Any]) -> str:
        """Parse image order with backwards compatibility"""
        if "image_order" in kwargs:
            return kwargs["image_order"]
        if "random_order" in kwargs:
            random_order = kwargs["random_order"]
            logging.warning("Using legacy random_order parameter")
            if isinstance(random_order, bool):
                return "random" if random_order else "sequential"
            elif isinstance(random_order, str):
                if random_order.lower() in ["true", "1", "yes", "on"]:
                    return "random"
                else:
                    return "sequential"
        return "random"
    
    def _validate_image_order(self):
        """Validate image_order configuration"""
        valid_orders = ["random", "latest", "oldest", "sequential"]
        if self.image_order not in valid_orders:
            logging.error(f"Invalid image_order: '{self.image_order}'. Valid: {valid_orders}")
            self.image_order = "random"
        logging.info(f"Image order configured: {self.image_order}")
    
    def get_image_order_mode(self) -> str:
        """Get current image order mode"""
        return self.image_order
    
    def set_image_order_mode(self, mode: str) -> bool:
        """Set image order mode with validation"""
        valid_orders = ["random", "latest", "oldest", "sequential"]
        if mode not in valid_orders:
            logging.error(f"Invalid image order mode: {mode}. Valid: {valid_orders}")
            return False
        self.image_order = mode
        logging.info(f"Image order changed to: {mode}")
        return True
    
    def get_image_order_description(self) -> str:
        """Get description of current image order mode"""
        descriptions = {
            "random": "Random order - images shuffled each cycle",
            "latest": "Latest first - newest images shown first", 
            "oldest": "Oldest first - oldest images shown first",
            "sequential": "Sequential order - images shown in storage order"
        }
        return descriptions.get(self.image_order, "Unknown order mode")
    
    def _validate_rate_limiting(self):
        """Validate rate limiting configuration"""
        if not isinstance(self.rate_limiting_enabled, bool):
            raise ValueError("rate_limiting_enabled must be boolean")
        if not 1 <= self.rate_limit_window <= 3600:
            raise ValueError("rate_limit_window must be between 1 and 3600 seconds")
        if not 1 <= self.rate_limit_max_messages <= 1000:
            raise ValueError("rate_limit_max_messages must be between 1 and 1000")
        if not isinstance(self.rate_limit_whitelist_exempt, bool):
            raise ValueError("rate_limit_whitelist_exempt must be boolean")
        if not isinstance(self.rate_limit_admin_exempt, bool):
            raise ValueError("rate_limit_admin_exempt must be boolean")
        if not 1 <= self.rate_limit_ban_duration <= 1440:
            raise ValueError("rate_limit_ban_duration must be between 1 and 1440 minutes")
    
    def get_rate_limit_config(self) -> Dict[str, Any]:
        """Get complete rate limiting configuration"""
        return {
            "enabled": self.rate_limiting_enabled,
            "window_seconds": self.rate_limit_window,
            "max_messages": self.rate_limit_max_messages,
            "whitelist_exempt": self.rate_limit_whitelist_exempt,
            "admin_exempt": self.rate_limit_admin_exempt,
            "ban_duration_minutes": self.rate_limit_ban_duration
        }
    
    def _parse_time(self, time_value: Union[str, int]) -> time:
        """Parse time from various formats"""
        if isinstance(time_value, int):
            if 0 <= time_value <= 23:
                return time(hour=time_value, minute=0)
            else:
                raise ValueError(f"Invalid hour: {time_value}")
        
        if isinstance(time_value, str):
            time_value = time_value.strip()
            if ':' in time_value:
                time_pattern = r'^(\d{1,2}):(\d{2})$'
                match = re.match(time_pattern, time_value)
                if match:
                    hour = int(match.group(1))
                    minute = int(match.group(2))
                    if 0 <= hour <= 23 and 0 <= minute <= 59:
                        return time(hour=hour, minute=minute)
                    else:
                        raise ValueError(f"Invalid time: {time_value}")
                else:
                    raise ValueError(f"Invalid time format: {time_value}")
            try:
                hour = int(time_value)
                if 0 <= hour <= 23:
                    return time(hour=hour, minute=0)
                else:
                    raise ValueError(f"Invalid hour: {hour}")
            except ValueError:
                raise ValueError(f"Invalid time format: {time_value}")
        
        raise ValueError(f"Unsupported time format: {type(time_value)}")
    
    def _validate_time_config(self):
        """Validate time configuration"""
        if self.turn_on_time == self.turn_off_time:
            raise ValueError("Turn on and turn off times cannot be the same")
    
    def _detect_best_driver(self) -> str:
        """Auto-detect the best SDL video driver"""
        if Path("/proc/device-tree/model").exists():
            try:
                with open("/proc/device-tree/model", "r") as f:
                    model = f.read().lower()
                if "raspberry pi" in model:
                    if Path("/dev/dri/card0").exists():
                        return "kmsdrm"
                    elif Path("/dev/fb0").exists():
                        return "fbcon"
            except:
                pass
        
        if Path("/dev/fb0").exists():
            return "fbcon"
        if os.environ.get("DISPLAY"):
            return "x11"
        return "dummy"
    
    def _ensure_directories(self):
        """Create necessary directories"""
        directories = [
            self.image_folder,
            Path("logs"),
            Path("sounds"),
            Path("cache"),
            Path("data")
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
    
    def _validate(self):
        """Validate configuration values"""
        if not 1 <= self.image_count <= 1000:
            raise ValueError("image_count must be between 1 and 1000")
        if not 0 <= self.fade_time <= 10000:
            raise ValueError("fade_time must be between 0 and 10000 ms")
        if not 1000 <= self.interval <= 300000:
            raise ValueError("interval must be between 1000 and 300000 ms")
        if not 10 <= self.target_fps <= 120:
            raise ValueError("target_fps must be between 10 and 120")
        
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if self.log_level.upper() not in valid_levels:
            raise ValueError(f"log_level must be one of: {valid_levels}")
        self.log_level = self.log_level.upper()
        
        if self.max_file_size > 500 * 1024 * 1024:
            logging.warning("Very large max_file_size - may cause memory issues")
        
        self.allowed_file_types = [
            ext.lower() if ext.startswith('.') else f'.{ext.lower()}' 
            for ext in self.allowed_file_types
        ]
        
        if self.bot_token not in ["bot-disabled", "YOUR_BOT_TOKEN_HERE"]:
            if not self._validate_bot_token(self.bot_token):
                logging.warning("Bot token format appears invalid")
    
    def _validate_bot_token(self, token: str) -> bool:
        """Validate bot token format"""
        parts = token.split(':')
        if len(parts) != 2:
            return False
        try:
            int(parts[0])
            return len(parts[1]) >= 35
        except ValueError:
            return False
    
    def _apply_system_optimizations(self):
        """Apply system-level optimizations"""
        if sys.platform.startswith('linux'):
            self._apply_linux_optimizations()
        
        # Apply resolution-specific optimizations
        self.optimize_for_resolution()
    
    def _apply_linux_optimizations(self):
        """Apply Linux-specific optimizations"""
        try:
            if os.geteuid() == 0:
                os.nice(-10)
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
        """Load configuration from TOML file"""
        config_file = Path(config_path)
        
        if not config_file.exists():
            logging.info(f"Config file {config_path} not found, creating default")
            default_config = cls()
            default_config.save_to_file(config_path)
            return default_config
        
        try:
            logging.info(f"Loading configuration from {config_path}")
            config_data = toml.load(config_file)
            
            logging.debug(f"Loaded config keys: {list(config_data.keys())}")
            if "display" in config_data:
                logging.debug(f"Display config: {config_data['display']}")
            
            config_instance = cls(**config_data)
            logging.info(f"Configuration loaded successfully")
            logging.info(f"Display resolution: {config_instance.display_width}x{config_instance.display_height}")
            logging.info(f"Image order: {config_instance.image_order}")
            
            return config_instance
            
        except toml.TomlDecodeError as e:
            logging.error(f"TOML syntax error in {config_path}: {e}")
            backup_path = config_file.with_suffix('.toml.broken')
            try:
                import shutil
                shutil.copy2(config_file, backup_path)
                logging.info(f"Broken config backed up to: {backup_path}")
            except Exception:
                pass
            return cls()
            
        except Exception as e:
            logging.error(f"Error loading config file {config_path}: {e}")
            return cls()
    
    def save_to_file(self, config_path: str = "config.toml"):
        """Save configuration to TOML file"""
        config_file = Path(config_path)
        
        if config_file.exists():
            backup_file = config_file.with_suffix('.toml.backup')
            try:
                import shutil
                shutil.copy2(config_file, backup_file)
                logging.debug(f"Config backup created: {backup_file}")
            except Exception as e:
                logging.warning(f"Could not create config backup: {e}")
        
        config_dict = self._to_dict()
        
        try:
            with open(config_file, 'w') as f:
                toml.dump(config_dict, f)
            logging.info(f"Configuration saved to {config_path}")
        except Exception as e:
            logging.error(f"Error saving config file: {e}")
    
    def _to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary"""
        config_dict = {
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
            'image_order': self.image_order,
            'show_sender': self.show_sender,
            'show_sender_time': self.show_sender_time,
            'show_caption': self.show_caption,
            'show_caption_time': self.show_caption_time,
            'show_order_indicator': self.show_order_indicator,
            'crop_zoom_images': self.crop_zoom_images,
            'hide_cursor': self.hide_cursor,
            'disable_screensaver': self.disable_screensaver,
            'toggle_monitor': self.toggle_monitor,
            'turn_on_hour': self.format_time(self.turn_on_time),
            'turn_off_hour': self.format_time(self.turn_off_time),
            'max_file_size': self.max_file_size,
            'allowed_file_types': self.allowed_file_types,
            'log_level': self.log_level,
        }
        
        if self.log_file:
            config_dict['log_file'] = str(self.log_file)
        
        # Display configuration
        config_dict['display'] = {
            'resolution': f"{self.display_width}x{self.display_height}",
            'width': self.display_width,
            'height': self.display_height,
        }
        
        # Bot Rate Limiting
        config_dict['bot_rate_limiting'] = self.get_rate_limit_config()
        
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
        """Setup SDL environment variables"""
        for key in list(os.environ.keys()):
            if key.startswith('SDL_'):
                del os.environ[key]
        
        os.environ['SDL_VIDEODRIVER'] = self.sdl_videodriver
        os.environ['SDL_AUDIODRIVER'] = self.sdl_audiodriver
        
        if not self.fullscreen:
            os.environ['SDL_VIDEO_WINDOW_POS'] = '0,0'
            os.environ['SDL_VIDEO_CENTERED'] = '0'
        
        if self.sdl_videodriver == 'fbcon':
            os.environ['SDL_FBDEV'] = self.sdl_fbdev
            os.environ['SDL_MOUSE_RELATIVE'] = '0'
        
        if self.sdl_nomouse or self.hide_cursor:
            os.environ['SDL_NOMOUSE'] = '1'
        
        if self.hide_cursor:
            os.environ['SDL_VIDEO_WINDOW_POS'] = '0,0'
            os.environ['SDL_VIDEO_CENTERED'] = '0'
        
        if self.disable_screensaver:
            os.environ['SDL_VIDEO_ALLOW_SCREENSAVER'] = '0'
        
        if self.hardware_acceleration:
            os.environ['SDL_RENDER_DRIVER'] = 'opengles2'
        
        if self.vsync:
            os.environ['SDL_RENDER_VSYNC'] = '1'
        
        if self.sdl_videodriver == 'kmsdrm':
            os.environ['SDL_KMSDRM_REQUIRE_DRM_MASTER'] = '0'
        
        if self.sdl_audiodriver == 'alsa':
            os.environ['SDL_ALSA_PCM_CARD'] = '0'
            os.environ['SDL_ALSA_PCM_DEVICE'] = '0'
        
        for key, value in self.sdl_extra_env.items():
            if key.startswith('SDL_'):
                os.environ[key] = str(value)
        
        if sys.platform.startswith('linux'):
            self._setup_linux_display_env()
        
        logging.info(f"SDL configured: {self.sdl_videodriver} driver, resolution: {self.display_width}x{self.display_height}")
    
    def _setup_linux_display_env(self):
        """Setup Linux-specific display environment"""
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
                            pass
            except:
                pass
    
    def get_system_info(self) -> Dict[str, Any]:
        """Get system information for diagnostics"""
        info = {
            'platform': sys.platform,
            'python_version': sys.version,
            'framebuffer_exists': Path("/dev/fb0").exists(),
            'x11_display': os.environ.get('DISPLAY'),
            'user': os.environ.get('USER'),
            'home': os.environ.get('HOME'),
            'display_resolution': f"{self.display_width}x{self.display_height}",
            'display_info': self.get_display_info(),
        }
        
        try:
            if Path("/proc/device-tree/model").exists():
                with open("/proc/device-tree/model", "r") as f:
                    info['device_model'] = f.read().strip()
        except:
            pass
        
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

    def _validate_ui_text_settings(self):
        """Validate UI text display settings"""
        import logging

        # Ensure display times are reasonable
        if self.show_sender_time < 0:
            self.logger.warning("show_sender_time cannot be negative, setting to 0")
            self.show_sender_time = 0
        
        if self.show_caption_time < 0:
            self.logger.warning("show_caption_time cannot be negative, setting to 0")
            self.show_caption_time = 0
        
        # Limit maximum display time to interval time
        max_display_time = self.interval / 1000  # Convert ms to seconds
        
        if self.show_sender_time > max_display_time and self.show_sender_time != 0:
            self.logger.warning(f"show_sender_time ({self.show_sender_time}s) > interval ({max_display_time}s), limiting to interval")
            self.show_sender_time = max_display_time
        
        if self.show_caption_time > max_display_time and self.show_caption_time != 0:
            self.logger.warning(f"show_caption_time ({self.show_caption_time}s) > interval ({max_display_time}s), limiting to interval")
            self.show_caption_time = max_display_time
        
        logging.debug(f"UI Text Settings: sender_time={self.show_sender_time}s, caption_time={self.show_caption_time}s, order_indicator={self.show_order_indicator}")


if __name__ == "__main__":
    # Test configuration loading and validation
    print("🧪 Testing TeleFrame Configuration with Display Resolution...")

    # Test 1: Normal loading
    config = TeleFrameConfig.from_file("config.toml")

    print("✅ Configuration loaded successfully")
    print(f"🖥️  Display resolution: {config.display_width}x{config.display_height}")
    print(f"⏰ Schedule: {config.format_time(config.get_turn_on_time())} - {config.format_time(config.get_turn_off_time())}")
    print(f"🔄 Image order: {config.image_order}")

    display_info = config.get_display_info()
    print(f"📊 Display info:")
    for key, value in display_info.items():
        print(f"   {key}: {value}")

    # Test 2: Resolution presets
    print(f"\n🎨 Available resolution presets:")
    presets = config.get_available_presets()
    for name, (width, height) in presets.items():
        print(f"   {name}: {width}x{height}")

    # Test 3: Resolution changes
    print(f"\n🔄 Testing resolution changes:")
    test_resolutions = ["1280x720", "fhd", "pi_touch"]
    for res in test_resolutions:
        success = config.set_display_resolution_preset(res)
        if success:
            print(f"  ✅ {res}: {config.display_width}x{config.display_height}")
        else:
            print(f"  ❌ {res}: Failed")

    # Test 4: Auto-detection
    print(f"\n🔍 Testing auto-detection:")
    auto_res = config._auto_detect_resolution()
    print(f"Auto-detected resolution: {auto_res[0]}x{auto_res[1]}")
    
    # Test 5: Legacy compatibility
    print(f"\n🔧 Testing legacy compatibility:")
    legacy_config_data = {
        "random_order": True,  # Old parameter
        "image_folder": "test_images"
    }
    legacy_config = TeleFrameConfig(**legacy_config_data)
    print(f"Legacy random_order=True → image_order={legacy_config.image_order}")
    
    legacy_config_data2 = {
        "random_order": False,  # Old parameter
    }
    legacy_config2 = TeleFrameConfig(**legacy_config_data2)
    print(f"Legacy random_order=False → image_order={legacy_config2.image_order}")
    
    # Test 6: Image order modes
    print(f"\n🔄 Testing image order modes:")
    test_modes = ["random", "latest", "oldest", "sequential", "invalid"]
    for mode in test_modes:
        success = config.set_image_order_mode(mode)
        if success:
            print(f"  ✅ {mode}: {config.get_image_order_description()}")
        else:
            print(f"  ❌ {mode}: Invalid mode")
    
    # Test 7: Rate limiting config
    print(f"\n⚡ Rate Limiting:")
    rate_config = config.get_rate_limit_config()
    for key, value in rate_config.items():
        print(f"  {key}: {value}")
    
    # Test 8: Time methods (monitor control compatibility)
    print(f"\n⏰ Time Methods:")
    print(f"  get_turn_on_time(): {config.get_turn_on_time()}")
    print(f"  get_turn_off_time(): {config.get_turn_off_time()}")
    print(f"  format_time(): {config.format_time(config.get_turn_on_time())}")
    
    # Test 9: Display resolution methods
    print(f"\n🖥️  Display Methods:")
    print(f"  get_display_resolution(): {config.get_display_resolution()}")
    print(f"  display_width: {config.display_width}")
    print(f"  display_height: {config.display_height}")
    
    # Test 10: System info
    print(f"\n🔧 System Info:")
    system_info = config.get_system_info()
    important_keys = ['platform', 'device_model', 'display_resolution', 'framebuffer_exists']
    for key in important_keys:
        if key in system_info:
            print(f"  {key}: {system_info[key]}")

    print(f"\n🎉 All tests completed!")
