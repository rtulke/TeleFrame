# monitor_control.py - Complete Monitor Control System
"""
Advanced monitor control with precise time scheduling and multi-platform support
Compatible with Raspberry Pi, modern Linux, X11, and embedded systems
"""

import asyncio
import logging
import subprocess
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Optional, Dict, Any


class MonitorController:
    """Complete monitor controller with multi-platform support"""
    
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Use enhanced time objects from config
        self.turn_on_time = config.get_turn_on_time()
        self.turn_off_time = config.get_turn_off_time()
        
        # Monitor state tracking
        self.monitor_state = True  # Assume monitor is on initially
        self.last_check = datetime.now()
        self.last_manual_override = None
        
        # Auto-detect best control method
        self.control_method = self._detect_control_method()
        
        # Initialize logging
        self.logger.info("🖥️  Monitor Controller initialized:")
        self.logger.info(f"   Control method: {self.control_method}")
        self.logger.info(f"   Schedule: ON at {config.format_time(self.turn_on_time)}, OFF at {config.format_time(self.turn_off_time)}")
        self.logger.info(f"   Auto-control: {'Enabled' if config.toggle_monitor else 'Disabled'}")
        
        # Test control method on startup
        self._test_control_method()
    
    def _detect_control_method(self) -> str:
        """Auto-detect the best available monitor control method"""
        
        # 1. Raspberry Pi vcgencmd (most reliable for Pi)
        if Path("/opt/vc/bin/vcgencmd").exists():
            self.logger.debug("Found vcgencmd - using Raspberry Pi control")
            return "vcgencmd"
        
        # 2. Modern DRM/KMS (Linux with modern graphics stack)
        if Path("/sys/class/drm").exists():
            drm_devices = list(Path("/sys/class/drm").glob("card*-*"))
            if drm_devices:
                self.logger.debug(f"Found DRM devices: {len(drm_devices)}")
                return "drm"
        
        # 3. X11 xset (if running X11)
        if self._command_exists("xset"):
            self.logger.debug("Found xset - using X11 DPMS control")
            return "xset"
        
        # 4. Backlight control (laptops, embedded displays)
        if Path("/sys/class/backlight").exists():
            backlight_devices = list(Path("/sys/class/backlight").iterdir())
            if backlight_devices:
                self.logger.debug(f"Found backlight devices: {len(backlight_devices)}")
                return "backlight"
        
        # 5. Framebuffer console blanking
        if Path("/sys/class/graphics/fbcon").exists():
            self.logger.debug("Found fbcon - using framebuffer blanking")
            return "fbcon"
        
        # 6. Generic DPMS via sysfs
        if Path("/sys/class/graphics").exists():
            self.logger.debug("Found graphics sysfs - using generic DPMS")
            return "dpms"
        
        # 7. No control method available
        self.logger.warning("No monitor control method detected")
        return "none"
    
    def _command_exists(self, command: str) -> bool:
        """Check if a command exists in PATH"""
        try:
            result = subprocess.run(
                ["which", command], 
                capture_output=True, 
                text=True
            )
            return result.returncode == 0
        except Exception:
            return False
    
    def _test_control_method(self):
        """Test the selected control method to ensure it works"""
        if self.control_method == "none":
            self.logger.warning("⚠️  No monitor control available - commands will be ignored")
            return
        
        try:
            # Test basic functionality (synchronous test)
            test_result = self._test_control_command_sync()
            if test_result:
                self.logger.info(f"✅ Monitor control test successful: {self.control_method}")
            else:
                self.logger.warning(f"⚠️  Monitor control test failed: {self.control_method}")
        except Exception as e:
            self.logger.error(f"❌ Monitor control test error: {e}")
    
    def _test_control_command_sync(self) -> bool:
        """Test if the control method works (synchronous version)"""
        try:
            if self.control_method == "vcgencmd":
                # Test vcgencmd without changing state
                result = subprocess.run(
                    ["/opt/vc/bin/vcgencmd", "display_power", "-1"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                return result.returncode == 0
                
            elif self.control_method == "xset":
                # Test xset without changing state
                result = subprocess.run(
                    ["xset", "q"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                return result.returncode == 0
                
            elif self.control_method in ["drm", "backlight", "fbcon", "dpms"]:
                # Test file system access
                return self._test_sysfs_access()
                
        except Exception as e:
            self.logger.debug(f"Control method test failed: {e}")
            return False
        
        return True
    
    async def _test_control_command(self) -> bool:
        """Test if the control method works (without actually changing state)"""
        try:
            if self.control_method == "vcgencmd":
                # Test vcgencmd without changing state
                result = await asyncio.create_subprocess_exec(
                    "/opt/vc/bin/vcgencmd", "display_power", "-1",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await result.communicate()
                return result.returncode == 0
                
            elif self.control_method == "xset":
                # Test xset without changing state
                result = await asyncio.create_subprocess_exec(
                    "xset", "q",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                return result.returncode == 0
                
            elif self.control_method in ["drm", "backlight", "fbcon", "dpms"]:
                # Test file system access
                return self._test_sysfs_access()
                
        except Exception as e:
            self.logger.debug(f"Control method test failed: {e}")
            return False
        
        return True
    
    def _test_sysfs_access(self) -> bool:
        """Test if we can access sysfs files for control"""
        test_paths = {
            "drm": ["/sys/class/drm"],
            "backlight": ["/sys/class/backlight"],
            "fbcon": ["/sys/class/graphics/fbcon"],
            "dpms": ["/sys/class/graphics"]
        }
        
        paths = test_paths.get(self.control_method, [])
        for path in paths:
            if Path(path).exists():
                return True
        return False
    
    async def check_schedule(self):
        """Check if monitor should be on/off based on schedule"""
        if not self.config.toggle_monitor:
            return
        
        # Skip if manual override is recent (within 10 minutes)
        if (self.last_manual_override and 
            (datetime.now() - self.last_manual_override).total_seconds() < 600):
            self.logger.debug("Skipping schedule check - manual override active")
            return
        
        current_time = datetime.now().time()
        should_be_on = self._should_monitor_be_on(current_time)
        
        if should_be_on != self.monitor_state:
            self.logger.info(f"⏰ Schedule trigger: Monitor should be {'ON' if should_be_on else 'OFF'}")
            
            if should_be_on:
                await self.turn_on()
            else:
                await self.turn_off()
    
    def _should_monitor_be_on(self, current: time) -> bool:
        """Determine if monitor should be on based on current time"""
        if self.turn_on_time <= self.turn_off_time:
            # Same day schedule (e.g., 09:10 - 22:34)
            return self.turn_on_time <= current <= self.turn_off_time
        else:
            # Cross-midnight schedule (e.g., 22:34 - 09:10)
            return current >= self.turn_on_time or current <= self.turn_off_time
    
    async def turn_on(self, manual: bool = False):
        """Turn monitor on"""
        if self.monitor_state and not manual:
            self.logger.debug("Monitor already on")
            return
        
        try:
            success = await self._execute_control_command(True)
            if success:
                self.monitor_state = True
                if manual:
                    self.last_manual_override = datetime.now()
                
                log_msg = f"🖥️  Monitor turned ON {'(manual)' if manual else '(scheduled)'}"
                self.logger.info(log_msg)
                
                # Security logging for manual overrides
                if manual:
                    security_logger = logging.getLogger("teleframe.security")
                    security_logger.info(f"Monitor manually turned ON")
            else:
                self.logger.warning("❌ Failed to turn monitor on")
                
        except Exception as e:
            self.logger.error(f"❌ Error turning monitor on: {e}")
    
    async def turn_off(self, manual: bool = False):
        """Turn monitor off"""
        if not self.monitor_state and not manual:
            self.logger.debug("Monitor already off")
            return
        
        try:
            success = await self._execute_control_command(False)
            if success:
                self.monitor_state = False
                if manual:
                    self.last_manual_override = datetime.now()
                
                log_msg = f"🖥️  Monitor turned OFF {'(manual)' if manual else '(scheduled)'}"
                self.logger.info(log_msg)
                
                # Security logging for manual overrides
                if manual:
                    security_logger = logging.getLogger("teleframe.security")
                    security_logger.info(f"Monitor manually turned OFF")
            else:
                self.logger.warning("❌ Failed to turn monitor off")
                
        except Exception as e:
            self.logger.error(f"❌ Error turning monitor off: {e}")
    
    async def _execute_control_command(self, turn_on: bool) -> bool:
        """Execute the appropriate control command for the detected method"""
        if self.control_method == "none":
            self.logger.debug("No control method - ignoring command")
            return False
        
        try:
            # Route to appropriate control method
            if self.control_method == "vcgencmd":
                return await self._control_vcgencmd(turn_on)
            elif self.control_method == "drm":
                return await self._control_drm(turn_on)
            elif self.control_method == "xset":
                return await self._control_xset(turn_on)
            elif self.control_method == "backlight":
                return await self._control_backlight(turn_on)
            elif self.control_method == "fbcon":
                return await self._control_fbcon(turn_on)
            elif self.control_method == "dpms":
                return await self._control_dpms(turn_on)
            else:
                self.logger.warning(f"Unknown control method: {self.control_method}")
                return False
                
        except Exception as e:
            self.logger.error(f"Monitor control command failed: {e}")
            return False
    
    async def _control_vcgencmd(self, turn_on: bool) -> bool:
        """Control via Raspberry Pi vcgencmd"""
        cmd = ["sudo", "/opt/vc/bin/vcgencmd", "display_power", "1" if turn_on else "0"]
        
        try:
            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await result.communicate()
            
            if result.returncode == 0:
                self.logger.debug(f"vcgencmd success: {stdout.decode().strip()}")
                return True
            else:
                self.logger.error(f"vcgencmd failed: {stderr.decode().strip()}")
                return False
                
        except Exception as e:
            self.logger.error(f"vcgencmd execution failed: {e}")
            return False
    
    async def _control_drm(self, turn_on: bool) -> bool:
        """Control via DRM/KMS connectors"""
        try:
            drm_path = Path("/sys/class/drm")
            
            # Find connected displays
            for connector in drm_path.glob("card*-*"):
                if not connector.is_dir():
                    continue
                
                status_file = connector / "status"
                enabled_file = connector / "enabled"
                dpms_file = connector / "dpms"
                
                try:
                    # Check if connector is connected
                    if status_file.exists():
                        with open(status_file, 'r') as f:
                            status = f.read().strip()
                        
                        if status == "connected":
                            # Try DPMS control first
                            if dpms_file.exists():
                                with open(dpms_file, 'w') as f:
                                    f.write("On" if turn_on else "Off")
                                self.logger.debug(f"DRM DPMS control: {connector.name}")
                                return True
                            
                            # Try enabled control
                            elif enabled_file.exists():
                                with open(enabled_file, 'w') as f:
                                    f.write("1" if turn_on else "0")
                                self.logger.debug(f"DRM enabled control: {connector.name}")
                                return True
                                
                except PermissionError:
                    self.logger.debug(f"No permission for DRM control: {connector.name}")
                    continue
                except Exception as e:
                    self.logger.debug(f"DRM control error for {connector.name}: {e}")
                    continue
            
            self.logger.warning("No accessible DRM connectors found")
            return False
            
        except Exception as e:
            self.logger.error(f"DRM control error: {e}")
            return False
    
    async def _control_xset(self, turn_on: bool) -> bool:
        """Control via X11 xset DPMS"""
        if turn_on:
            cmd = ["xset", "dpms", "force", "on"]
        else:
            cmd = ["xset", "dpms", "force", "off"]
        
        try:
            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await result.communicate()
            
            if result.returncode == 0:
                self.logger.debug(f"xset DPMS success")
                return True
            else:
                self.logger.error(f"xset DPMS failed: {stderr.decode().strip()}")
                return False
                
        except Exception as e:
            self.logger.error(f"xset execution failed: {e}")
            return False
    
    async def _control_backlight(self, turn_on: bool) -> bool:
        """Control via backlight brightness"""
        try:
            backlight_path = Path("/sys/class/backlight")
            
            for device in backlight_path.iterdir():
                if not device.is_dir():
                    continue
                
                brightness_file = device / "brightness"
                max_brightness_file = device / "max_brightness"
                
                if brightness_file.exists() and max_brightness_file.exists():
                    try:
                        if turn_on:
                            # Read max brightness and set to full
                            with open(max_brightness_file, 'r') as f:
                                max_brightness = int(f.read().strip())
                            
                            with open(brightness_file, 'w') as f:
                                f.write(str(max_brightness))
                                
                            self.logger.debug(f"Backlight ON: {device.name} -> {max_brightness}")
                        else:
                            # Set to minimum brightness (0)
                            with open(brightness_file, 'w') as f:
                                f.write("0")
                                
                            self.logger.debug(f"Backlight OFF: {device.name}")
                        
                        return True
                        
                    except PermissionError:
                        self.logger.debug(f"No permission for backlight: {device.name}")
                        continue
                    except Exception as e:
                        self.logger.debug(f"Backlight control error for {device.name}: {e}")
                        continue
            
            self.logger.warning("No accessible backlight devices found")
            return False
            
        except Exception as e:
            self.logger.error(f"Backlight control error: {e}")
            return False
    
    async def _control_fbcon(self, turn_on: bool) -> bool:
        """Control via framebuffer console blanking"""
        try:
            # Various console blanking control files
            blank_files = [
                Path("/sys/class/graphics/fbcon/cursor_blink"),
                Path("/sys/class/tty/tty0/active"),
                Path("/sys/module/kernel/parameters/consoleblank"),
                Path("/sys/class/graphics/fb0/blank")
            ]
            
            for blank_file in blank_files:
                if blank_file.exists():
                    try:
                        with open(blank_file, 'w') as f:
                            if "blank" in str(blank_file) and "cursor" not in str(blank_file):
                                # For actual blank files, 0=unblank, 1=blank
                                f.write("0" if turn_on else "1")
                            else:
                                # For cursor/active files, 1=active, 0=inactive
                                f.write("1" if turn_on else "0")
                        
                        self.logger.debug(f"FB console control: {blank_file.name}")
                        return True
                        
                    except PermissionError:
                        self.logger.debug(f"No permission for fbcon: {blank_file}")
                        continue
                    except Exception as e:
                        self.logger.debug(f"FB console error for {blank_file}: {e}")
                        continue
            
            self.logger.warning("No accessible framebuffer console controls found")
            return False
            
        except Exception as e:
            self.logger.error(f"FB console control error: {e}")
            return False
    
    async def _control_dpms(self, turn_on: bool) -> bool:
        """Control via generic DPMS"""
        try:
            # Various DPMS control files
            dpms_files = [
                Path("/sys/class/graphics/fb0/blank"),
                Path("/sys/class/drm/card0/card0-HDMI-A-1/dpms"),
                Path("/sys/class/drm/card0/card0-VGA-1/dpms"),
                Path("/sys/class/drm/card0/card0-DVI-D-1/dpms")
            ]
            
            for dpms_file in dpms_files:
                if dpms_file.exists():
                    try:
                        with open(dpms_file, 'w') as f:
                            if "blank" in str(dpms_file):
                                # Blank files: 0=unblank, 1=blank
                                f.write("0" if turn_on else "1")
                            else:
                                # DPMS files: On/Off
                                f.write("On" if turn_on else "Off")
                        
                        self.logger.debug(f"DPMS control: {dpms_file.name}")
                        return True
                        
                    except PermissionError:
                        self.logger.debug(f"No permission for DPMS: {dpms_file}")
                        continue
                    except Exception as e:
                        self.logger.debug(f"DPMS error for {dpms_file}: {e}")
                        continue
            
            self.logger.warning("No accessible DPMS controls found")
            return False
            
        except Exception as e:
            self.logger.error(f"DPMS control error: {e}")
            return False
    
    def update_schedule(self, turn_on_time: str, turn_off_time: str) -> bool:
        """Update monitor schedule with new times"""
        try:
            # Update config first
            success = self.config.update_schedule(turn_on_time, turn_off_time)
            if success:
                # Update local times
                self.turn_on_time = self.config.get_turn_on_time()
                self.turn_off_time = self.config.get_turn_off_time()
                
                self.logger.info(f"📅 Schedule updated: ON at {self.config.format_time(self.turn_on_time)}, OFF at {self.config.format_time(self.turn_off_time)}")
                
                # Security logging
                security_logger = logging.getLogger("teleframe.security")
                security_logger.info(f"Schedule updated: {turn_on_time} - {turn_off_time}")
                
                return True
            else:
                self.logger.error("Failed to update config schedule")
                return False
                
        except Exception as e:
            self.logger.error(f"Error updating schedule: {e}")
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive monitor status"""
        current_time = datetime.now().time()
        
        return {
            "enabled": self.config.toggle_monitor,
            "state": "ON" if self.monitor_state else "OFF",
            "control_method": self.control_method,
            "turn_on_time": self.config.format_time(self.turn_on_time),
            "turn_off_time": self.config.format_time(self.turn_off_time),
            "current_time": current_time.strftime("%H:%M"),
            "should_be_on": self._should_monitor_be_on(current_time) if self.config.toggle_monitor else None,
            "next_change": self._get_next_change_time(),
            "last_manual_override": self.last_manual_override.strftime("%H:%M") if self.last_manual_override else None
        }
    
    def _get_next_change_time(self) -> str:
        """Calculate next monitor state change time"""
        if not self.config.toggle_monitor:
            return "Disabled"
        
        now = datetime.now()
        current_time = now.time()
        
        # Calculate next change
        if self.monitor_state:  # Currently on, find next off time
            if current_time < self.turn_off_time:
                next_change = datetime.combine(now.date(), self.turn_off_time)
            else:
                # Next day
                next_change = datetime.combine(now.date() + timedelta(days=1), self.turn_off_time)
        else:  # Currently off, find next on time
            if current_time < self.turn_on_time:
                next_change = datetime.combine(now.date(), self.turn_on_time)
            else:
                # Next day
                next_change = datetime.combine(now.date() + timedelta(days=1), self.turn_on_time)
        
        # Calculate time until next change
        time_until = next_change - now
        hours, remainder = divmod(time_until.total_seconds(), 3600)
        minutes, _ = divmod(remainder, 60)
        
        return f"{next_change.strftime('%H:%M')} (in {int(hours)}h {int(minutes)}m)"
    
    def get_system_info(self) -> Dict[str, Any]:
        """Get comprehensive system information for diagnostics"""
        info = {
            "control_method": self.control_method,
            "available_methods": []
        }
        
        # Check all available methods
        methods = [
            ("vcgencmd", Path("/opt/vc/bin/vcgencmd").exists()),
            ("drm", Path("/sys/class/drm").exists()),
            ("xset", self._command_exists("xset")),
            ("backlight", Path("/sys/class/backlight").exists()),
            ("fbcon", Path("/sys/class/graphics/fbcon").exists()),
            ("dpms", Path("/sys/class/graphics").exists())
        ]
        
        for method, available in methods:
            if available:
                info["available_methods"].append(method)
        
        # Device information
        try:
            if Path("/proc/device-tree/model").exists():
                with open("/proc/device-tree/model", "r") as f:
                    info["device_model"] = f.read().strip()
        except:
            pass
        
        # Hardware capabilities
        info["hardware"] = {
            "raspberry_pi": Path("/opt/vc/bin/vcgencmd").exists(),
            "framebuffer": Path("/dev/fb0").exists(),
            "x11_display": bool(subprocess.run(["echo", "$DISPLAY"], capture_output=True).stdout.strip()),
            "drm_devices": len(list(Path("/sys/class/drm").glob("card*"))) if Path("/sys/class/drm").exists() else 0,
            "backlight_devices": len(list(Path("/sys/class/backlight").iterdir())) if Path("/sys/class/backlight").exists() else 0
        }
        
        return info


if __name__ == "__main__":
    """Test and demonstration of monitor controller"""
    import sys
    
    # Add parent directory to path for imports
    sys.path.insert(0, str(Path(__file__).parent))
    
    try:
        from config import TeleFrameConfig
    except ImportError:
        print("❌ Could not import TeleFrameConfig")
        print("   Make sure config.py is in the same directory")
        sys.exit(1)
    
    async def test_monitor_controller():
        """Test the monitor controller functionality"""
        print("🖥️  TeleFrame Monitor Controller Test")
        print("=" * 50)
        
        # Load config
        try:
            config = TeleFrameConfig.from_file("config.toml")
        except Exception as e:
            print(f"❌ Error loading config: {e}")
            return
        
        # Create controller
        controller = MonitorController(config)
        
        # Show status
        print("\n📊 Current Status:")
        status = controller.get_status()
        for key, value in status.items():
            print(f"  {key}: {value}")
        
        # Show system info
        print("\n🔧 System Information:")
        info = controller.get_system_info()
        for key, value in info.items():
            if isinstance(value, dict):
                print(f"  {key}:")
                for subkey, subvalue in value.items():
                    print(f"    {subkey}: {subvalue}")
            else:
                print(f"  {key}: {value}")
        
        # Test schedule logic
        print("\n🕒 Schedule Logic Test:")
        if config.toggle_monitor:
            test_times = ["08:00", "09:10", "12:00", "22:34", "23:00"]
            for test_time in test_times:
                hour, minute = map(int, test_time.split(':'))
                test_time_obj = time(hour, minute)
                should_be_on = controller._should_monitor_be_on(test_time_obj)
                print(f"  {test_time} → {'ON' if should_be_on else 'OFF'}")
        else:
            print("  Auto-control disabled")
        
        # Interactive test (optional)
        print("\n🔬 Interactive Test:")
        print("  Commands: 'on', 'off', 'status', 'schedule', 'quit'")
        
        while True:
            try:
                command = input("\nEnter command: ").strip().lower()
                
                if command == 'quit' or command == 'q':
                    break
                elif command == 'on':
                    await controller.turn_on(manual=True)
                    print("✅ Monitor turned ON")
                elif command == 'off':
                    await controller.turn_off(manual=True)
                    print("✅ Monitor turned OFF")
                elif command == 'status':
                    status = controller.get_status()
                    print(f"Monitor: {status['state']}")
                elif command == 'schedule':
                    await controller.check_schedule()
                    print("✅ Schedule check completed")
                elif command == 'help':
                    print("Available commands: on, off, status, schedule, quit")
                else:
                    print("❓ Unknown command. Type 'help' for available commands.")
                    
            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"❌ Error: {e}")
        
        print("\n✅ Test completed")
    
    # Run the test
    try:
        asyncio.run(test_monitor_controller())
    except KeyboardInterrupt:
        print("\n👋 Test interrupted by user")
    except Exception as e:
        print(f"❌ Test failed: {e}")
        sys.exit(1)
