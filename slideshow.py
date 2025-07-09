# slideshow.py - Updated with image_order support
"""
Enhanced slideshow display with configurable image ordering
Supports random, latest, oldest, and sequential ordering
"""

import asyncio
import logging
import os
import random
from pathlib import Path
from typing import Optional, Tuple, List

# DON'T import pygame here - import it AFTER SDL setup!


class SlideshowDisplay:
    """Handles slideshow display with configurable image ordering"""
    
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
        
        # Image sequence for different ordering modes
        self.image_sequence = []
        self.sequence_index = 0
        self.last_order_mode = None  # Track when order mode changes
        
        # Colors (will be set after pygame import)
        self.black = None
        self.white = None
        
        # pygame and PIL modules (imported later)
        self.pygame = None
        self.PILImage = None
        
        self.logger.info(f"SlideshowDisplay initialized with order: {config.get_image_order_mode()}")
    
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
            self.logger.info(f"   Image order: {self.config.get_image_order_mode()}")
            
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
        """Show startup screen with TeleFrame logo and image order info"""
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
            
            # Image order info
            order_text = f"Order: {self.config.get_image_order_description()}"
            order = self.font_small.render(order_text, True, self.white)
            order_rect = order.get_rect(center=(self.screen_size[0] // 2,
                                               self.screen_size[1] // 2 + 50))
            self.screen.blit(order, order_rect)
            
            # Display driver info
            driver_info = f"Driver: {self.pygame.display.get_driver()}"
            driver_text = self.font_small.render(driver_info, True, self.white)
            driver_rect = driver_text.get_rect(center=(self.screen_size[0] // 2,
                                                     self.screen_size[1] // 2 + 80))
            self.screen.blit(driver_text, driver_rect)
            
            self.pygame.display.flip()
            
        except Exception as e:
            self.logger.error(f"Error showing startup screen: {e}")
    
    def _update_image_sequence(self, force_refresh: bool = False):
        """Update the image display sequence based on order mode"""
        if not self.image_manager:
            return
        
        image_count = self.image_manager.get_image_count()
        if image_count == 0:
            self.image_sequence = []
            return
        
        current_order_mode = self.config.get_image_order_mode()
        
        # Check if we need to update the sequence
        if (not force_refresh and 
            self.last_order_mode == current_order_mode and 
            len(self.image_sequence) == image_count):
            return
        
        self.logger.info(f"🔄 Updating image sequence: {current_order_mode} mode")
        
        # Generate sequence based on order mode
        if current_order_mode == "random":
            self.image_sequence = self._generate_random_sequence(image_count)
        elif current_order_mode == "latest":
            self.image_sequence = self._generate_latest_sequence(image_count)
        elif current_order_mode == "oldest":
            self.image_sequence = self._generate_oldest_sequence(image_count)
        elif current_order_mode == "sequential":
            self.image_sequence = self._generate_sequential_sequence(image_count)
        else:
            # Fallback to sequential if unknown mode
            self.logger.warning(f"Unknown order mode: {current_order_mode}, using sequential")
            self.image_sequence = self._generate_sequential_sequence(image_count)
        
        # Reset sequence position
        self.sequence_index = 0
        self.last_order_mode = current_order_mode
        
        self.logger.debug(f"Generated sequence: {len(self.image_sequence)} images, first 5: {self.image_sequence[:5]}")
    
    def _generate_random_sequence(self, image_count: int) -> List[int]:
        """Generate randomized image sequence"""
        sequence = list(range(image_count))
        random.shuffle(sequence)
        return sequence
    
    def _generate_latest_sequence(self, image_count: int) -> List[int]:
        """Generate sequence with latest images first (reverse chronological)"""
        # Images are stored with index 0 being newest (inserted at beginning)
        return list(range(image_count))
    
    def _generate_oldest_sequence(self, image_count: int) -> List[int]:
        """Generate sequence with oldest images first (chronological)"""
        # Reverse the list to show oldest first
        return list(range(image_count - 1, -1, -1))
    
    def _generate_sequential_sequence(self, image_count: int) -> List[int]:
        """Generate sequential sequence (storage order)"""
        return list(range(image_count))
    
    def change_image_order(self, new_order: str) -> bool:
        """Change image order mode and refresh sequence"""
        if self.config.set_image_order_mode(new_order):
            self._update_image_sequence(force_refresh=True)
            self.logger.info(f"✅ Image order changed to: {new_order}")
            
            # Show notification on screen if possible
            self._show_order_change_notification(new_order)
            return True
        else:
            self.logger.error(f"❌ Failed to change image order to: {new_order}")
            return False
    
    def _show_order_change_notification(self, new_order: str):
        """Show temporary notification of order change"""
        if not self.pygame or not self.screen:
            return
        
        try:
            # Save current screen
            saved_screen = self.screen.copy()
            
            # Create semi-transparent overlay
            overlay = self.pygame.Surface(self.screen_size)
            overlay.set_alpha(128)
            overlay.fill((0, 0, 0))
            self.screen.blit(overlay, (0, 0))
            
            # Show notification text
            notification_text = f"Image Order: {new_order.title()}"
            description = self.config.get_image_order_description()
            
            title = self.font_large.render(notification_text, True, self.white)
            desc = self.font_medium.render(description, True, self.white)
            
            title_rect = title.get_rect(center=(self.screen_size[0] // 2, 
                                               self.screen_size[1] // 2 - 30))
            desc_rect = desc.get_rect(center=(self.screen_size[0] // 2,
                                            self.screen_size[1] // 2 + 30))
            
            self.screen.blit(title, title_rect)
            self.screen.blit(desc, desc_rect)
            
            self.pygame.display.flip()
            
            # Brief pause to show notification
            import time
            time.sleep(1.5)
            
            # Restore screen
            self.screen.blit(saved_screen, (0, 0))
            self.pygame.display.flip()
            
        except Exception as e:
            self.logger.error(f"Error showing order change notification: {e}")
    
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
        """Show next image based on current order mode"""
        if not self.image_manager or self.image_manager.get_image_count() == 0:
            self.logger.debug("No images available for next_image")
            return
        
        # Update sequence if needed (e.g., new images added)
        self._update_image_sequence()
        
        if not self.image_sequence:
            return
        
        # Handle random mode special case - reshuffle when sequence ends
        if (self.config.get_image_order_mode() == "random" and 
            self.sequence_index >= len(self.image_sequence) - 1):
            self.logger.debug("End of random sequence - reshuffling")
            self._update_image_sequence(force_refresh=True)
        
        # Advance to next image
        self.sequence_index = (self.sequence_index + 1) % len(self.image_sequence)
        self.current_image_index = self.image_sequence[self.sequence_index]
        
        await self._transition_to_image(self.current_image_index)
    
    async def previous_image(self):
        """Show previous image based on current order mode"""
        if not self.image_manager or self.image_manager.get_image_count() == 0:
            return
        
        # Update sequence if needed
        self._update_image_sequence()
        
        if not self.image_sequence:
            return
        
        # Go to previous image
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
        
        # Show image info if enabled
        if self.config.show_sender or self.config.show_caption:
            self._draw_image_info(image_index)
        
        self.pygame.display.flip()
        
        # Log with order info
        order_mode = self.config.get_image_order_mode()
        self.logger.debug(f"Showing image {image_index} ({self.sequence_index + 1}/{len(self.image_sequence)}) "
                         f"[{order_mode}]: {image_path}")
    
    def _draw_image_info(self, image_index: int):
        """Draw image information overlay"""
        if not self.pygame or not self.image_manager:
            return
        
        try:
            image_info = self.image_manager.get_image_info(image_index)
            if not image_info:
                return
            
            # Prepare text lines
            text_lines = []
            
            if self.config.show_sender and image_info.sender:
                text_lines.append(f"From: {image_info.sender}")
            
            if self.config.show_caption and image_info.caption:
                text_lines.append(f"Caption: {image_info.caption}")
            
            if not text_lines:
                return
            
            # Draw semi-transparent background
            padding = 10
            line_height = 30
            total_height = len(text_lines) * line_height + 2 * padding
            max_width = max(self.font_small.size(line)[0] for line in text_lines)
            bg_width = max_width + 2 * padding
            
            # Position at bottom of screen
            bg_x = 10
            bg_y = self.screen_size[1] - total_height - 10
            
            bg_surface = self.pygame.Surface((bg_width, total_height))
            bg_surface.set_alpha(180)
            bg_surface.fill((0, 0, 0))
            self.screen.blit(bg_surface, (bg_x, bg_y))
            
            # Draw text lines
            y_offset = bg_y + padding
            for line in text_lines:
                text_surface = self.font_small.render(line, True, self.white)
                self.screen.blit(text_surface, (bg_x + padding, y_offset))
                y_offset += line_height
                
        except Exception as e:
            self.logger.error(f"Error drawing image info: {e}")
    
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
                
                # Show order mode indicator (small text in corner)
                self._draw_order_indicator()
                
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
    
    def _draw_order_indicator(self):
        """Draw small order mode indicator in corner"""
        if not self.pygame:
            return
        
        try:
            # Small text in top-right corner
            order_text = self.config.get_image_order_mode().upper()
            text_surface = self.font_small.render(order_text, True, (200, 200, 200))
            
            # Position in top-right with small margin
            x = self.screen_size[0] - text_surface.get_width() - 10
            y = 10
            
            # Semi-transparent background
            bg_surface = self.pygame.Surface((text_surface.get_width() + 4, 
                                            text_surface.get_height() + 2))
            bg_surface.set_alpha(100)
            bg_surface.fill((0, 0, 0))
            self.screen.blit(bg_surface, (x - 2, y - 1))
            
            # Draw text
            self.screen.blit(text_surface, (x, y))
            
        except Exception as e:
            self.logger.error(f"Error drawing order indicator: {e}")
    
    def get_current_order_info(self) -> dict:
        """Get information about current image order"""
        return {
            "mode": self.config.get_image_order_mode(),
            "description": self.config.get_image_order_description(),
            "sequence_length": len(self.image_sequence),
            "current_position": self.sequence_index + 1 if self.image_sequence else 0,
            "current_image_index": self.current_image_index if self.image_sequence else None
        }
    
    def cleanup(self):
        """Clean up pygame resources"""
        try:
            if self.pygame:
                self.pygame.quit()
            self.logger.info("Display cleanup complete")
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")


if __name__ == "__main__":
    # Test slideshow display with different order modes
    import sys
    from config import TeleFrameConfig
    from image_manager import ImageManager
    
    async def test():
        config = TeleFrameConfig()
        manager = ImageManager(config)
        display = SlideshowDisplay(config, manager)
        
        await display.initialize()
        
        # Test different order modes
        test_modes = ["random", "latest", "oldest", "sequential"]
        
        for mode in test_modes:
            print(f"Testing {mode} mode...")
            display.change_image_order(mode)
            
            # Show order info
            order_info = display.get_current_order_info()
            print(f"  Order info: {order_info}")
            
            # Brief display
            import time
            time.sleep(2)
        
        display.cleanup()
    
    asyncio.run(test())
