# main.py - TeleFrame Python Robust Implementation
"""
TeleFrame - Digital Picture Frame with Telegram Bot
Robust implementation with proper error handling and process management
"""

import asyncio
import atexit
import logging
import os
import signal
import sys
import time
from pathlib import Path
from typing import Optional

# Load configuration first to get SDL settings
from config import TeleFrameConfig

# Load configuration
config = TeleFrameConfig.from_file("config.toml")

# Setup SDL environment from configuration
config.setup_sdl_environment()

import pygame
from image_manager import ImageManager
from slideshow import SlideshowDisplay
from telegram_bot import TeleFrameBot
from logger import setup_logger, setup_security_logger


class ProcessManager:
    """Handle process locking and cleanup"""
    
    def __init__(self, app_name: str = "teleframe"):
        self.app_name = app_name
        self.pid_file = Path(f"/tmp/{app_name}.pid")
        self.lock_file = Path(f"/tmp/{app_name}.lock")
        self.logger = logging.getLogger(f"{app_name}.process")
        
    def is_running(self) -> bool:
        """Check if another instance is running"""
        if not self.pid_file.exists():
            return False
            
        try:
            with open(self.pid_file, 'r') as f:
                pid = int(f.read().strip())
            
            # Check if process exists
            try:
                os.kill(pid, 0)  # Signal 0 = check if process exists
                return True
            except ProcessLookupError:
                # Process doesn't exist, clean up stale PID file
                self.pid_file.unlink(missing_ok=True)
                return False
                
        except (ValueError, FileNotFoundError):
            return False
    
    def create_lock(self) -> bool:
        """Create process lock"""
        if self.is_running():
            return False
            
        try:
            # Write current PID
            with open(self.pid_file, 'w') as f:
                f.write(str(os.getpid()))
            
            # Create lock file
            self.lock_file.touch()
            
            # Register cleanup on exit
            atexit.register(self.cleanup)
            
            self.logger.info(f"Process lock created: PID {os.getpid()}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error creating lock: {e}")
            return False
    
    def cleanup(self):
        """Clean up lock files"""
        try:
            self.pid_file.unlink(missing_ok=True)
            self.lock_file.unlink(missing_ok=True)
            self.logger.info("Process lock cleaned up")
        except Exception as e:
            self.logger.error(f"Error cleaning up lock: {e}")


