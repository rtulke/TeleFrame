# slideshow.py - FIXED Import Order
"""
Fixed slideshow display with pygame import AFTER SDL setup
This matches the working framebuffer_test.py approach exactly
"""

import asyncio
import logging
import os
import random
from pathlib import Path
from typing import Optional, Tuple

# DON'T import pygame here - import it AFTER SDL setup!


class SlideshowDisplay:
    """Handles slideshow display with FIXED pygame import timing"""
    
    def __init__(self, config, image_manager=None):
        self.config = config
        self.image_manager = image_manager
        self.logger = logging.getLogger(__name__)
        
        # Display state
        self.screen = None
        self.current_image_index = 0
        self.is_paused = False
        self.current_surface = None
        self.fade_surface = None
        
        # Animation state
        self.fade_progress = 0.0
        self.fade_duration = config.fade_time
        self.fade_start_time = 0
        self.is_fading = False
        
        # Image sequence for random order
        self.image_sequence = []
        self.sequence_index = 0
        
        # Colors (will be set after pygame import)
        self.black = None
        self.white = None
        
        # pygame and PIL modules (imported later)
        self.pygame = None
        self.PILImage = None
        
        self.logger.info("SlideshowDisplay initialized (pygame not imported yet)")
    
    async def initialize(self):
        """Initialize pygame and display - IMPORT pygame HERE, not at module level"""
        try:
            self.logger.info("🔧 Setting up SDL environment BEFORE pygame import...")
            
            # STEP 1: Clear ALL existing SDL environment (exactly like working test)
            for key in list(os.environ.keys()):
                if key.startswith('SDL_'):
                    del os.environ[key]
                    self.logger.debug(f"Cleared {key}")
                    
            # STEP 2: Check system capabilities
            fb_device = Path("/dev/fb0")
            dri_device = Path("/dev/dri/card0")
            
            self.logger.info(f"📺 System check:")
            self.logger.info(f"   Framebuffer: {fb_device.exists()}")
            self.logger.info(f"   DRI/KMS: {dri_device.exists()}")
            
            # STEP 3: Try display modes in order of preference
            display_success = False
            final_driver = None
            
            # Mode 1: KMSDRM (exactly like working framebuffer_test.py)
            if not display_success and dri_device.exists():
                try:
                    self.logger.info("🎯 Attempting KMSDRM mode...")
                    
                    # Set environment exactly like working test
                    os.environ['SDL_VIDEODRIVER'] = 'kmsdrm'
                    os.environ['SDL_AUDIODRIVER'] = 'dummy'
                    
                    self.logger.debug("SDL environment set for KMSDRM")
                    
                    # CRITICAL: Import pygame AFTER setting environment
                    import pygame
                    self.pygame = pygame
                    
                    # Import PIL here too
                    from PIL import Image as PILImage
                    self.PILImage = PILImage
                    
                    self.logger.info(f"✅ pygame imported AFTER SDL setup: {pygame.version.ver}")
                    
                    # Force complete reinitialization (like working test)
                    pygame.quit()  # Clean slate
                    pygame.display.quit()  # Extra cleanup
                    pygame.display.init()  # Fresh start
                    
                    # Check what driver we actually got
                    detected_driver = pygame.display.get_driver()
                    self.logger.info(f"📺 Detected driver: {detected_driver}")
                    
                    if detected_driver.upper() == 'KMSDRM':
                        # Try to create display
                        if self.config.fullscreen:
                            self.screen = pygame.display.set_mode((1920, 1080), pygame.FULLSCREEN)
                        else:
                            self.screen = pygame.display.set_mode((1920, 1080))
                        
                        display_success = True
                        final_driver = 'KMSDRM'
                        self.logger.info(f"✅ KMSDRM SUCCESS: {self.screen.get_size()}")
                        
                    else:
                        self.logger.warning(f"❌ Expected KMSDRM, got: {detected_driver}")
                        
                except Exception as e:
                    self.logger.warning(f"KMSDRM mode failed: {e}")
                    import traceback
                    self.logger.debug(f"KMSDRM traceback: {traceback.format_exc()}")
            
            # Mode 2: Legacy Framebuffer
            if not display_success and fb_device.exists():
                try:
                    self.logger.info("🔄 Attempting legacy framebuffer mode...")
                    
                    # Clear and set FB environment
                    for key in list(os.environ.keys()):
                        if key.startswith('SDL_'):
                            del os.environ[key]
                    
                    os.environ['SDL_VIDEODRIVER'] = 'fbcon'
                    os.environ['SDL_FBDEV'] = '/dev/fb0'
                    os.environ['SDL_AUDIODRIVER'] = 'dummy'
                    
                    # Import pygame if not already imported
                    if not self.pygame:
                        import pygame
                        self.pygame = pygame
                        from PIL import Image as PILImage
                        self.PILImage = PILImage
                    
                    pygame.quit()
                    pygame.display.quit()
                    pygame.display.init()
                    
                    detected_driver = pygame.display.get_driver()
                    self.logger.info(f"📺 FB driver: {detected_driver}")
                    
                    if self.config.fullscreen:
                        self.screen = pygame.display.set_mode((1920, 1080), pygame.FULLSCREEN)
                    else:
                        self.screen = pygame.display.set_mode((800, 480))
                    
                    display_success = True
                    final_driver = 'FBCON'
                    self.logger.info(f"✅ Legacy framebuffer SUCCESS: {self.screen.get_size()}")
                    
                except Exception as e:
                    self.logger.warning(f"Legacy framebuffer mode failed: {e}")
            
            # Mode 3: X11 (development fallback)
            if not display_success:
                try:
                    self.logger.info("🔄 Attempting X11 mode...")
                    
                    for key in list(os.environ.keys()):
                        if key.startswith('SDL_'):
                            del os.environ[key]
                    
                    os.environ['SDL_VIDEODRIVER'] = 'x11'
                    os.environ['SDL_AUDIODRIVER'] = 'pulse'
                    
                    if not self.pygame:
                        import pygame
                        self.pygame = pygame
                        from PIL import Image as PILImage
                        self.PILImage = PILImage
                    
                    pygame.quit()
                    pygame.display.quit()
                    pygame.display.init()
                    
                    if os.environ.get('DISPLAY'):
                        if self.config.fullscreen:
                            self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
                        else:
                            self.screen = pygame.display.set_mode((800, 600))
                        
                        display_success = True
                        final_driver = 'X11'
                        self.logger.info(f"✅ X11 SUCCESS: {self.screen.get_size()}")
                    else:
                        self.logger.warning("No DISPLAY variable for X11")
                        
                except Exception as e:
                    self.logger.warning(f"X11 mode failed: {e}")
            
            # Mode 4: Dummy (headless fallback)
            if not display_success:
                try:
                    self.logger.info("🔄 Attempting dummy mode...")
                    
                    for key in list(os.environ.keys()):
                        if key.startswith('SDL_'):
                            del os.environ[key]
                    
                    os.environ['SDL_VIDEODRIVER'] = 'dummy'
                    os.environ['SDL_AUDIODRIVER'] = 'dummy'
                    
                    if not self.pygame:
                        import pygame
                        self.pygame = pygame
                        from PIL import Image as PILImage
                        self.PILImage = PILImage
                    
                    pygame.quit()
                    pygame.display.quit()
                    pygame.display.init()
                    
                    self.screen = pygame.display.set_mode((800, 480))
                    display_success = True
                    final_driver = 'DUMMY'
                    self.logger.info(f"✅ Dummy mode SUCCESS (headless): {self.screen.get_size()}")
                    
                except Exception as e:
                    self.logger.error(f"Dummy mode failed: {e}")
            
            if not display_success:
                raise Exception("All display modes failed")
            
            # STEP 4: Common initialization (after successful pygame import)
            # Set colors now that pygame is imported
            self.black = (0, 0, 0)
            self.white = (255, 255, 255)
            
            # Hide cursor completely
            self.pygame.mouse.set_visible(False)
            self.pygame.display.set_caption("TeleFrame")
            
            # Disable screensaver and limit events
            self.pygame.event.set_allowed([
                self.pygame.QUIT, 
                self.pygame.KEYDOWN, 
                self.pygame.MOUSEBUTTONDOWN
            ])
            
            # Initialize font
            self.pygame.font.init()
            try:
                self.font_large = self.pygame.font.Font(None, 48)
                self.font_medium = self.pygame.font.Font(None, 32)
                self.font_small = self.pygame.font.Font(None, 24)
            except Exception as e:
                self.logger.warning(f"Font initialization failed: {e}")
                self.font_large = self.font_medium = self.font_small = self.pygame.font.Font(None, 36)
            
            self.screen_size = self.screen.get_size()
            
            # Final success message
            self.logger.info(f"🎉 Display initialized successfully!")
            self.logger.info(f"   Resolution: {self.screen_size}")
            self.logger.info(f"   Driver: {final_driver}")
            self.logger.info(f"   pygame version: {self.pygame.version.ver}")
            self.logger.info(f"   SDL version: {self.pygame.version.SDL}")
            self.logger.info(f"   Fullscreen: {self.config.fullscreen}")
            
            # Show initial screen
            self._show_startup_screen()
            
            # Generate initial image sequence
            self._update_image_sequence()
            
        except Exception as e:
            self.logger.error(f"❌ Error initializing display: {e}")
            self.logger.error("🔧 Debug info:")
            if self.pygame:
                self.logger.error(f"   pygame version: {self.pygame.version.ver}")
                try:
                    self.logger.error(f"   Current driver: {self.pygame.display.get_driver()}")
                except:
                    pass
            raise
    
    def _show_startup_screen(self):
        """Show startup screen with TeleFrame logo"""
        if not self.pygame or not self.screen:
            return
            
        try:
            self.screen.fill(self.black)
            
            # Render TeleFrame text
            title = self.font_large.render("Oma Ilonas TeleFrame", True, self.white)
            title_rect = title.get_rect(center=(self.screen_size[0] // 2, 
                                                self.screen_size[1] // 2 - 50))
            self.screen.blit(title, title_rect)
            
            # Status text
            if self.image_manager and self.image_manager.get_image_count() > 0:
                status_text = f"{self.image_manager.get_image_count()} images loaded"
            else:
                status_text = "Waiting for images..."
            
            status = self.font_medium.render(status_text, True, self.white)
            status_rect = status.get_rect(center=(self.screen_size[0] // 2,
                                                self.screen_size[1] // 2 + 20))
            self.screen.blit(status, status_rect)
            
            # Display driver info
            driver_info = f"Driver: {self.pygame.display.get_driver()}"
            driver_text = self.font_small.render(driver_info, True, self.white)
            driver_rect = driver_text.get_rect(center=(self.screen_size[0] // 2,
                                                     self.screen_size[1] // 2 + 60))
            self.screen.blit(driver_text, driver_rect)
            
            self.pygame.display.flip()
            
        except Exception as e:
            self.logger.error(f"Error showing startup screen: {e}")
    
    def _update_image_sequence(self):
        """Update the image display sequence"""
        if not self.image_manager:
            return
        
        image_count = self.image_manager.get_image_count()
        if image_count == 0:
            self.image_sequence = []
            return
        
        if self.config.random_order:
            self.image_sequence = list(range(image_count))
            random.shuffle(self.image_sequence)
        else:
            self.image_sequence = list(range(image_count))
        
        self.sequence_index = 0
        self.logger.debug(f"Updated image sequence: {len(self.image_sequence)} images")
    
    def _load_and_scale_image(self, image_path: Path) -> Optional:
        """Load and scale image to fit screen"""
        if not self.pygame or not self.PILImage:
            self.logger.error("pygame/PIL not initialized")
            return None
            
        try:
            # Load with PIL for better format support
            pil_image = self.PILImage.open(image_path)
            
            # Convert to RGB if necessary
            if pil_image.mode != 'RGB':
                pil_image = pil_image.convert('RGB')
            
            # Calculate scaling
            img_size = pil_image.size
            scale_factor = self._calculate_scale_factor(img_size, self.screen_size)
            
            if self.config.crop_zoom_images:
                # Scale to fill screen (crop if necessary)
                new_size = self._calculate_crop_size(img_size, self.screen_size)
                pil_image = pil_image.resize(new_size, self.PILImage.Resampling.LANCZOS)
                
                # Center crop
                left = (new_size[0] - self.screen_size[0]) // 2
                top = (new_size[1] - self.screen_size[1]) // 2
                right = left + self.screen_size[0]
                bottom = top + self.screen_size[1]
                pil_image = pil_image.crop((left, top, right, bottom))
            else:
                # Scale to fit screen (letterbox if necessary)
                new_size = (int(img_size[0] * scale_factor), 
                           int(img_size[1] * scale_factor))
                pil_image = pil_image.resize(new_size, self.PILImage.Resampling.LANCZOS)
            
            # Convert PIL image to pygame surface
            mode = pil_image.mode
            size = pil_image.size
            data = pil_image.tobytes()
            
            surface = self.pygame.image.fromstring(data, size, mode)
            
            # Center on screen if not crop mode
            if not self.config.crop_zoom_images:
                final_surface = self.pygame.Surface(self.screen_size)
                final_surface.fill(self.black)
                
                x = (self.screen_size[0] - surface.get_width()) // 2
                y = (self.screen_size[1] - surface.get_height()) // 2
                final_surface.blit(surface, (x, y))
                surface = final_surface
            
            return surface
            
        except Exception as e:
            self.logger.error(f"Error loading image {image_path}: {e}")
            return None
    
    def _calculate_scale_factor(self, img_size: Tuple[int, int], 
                               screen_size: Tuple[int, int]) -> float:
        """Calculate scale factor to fit image on screen"""
        img_w, img_h = img_size
        screen_w, screen_h = screen_size
        
        scale_w = screen_w / img_w
        scale_h = screen_h / img_h
        
        return min(scale_w, scale_h)
    
    def _calculate_crop_size(self, img_size: Tuple[int, int], 
                           screen_size: Tuple[int, int]) -> Tuple[int, int]:
        """Calculate size for crop-to-fill mode"""
        img_w, img_h = img_size
        screen_w, screen_h = screen_size
        
        scale_w = screen_w / img_w
        scale_h = screen_h / img_h
        
        scale = max(scale_w, scale_h)
        
        return (int(img_w * scale), int(img_h * scale))
    
    async def next_image(self):
        """Show next image"""
        if not self.image_manager or self.image_manager.get_image_count() == 0:
            self.logger.debug("No images available for next_image")
            return
        
        if not self.image_sequence:
            self._update_image_sequence()
        
        self.sequence_index = (self.sequence_index + 1) % len(self.image_sequence)
        self.current_image_index = self.image_sequence[self.sequence_index]
        
        await self._transition_to_image(self.current_image_index)
    
    async def previous_image(self):
        """Show previous image"""
        if not self.image_manager or self.image_manager.get_image_count() == 0:
            return
        
        if not self.image_sequence:
            self._update_image_sequence()
        
        self.sequence_index = (self.sequence_index - 1) % len(self.image_sequence)
        self.current_image_index = self.image_sequence[self.sequence_index]
        
        await self._transition_to_image(self.current_image_index)
    
    async def _transition_to_image(self, image_index: int):
        """Transition to specific image with fade effect"""
        if not self.pygame:
            return
            
        image_path = self.image_manager.get_image_path(image_index)
        if not image_path or not image_path.exists():
            self.logger.warning(f"Image not found: {image_path}")
            return
        
        # Load new image
        new_surface = self._load_and_scale_image(image_path)
        if not new_surface:
            return
        
        # Simple immediate transition for now
        self.current_surface = new_surface
        self.screen.blit(self.current_surface, (0, 0))
        self.pygame.display.flip()
        
        self.logger.debug(f"Showing image {image_index}: {image_path}")
    
    def toggle_pause(self):
        """Toggle pause state"""
        self.is_paused = not self.is_paused
        self.logger.debug(f"Slideshow {'paused' if self.is_paused else 'resumed'}")
    
    def update(self):
        """Update display - call this in main loop"""
        if not self.pygame or not self.screen:
            return
            
        try:
            if not self.is_fading and self.current_surface:
                self.screen.blit(self.current_surface, (0, 0))
                
                # Show pause indicator
                if self.is_paused:
                    self._draw_pause_indicator()
                
                self.pygame.display.flip()
        except Exception as e:
            self.logger.error(f"Error updating display: {e}")
    
    def _draw_pause_indicator(self):
        """Draw pause indicator on screen"""
        if not self.pygame:
            return
            
        try:
            pause_size = 60
            x = self.screen_size[0] - pause_size - 20
            y = 20
            
            # Draw two vertical bars
            bar_width = 15
            bar_height = 40
            gap = 10
            
            self.pygame.draw.rect(self.screen, self.white, 
                            (x, y, bar_width, bar_height))
            self.pygame.draw.rect(self.screen, self.white,
                            (x + bar_width + gap, y, bar_width, bar_height))
        except Exception as e:
            self.logger.error(f"Error drawing pause indicator: {e}")
    
    def cleanup(self):
        """Clean up pygame resources"""
        try:
            if self.pygame:
                self.pygame.quit()
            self.logger.info("Display cleanup complete")
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")


if __name__ == "__main__":
    # Test slideshow display
    import sys
    from config import TeleFrameConfig
    from image_manager import ImageManager
    
    async def test():
        config = TeleFrameConfig()
        manager = ImageManager(config)
        display = SlideshowDisplay(config, manager)
        
        await display.initialize()
        
        # Simple test loop
        import time
        running = True
        
        start_time = time.time()
        while running and (time.time() - start_time) < 5:  # 5 second test
            for event in display.pygame.event.get():
                if event.type == display.pygame.QUIT or event.type == display.pygame.KEYDOWN:
                    running = False
            
            display.update()
            await asyncio.sleep(0.016)  # ~60fps
        
        display.cleanup()
    
    asyncio.run(test())