class TeleFrame:
    """Main TeleFrame application class with robust error handling"""
    
    def __init__(self, config_path: str = "config.toml"):
        # Use already loaded config or load new one
        try:
            self.config = config
        except NameError:
            self.config = TeleFrameConfig.from_file(config_path)
            self.config.setup_sdl_environment()
        
        # Setup logging
        self.logger = setup_logger(self.config.log_level, self.config.log_file)
        self.security_logger = setup_security_logger(Path("logs/security.log"))
        
        # Process management
        self.process_manager = ProcessManager("teleframe")
        
        # Initialize components
        self.image_manager = None
        self.display = None
        self.bot = None
        
        # State
        self.running = False
        self.shutdown_requested = False
        
        # Setup signal handlers
        self._setup_signal_handlers()
        
        self.logger.info("TeleFrame initialized")
    
    def _setup_signal_handlers(self):
        """Setup graceful shutdown signal handlers"""
        def signal_handler(signum, frame):
            signal_name = signal.Signals(signum).name
            self.logger.info(f"Received signal {signal_name}")
            
            # Set shutdown flag immediately
            self.shutdown_requested = True
            
            # Schedule graceful shutdown (don't block signal handler)
            if self.running:
                # Create shutdown task without blocking
                def schedule_shutdown():
                    loop = None
                    try:
                        loop = asyncio.get_running_loop()
                    except RuntimeError:
                        try:
                            loop = asyncio.get_event_loop()
                        except RuntimeError:
                            pass
                    
                    if loop and not loop.is_closed():
                        loop.create_task(self.stop())
                
                schedule_shutdown()
        
        # Register signal handlers
        signal.signal(signal.SIGINT, signal_handler)   # Ctrl+C
        signal.signal(signal.SIGTERM, signal_handler)  # systemctl stop
        
        if hasattr(signal, 'SIGHUP'):  # Not available on Windows
            signal.signal(signal.SIGHUP, signal_handler)  # Reload config
    
    async def start(self):
        """Start TeleFrame application with robust error handling"""
        # Check if already running
        if self.process_manager.is_running():
            self.logger.error("❌ Another TeleFrame instance is already running!")
            self.logger.error("   Check with: ps aux | grep main.py")
            self.logger.error("   Kill with: pkill -f 'python.*main.py'")
            sys.exit(1)
        
        # Create process lock
        if not self.process_manager.create_lock():
            self.logger.error("❌ Could not create process lock")
            sys.exit(1)
        
        self.logger.info("🚀 Starting TeleFrame...")
        self.running = True
        
        try:
            # Initialize components with error handling
            await self._initialize_components()
            
            # Start main loop
            await self._main_loop()
            
        except KeyboardInterrupt:
            self.logger.info("🛑 Shutdown requested by user")
            
        except Exception as e:
            self.logger.error(f"💥 Fatal error in main loop: {e}")
            self.security_logger.error(f"Main loop crashed: {e}")
            raise
            
        finally:
            await self._cleanup()
    
    async def _initialize_components(self):
        """Initialize all components with error handling"""
        try:
            # Initialize image manager
            self.logger.info("📁 Initializing image manager...")
            self.image_manager = ImageManager(self.config)
            
            # Initialize display with retry logic
            self.logger.info("🖥️  Initializing display...")
            await self._init_display_with_retry()
            
            # Initialize bot if enabled
            if self.config.bot_token != "bot-disabled":
                self.logger.info("🤖 Initializing Telegram bot...")
                await self._init_bot_with_retry()
            else:
                self.logger.info("🤖 Telegram bot disabled")
            
        except Exception as e:
            self.logger.error(f"❌ Component initialization failed: {e}")
            raise
    
    async def _init_display_with_retry(self, max_retries: int = 3):
        """Initialize display with retry logic"""
        for attempt in range(max_retries):
            try:
                self.display = SlideshowDisplay(self.config, self.image_manager)
                await self.display.initialize()
                self.logger.info("✅ Display initialized successfully")
                return
                
            except Exception as e:
                self.logger.warning(f"Display init attempt {attempt + 1}/{max_retries} failed: {e}")
                
                if attempt == max_retries - 1:
                    self.logger.error("❌ All display initialization attempts failed")
                    self.logger.error("🔧 Troubleshooting tips:")
                    self.logger.error("   - Check framebuffer: ls -la /dev/fb*")
                    self.logger.error("   - Check video group: groups $USER")
                    self.logger.error("   - Try: sudo usermod -a -G video $USER")
                    raise
                
                await asyncio.sleep(2)  # Wait before retry
    
    async def _init_bot_with_retry(self, max_retries: int = 5):
        """Initialize bot with retry logic for conflicts"""
        for attempt in range(max_retries):
            try:
                self.bot = TeleFrameBot(self.config, self.image_manager)
                await self.bot.start()
                self.logger.info("✅ Telegram bot started successfully")
                return
                
            except Exception as e:
                error_msg = str(e).lower()
                
                if "conflict" in error_msg or "terminated by other" in error_msg:
                    self.logger.warning(f"🔄 Bot conflict detected (attempt {attempt + 1}/{max_retries})")
                    self.logger.warning("   Another bot instance may be running...")
                    
                    if attempt == max_retries - 1:
                        self.logger.error("❌ Bot startup failed: Multiple instances detected")
                        self.logger.error("🔧 Resolution steps:")
                        self.logger.error("   1. Stop other bot instances: pkill -f telegram")
                        self.logger.error("   2. Wait 30 seconds for Telegram API cleanup")
                        self.logger.error("   3. Restart TeleFrame")
                        raise RuntimeError("Bot conflict: Another instance running")
                    
                    # Exponential backoff for conflicts
                    wait_time = 10 * (2 ** attempt)
                    self.logger.info(f"   Waiting {wait_time}s before retry...")
                    await asyncio.sleep(wait_time)
                    
                elif "unauthorized" in error_msg or "token" in error_msg:
                    self.logger.error("❌ Bot authentication failed")
                    self.logger.error("🔧 Check your bot token in config.toml")
                    self.logger.error("   Get token from @BotFather on Telegram")
                    raise
                    
                else:
                    self.logger.error(f"❌ Bot startup failed: {e}")
                    if attempt == max_retries - 1:
                        raise
                    await asyncio.sleep(5)
    
    async def stop(self):
        """Graceful shutdown with proper timeout handling"""
        if not self.running:
            return
            
        self.logger.info("🛑 Stopping TeleFrame...")
        self.running = False
        self.shutdown_requested = True
        
        # Give components time to finish gracefully
        await self._cleanup_with_timeout()
    
    async def _cleanup_with_timeout(self):
        """Clean up all resources with timeout protection"""
        self.logger.info("🧹 Cleaning up resources...")
        
        cleanup_tasks = []
        
        # Stop bot with timeout
        if self.bot:
            cleanup_tasks.append(self._stop_bot_safely())
        
        # Clean up display with timeout  
        if self.display:
            cleanup_tasks.append(self._cleanup_display_safely())
        
        # Execute all cleanup tasks with timeout
        if cleanup_tasks:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*cleanup_tasks, return_exceptions=True),
                    timeout=10.0  # 10 second timeout
                )
            except asyncio.TimeoutError:
                self.logger.warning("⏰ Cleanup timeout - forcing shutdown")
            except Exception as e:
                self.logger.error(f"Error during cleanup: {e}")
        
        # Clean up pygame (synchronous)
        try:
            pygame.quit()
            self.logger.info("✅ pygame cleaned up")
        except Exception as e:
            self.logger.error(f"Error cleaning up pygame: {e}")
        
        # Clean up process lock
        self.process_manager.cleanup()
        
        self.logger.info("✅ Cleanup complete")
    
    async def _stop_bot_safely(self):
        """Stop bot with proper exception handling"""
        try:
            self.logger.info("🤖 Stopping bot gracefully...")
            await asyncio.wait_for(self.bot.stop(), timeout=5.0)
            self.logger.info("✅ Bot stopped")
        except asyncio.TimeoutError:
            self.logger.warning("⏰ Bot stop timeout - forcing shutdown")
        except Exception as e:
            self.logger.error(f"Error stopping bot: {e}")
    
    async def _cleanup_display_safely(self):
        """Clean up display with proper exception handling"""
        try:
            self.logger.info("🖥️  Cleaning up display...")
            # Display cleanup is synchronous
            self.display.cleanup()
            self.logger.info("✅ Display cleaned up")
        except Exception as e:
            self.logger.error(f"Error cleaning up display: {e}")
    
    async def _cleanup(self):
        """Legacy cleanup method - now calls new timeout version"""
        await self._cleanup_with_timeout()
    
    async def _main_loop(self):
        """Main application loop with error recovery"""
        self.logger.info("🎬 Starting main loop...")
        
        clock = pygame.time.Clock()
        last_image_change = 0
        error_count = 0
        max_errors = 10
        
        while self.running and not self.shutdown_requested:
            try:
                current_time = pygame.time.get_ticks()
                
                # Handle pygame events
                for event in pygame.event.get():
                    await self._handle_event(event)
                
                # Auto-advance slideshow
                if not self.display.is_paused and \
                   (current_time - last_image_change) >= self.config.interval:
                    await self.display.next_image()
                    last_image_change = current_time
                
                # Update display
                if self.display:
                    self.display.update()
                
                # Maintain framerate
                clock.tick(60)
                
                # Small async yield
                await asyncio.sleep(0.001)
                
                # Reset error count on successful iterations
                error_count = 0
                
            except KeyboardInterrupt:
                break
                
            except Exception as e:
                error_count += 1
                self.logger.error(f"Error in main loop iteration {error_count}: {e}")
                
                if error_count >= max_errors:
                    self.logger.error(f"❌ Too many errors ({max_errors}), shutting down")
                    break
                
                # Brief pause before retry
                await asyncio.sleep(0.1)
        
        self.logger.info("🏁 Main loop finished")
    
    async def _handle_event(self, event):
        """Handle pygame events with error handling"""
        try:
            if event.type == pygame.QUIT:
                self.shutdown_requested = True
                
            elif event.type == pygame.MOUSEBUTTONDOWN:
                await self._handle_touch(event.pos)
                
            elif event.type == pygame.KEYDOWN:
                await self._handle_keyboard(event.key)
                
        except Exception as e:
            self.logger.error(f"Error handling event {event.type}: {e}")
    
    async def _handle_touch(self, pos: tuple):
        """Handle touch input with error handling"""
        try:
            if not self.display:
                return
                
            screen_width = self.display.screen.get_width()
            x, y = pos
            
            if x < screen_width // 3:
                # Left third - previous image
                await self.display.previous_image()
            elif x > 2 * screen_width // 3:
                # Right third - next image
                await self.display.next_image()
            else:
                # Middle - pause/play
                self.display.toggle_pause()
                
        except Exception as e:
            self.logger.error(f"Error handling touch: {e}")
    
    async def _handle_keyboard(self, key):
        """Handle keyboard input with error handling"""
        try:
            if key == pygame.K_ESCAPE or key == pygame.K_q:
                self.shutdown_requested = True
            elif key == pygame.K_LEFT and self.display:
                await self.display.previous_image()
            elif key == pygame.K_RIGHT and self.display:
                await self.display.next_image()
            elif key == pygame.K_SPACE and self.display:
                self.display.toggle_pause()
                
        except Exception as e:
            self.logger.error(f"Error handling keyboard: {e}")


def check_prerequisites():
    """Check system prerequisites before starting"""
    logger = logging.getLogger("teleframe.precheck")
    
    # Check Python version
    if sys.version_info < (3, 10):
        logger.error("❌ Python 3.10+ required")
        return False
    
    # Check if config exists
    if not Path("config.toml").exists():
        logger.error("❌ config.toml not found")
        logger.error("   Run: python setup.py")
        return False
    
    # Check if framebuffer exists (warning only)
    if not Path("/dev/fb0").exists():
        logger.warning("⚠️  /dev/fb0 not found - desktop mode only")
    
    # Check required directories
    for directory in ["images", "logs"]:
        Path(directory).mkdir(exist_ok=True)
    
    return True


async def main():
    """Main entry point with comprehensive error handling"""
    # Setup basic logging first
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger = logging.getLogger("teleframe.main")
    teleframe = None
    
    try:
        # Check prerequisites
        if not check_prerequisites():
            sys.exit(1)
        
        # Create TeleFrame instance
        logger.info("🖼️  TeleFrame Python - Starting...")
        teleframe = TeleFrame()
        
        # Start application
        await teleframe.start()
        
    except KeyboardInterrupt:
        logger.info("🛑 Received interrupt signal")
        
    except SystemExit:
        # Don't log system exits (normal)
        pass
        
    except Exception as e:
        logger.error(f"💥 Fatal error: {e}")
        
    finally:
        # Ensure cleanup happens even if there are errors
        if teleframe:
            try:
                # Give cleanup extra time during shutdown
                await asyncio.wait_for(teleframe._cleanup_with_timeout(), timeout=15.0)
            except asyncio.TimeoutError:
                logger.warning("⏰ Final cleanup timeout")
            except Exception as e:
                logger.error(f"Error during final cleanup: {e}")
        
        logger.info("👋 TeleFrame shutdown complete")


if __name__ == "__main__":
    try:
        # Suppress asyncio debug warnings during shutdown
        import warnings
        warnings.filterwarnings("ignore", category=RuntimeWarning, message=".*was destroyed but it is pending.*")
        
        asyncio.run(main())
        
    except KeyboardInterrupt:
        print("\n🛑 Shutdown requested by user")
        
    except Exception as e:
        print(f"💥 Fatal error: {e}")
        sys.exit(1)
