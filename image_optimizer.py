#!/usr/bin/env python3
# image_optimizer.py - TeleFrame Image Optimization System
"""
Advanced image optimization system for TeleFrame with configurable compression
and automatic format conversion for optimal display performance.
"""

import logging
import os
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Tuple, Optional, Dict, Any
from PIL import Image, ImageOps, ImageFilter
from PIL.ExifTags import ORIENTATION


class ImageOptimizer:
    """Advanced image optimizer with configurable compression and format conversion"""
    
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Get display resolution from config
        self.target_width, self.target_height = config.get_display_resolution()
        
        # Optimization settings from config
        self.optimization_enabled = getattr(config, 'image_optimization', True)
        self.compress_level = getattr(config, 'compress_level', 70)
        self.auto_format_conversion = getattr(config, 'auto_format_conversion', True)
        self.preserve_aspect_ratio = getattr(config, 'preserve_aspect_ratio', True)
        self.enable_sharpening = getattr(config, 'enable_sharpening', False)
        self.max_quality = getattr(config, 'max_quality', 95)
        self.min_quality = getattr(config, 'min_quality', 60)
        
        # Format preferences (best compression to quality ratio)
        self.preferred_formats = {
            'photo': 'JPEG',        # Best for photos
            'graphics': 'PNG',      # Best for graphics/screenshots
            'animation': 'GIF',     # Keep animations as GIF
            'fallback': 'JPEG'      # Default fallback
        }
        
        # Quality mappings for different compression levels
        self.quality_map = self._create_quality_map()
        
        self.logger.info(f"🖼️  Image Optimizer initialized:")
        self.logger.info(f"   Optimization: {'Enabled' if self.optimization_enabled else 'Disabled'}")
        self.logger.info(f"   Target resolution: {self.target_width}x{self.target_height}")
        self.logger.info(f"   Compression level: {self.compress_level}")
        self.logger.info(f"   Quality range: {self.min_quality}-{self.max_quality}")
    
    def _create_quality_map(self) -> Dict[str, int]:
        """Create quality mapping based on compression level (0-100)"""
        # Map compression level to JPEG quality
        # Higher compress_level = lower quality = smaller files
        if self.compress_level <= 10:
            return {'jpeg': 95, 'png': 1, 'webp': 95}  # Minimal compression
        elif self.compress_level <= 30:
            return {'jpeg': 90, 'png': 3, 'webp': 90}  # Light compression
        elif self.compress_level <= 50:
            return {'jpeg': 85, 'png': 5, 'webp': 85}  # Medium compression
        elif self.compress_level <= 70:
            return {'jpeg': 75, 'png': 7, 'webp': 75}  # High compression
        elif self.compress_level <= 85:
            return {'jpeg': 65, 'png': 8, 'webp': 65}  # Very high compression
        else:
            return {'jpeg': 55, 'png': 9, 'webp': 55}  # Maximum compression
    
    def optimize_image(self, input_path: Path, output_path: Optional[Path] = None) -> Optional[Path]:
        """Optimize image for display with configurable compression"""
        
        if not self.optimization_enabled:
            self.logger.debug("Image optimization disabled, skipping")
            return input_path
        
        if not input_path.exists():
            self.logger.error(f"Input image not found: {input_path}")
            return None
        
        try:
            # Generate output path if not provided
            if output_path is None:
                output_path = self._generate_optimized_path(input_path)
            
            # Load and process image
            optimized_path = self._process_image(input_path, output_path)
            
            if optimized_path:
                # Log optimization results
                self._log_optimization_results(input_path, optimized_path)
                return optimized_path
            else:
                self.logger.warning(f"Optimization failed, keeping original: {input_path}")
                return input_path
                
        except Exception as e:
            self.logger.error(f"Error optimizing image {input_path}: {e}")
            return input_path
    
    def _generate_optimized_path(self, input_path: Path) -> Path:
        """Generate optimized file path with appropriate extension"""
        
        # Determine best format for this image
        optimal_format = self._determine_optimal_format(input_path)
        
        # Create new filename with optimization suffix and proper extension
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = input_path.stem
        
        if optimal_format.lower() == 'jpeg':
            extension = '.jpg'
        elif optimal_format.lower() == 'png':
            extension = '.png'
        elif optimal_format.lower() == 'webp':
            extension = '.webp'
        else:
            extension = '.jpg'  # Fallback
        
        # Generate unique filename
        optimized_name = f"{timestamp}_{base_name}_opt{extension}"
        return input_path.parent / optimized_name
    
    def _determine_optimal_format(self, image_path: Path) -> str:
        """Determine optimal format based on image characteristics"""
        
        if not self.auto_format_conversion:
            # Keep original format if conversion is disabled
            original_ext = image_path.suffix.lower()
            if original_ext in ['.jpg', '.jpeg']:
                return 'JPEG'
            elif original_ext == '.png':
                return 'PNG'
            elif original_ext == '.gif':
                return 'GIF'
            elif original_ext == '.webp':
                return 'WEBP'
            else:
                return 'JPEG'  # Fallback
        
        try:
            with Image.open(image_path) as img:
                # Check if image has animation (GIF)
                if hasattr(img, 'is_animated') and img.is_animated:
                    return 'GIF'
                
                # Check if image has transparency
                has_transparency = (
                    img.mode in ('RGBA', 'LA') or 
                    (img.mode == 'P' and 'transparency' in img.info)
                )
                
                if has_transparency:
                    # PNG is better for images with transparency
                    return 'PNG'
                
                # Check image characteristics
                width, height = img.size
                pixel_count = width * height
                
                # For small images or graphics, use PNG
                if pixel_count < 100000:  # Less than ~300x300
                    return 'PNG'
                
                # For large photos, use JPEG
                return 'JPEG'
                
        except Exception as e:
            self.logger.debug(f"Could not analyze image {image_path}: {e}")
            return 'JPEG'  # Safe fallback
    
    def _process_image(self, input_path: Path, output_path: Path) -> Optional[Path]:
        """Process and optimize image"""
        
        try:
            with Image.open(input_path) as img:
                # Handle EXIF orientation
                img = self._fix_orientation(img)
                
                # Convert mode if needed
                img = self._convert_mode(img, output_path)
                
                # Resize image to target resolution
                img = self._resize_image(img)
                
                # Apply sharpening if enabled
                if self.enable_sharpening:
                    img = self._apply_sharpening(img)
                
                # Save optimized image
                self._save_optimized_image(img, output_path)
                
                return output_path
                
        except Exception as e:
            self.logger.error(f"Error processing image {input_path}: {e}")
            return None
    
    def _fix_orientation(self, img: Image.Image) -> Image.Image:
        """Fix image orientation based on EXIF data"""
        try:
            # Use ImageOps.exif_transpose for better EXIF handling
            img = ImageOps.exif_transpose(img)
            self.logger.debug("Fixed image orientation using EXIF data")
        except Exception as e:
            self.logger.debug(f"Could not fix orientation: {e}")
        
        return img
    
    def _convert_mode(self, img: Image.Image, output_path: Path) -> Image.Image:
        """Convert image mode based on output format"""
        
        output_format = self._get_format_from_path(output_path)
        
        if output_format == 'JPEG':
            # JPEG doesn't support transparency
            if img.mode in ('RGBA', 'LA', 'P'):
                # Create white background
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')
                
        elif output_format == 'PNG':
            # PNG supports transparency
            if img.mode not in ('RGB', 'RGBA', 'L', 'LA'):
                if 'transparency' in img.info:
                    img = img.convert('RGBA')
                else:
                    img = img.convert('RGB')
                    
        elif output_format == 'WEBP':
            # WebP supports both RGB and RGBA
            if img.mode not in ('RGB', 'RGBA'):
                if 'transparency' in img.info:
                    img = img.convert('RGBA')
                else:
                    img = img.convert('RGB')
        
        return img
    
    def _resize_image(self, img: Image.Image) -> Image.Image:
        """Resize image to target resolution while preserving aspect ratio"""
        
        original_size = img.size
        target_size = (self.target_width, self.target_height)
        
        # Skip resize if image is already smaller or same size
        if (original_size[0] <= target_size[0] and 
            original_size[1] <= target_size[1]):
            self.logger.debug(f"Image {original_size} smaller than target {target_size}, keeping original size")
            return img
        
        if self.preserve_aspect_ratio:
            # Calculate scaling factor to fit within target size
            scale_x = target_size[0] / original_size[0]
            scale_y = target_size[1] / original_size[1]
            scale = min(scale_x, scale_y)
            
            new_size = (
                int(original_size[0] * scale),
                int(original_size[1] * scale)
            )
        else:
            # Stretch to exact target size
            new_size = target_size
        
        # Use high-quality resampling
        img = img.resize(new_size, Image.Resampling.LANCZOS)
        
        self.logger.debug(f"Resized image: {original_size} → {new_size}")
        return img
    
    def _apply_sharpening(self, img: Image.Image) -> Image.Image:
        """Apply subtle sharpening to improve clarity"""
        try:
            # Apply unsharp mask for subtle sharpening
            img = img.filter(ImageFilter.UnsharpMask(radius=1, percent=120, threshold=3))
            self.logger.debug("Applied image sharpening")
        except Exception as e:
            self.logger.debug(f"Could not apply sharpening: {e}")
        
        return img
    
    def _save_optimized_image(self, img: Image.Image, output_path: Path):
        """Save image with optimal compression settings"""
        
        output_format = self._get_format_from_path(output_path)
        quality_settings = self.quality_map
        
        save_kwargs = {}
        
        if output_format == 'JPEG':
            save_kwargs.update({
                'format': 'JPEG',
                'quality': quality_settings['jpeg'],
                'optimize': True,
                'progressive': True,  # Progressive JPEG for better perceived loading
            })
            
        elif output_format == 'PNG':
            save_kwargs.update({
                'format': 'PNG',
                'optimize': True,
                'compress_level': quality_settings['png'],  # 0-9, higher = more compression
            })
            
        elif output_format == 'WEBP':
            save_kwargs.update({
                'format': 'WEBP',
                'quality': quality_settings['webp'],
                'optimize': True,
                'method': 6,  # Best compression method
            })
            
        elif output_format == 'GIF':
            save_kwargs.update({
                'format': 'GIF',
                'optimize': True,
                'save_all': True,  # For animated GIFs
            })
        
        # Save the image
        img.save(output_path, **save_kwargs)
        self.logger.debug(f"Saved optimized image: {output_path} ({output_format}, quality: {save_kwargs.get('quality', 'N/A')})")
    
    def _get_format_from_path(self, path: Path) -> str:
        """Get image format from file extension"""
        ext = path.suffix.lower()
        
        if ext in ['.jpg', '.jpeg']:
            return 'JPEG'
        elif ext == '.png':
            return 'PNG'
        elif ext == '.gif':
            return 'GIF'
        elif ext == '.webp':
            return 'WEBP'
        else:
            return 'JPEG'  # Fallback
    
    def _log_optimization_results(self, input_path: Path, output_path: Path):
        """Log optimization results for monitoring"""
        try:
            input_size = input_path.stat().st_size
            output_size = output_path.stat().st_size
            
            reduction_percent = ((input_size - output_size) / input_size) * 100
            
            self.logger.info(f"📸 Image optimized: {input_path.name} → {output_path.name}")
            self.logger.info(f"   Size: {self._format_bytes(input_size)} → {self._format_bytes(output_size)} "
                           f"({reduction_percent:+.1f}%)")
            
            # Get image dimensions
            try:
                with Image.open(output_path) as img:
                    self.logger.info(f"   Resolution: {img.size[0]}x{img.size[1]}")
            except:
                pass
                
        except Exception as e:
            self.logger.debug(f"Could not log optimization results: {e}")
    
    def _format_bytes(self, bytes_value: int) -> str:
        """Format bytes in human readable format"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_value < 1024.0:
                return f"{bytes_value:.1f}{unit}"
            bytes_value /= 1024.0
        return f"{bytes_value:.1f}TB"
    
    def get_optimization_stats(self) -> Dict[str, Any]:
        """Get optimization statistics"""
        return {
            'enabled': self.optimization_enabled,
            'target_resolution': f"{self.target_width}x{self.target_height}",
            'compress_level': self.compress_level,
            'quality_settings': self.quality_map,
            'auto_format_conversion': self.auto_format_conversion,
            'preserve_aspect_ratio': self.preserve_aspect_ratio,
            'enable_sharpening': self.enable_sharpening,
            'preferred_formats': self.preferred_formats,
        }
    
    def test_optimization(self, test_image_path: Path) -> Dict[str, Any]:
        """Test optimization on a single image and return results"""
        
        if not test_image_path.exists():
            return {'error': f'Test image not found: {test_image_path}'}
        
        try:
            # Get original info
            original_size = test_image_path.stat().st_size
            
            with Image.open(test_image_path) as img:
                original_dimensions = img.size
                original_mode = img.mode
                original_format = img.format
            
            # Perform optimization
            optimized_path = self.optimize_image(test_image_path)
            
            if optimized_path and optimized_path != test_image_path:
                # Get optimized info
                optimized_size = optimized_path.stat().st_size
                
                with Image.open(optimized_path) as opt_img:
                    optimized_dimensions = opt_img.size
                    optimized_mode = opt_img.mode
                    optimized_format = opt_img.format
                
                # Calculate savings
                size_reduction = ((original_size - optimized_size) / original_size) * 100
                
                # Clean up test file
                try:
                    optimized_path.unlink()
                except:
                    pass
                
                return {
                    'success': True,
                    'original': {
                        'size': original_size,
                        'size_formatted': self._format_bytes(original_size),
                        'dimensions': original_dimensions,
                        'mode': original_mode,
                        'format': original_format,
                    },
                    'optimized': {
                        'size': optimized_size,
                        'size_formatted': self._format_bytes(optimized_size),
                        'dimensions': optimized_dimensions,
                        'mode': optimized_mode,
                        'format': optimized_format,
                    },
                    'savings': {
                        'bytes': original_size - optimized_size,
                        'percentage': size_reduction,
                    }
                }
            else:
                return {
                    'success': False,
                    'message': 'Optimization disabled or failed',
                    'original': {
                        'size': original_size,
                        'size_formatted': self._format_bytes(original_size),
                        'dimensions': original_dimensions,
                        'mode': original_mode,
                        'format': original_format,
                    }
                }
                
        except Exception as e:
            return {'error': f'Test failed: {e}'}

    def batch_optimize(self, image_folder: Path, file_pattern: str = "*.jpg") -> Dict[str, Any]:
        """Batch optimize images in a folder"""
        if not image_folder.exists():
            return {'error': f'Folder not found: {image_folder}'}
        
        try:
            # Find matching images
            image_files = list(image_folder.glob(file_pattern))
            if not image_files:
                return {'error': f'No images found matching pattern: {file_pattern}'}
            
            results = {
                'total_files': len(image_files),
                'successful': 0,
                'failed': 0,
                'total_original_size': 0,
                'total_optimized_size': 0,
                'errors': []
            }
            
            for image_file in image_files:
                try:
                    original_size = image_file.stat().st_size
                    results['total_original_size'] += original_size
                    
                    optimized_path = self.optimize_image(image_file)
                    
                    if optimized_path and optimized_path.exists():
                        optimized_size = optimized_path.stat().st_size
                        results['total_optimized_size'] += optimized_size
                        results['successful'] += 1
                    else:
                        results['total_optimized_size'] += original_size
                        results['failed'] += 1
                        results['errors'].append(f"Optimization failed for {image_file.name}")
                        
                except Exception as e:
                    results['failed'] += 1
                    results['errors'].append(f"Error processing {image_file.name}: {e}")
                    # Add original size to avoid division by zero
                    try:
                        results['total_optimized_size'] += image_file.stat().st_size
                    except:
                        pass
            
            # Calculate total savings
            if results['total_original_size'] > 0:
                total_savings = results['total_original_size'] - results['total_optimized_size']
                savings_percent = (total_savings / results['total_original_size']) * 100
                
                results['total_savings_bytes'] = total_savings
                results['total_savings_formatted'] = self._format_bytes(total_savings)
                results['savings_percent'] = savings_percent
            
            return results
            
        except Exception as e:
            return {'error': f'Batch optimization failed: {e}'}


if __name__ == "__main__":
    """Test image optimizer functionality"""
    import sys
    from pathlib import Path
    
    # Mock config for testing
    class MockConfig:
        def __init__(self):
            self.image_optimization = True
            self.compress_level = 70
            self.auto_format_conversion = True
            self.preserve_aspect_ratio = True
            self.enable_sharpening = False
            self.max_quality = 95
            self.min_quality = 60
        
        def get_display_resolution(self):
            return (1920, 1080)
        
        def get_image_optimization_config(self):
            return {
                "enabled": self.image_optimization,
                "compress_level": self.compress_level,
                "auto_format_conversion": self.auto_format_conversion,
                "preserve_aspect_ratio": self.preserve_aspect_ratio,
                "enable_sharpening": self.enable_sharpening,
                "max_quality": self.max_quality,
                "min_quality": self.min_quality,
            }
    
    print("🖼️  TeleFrame Image Optimizer Test")
    print("=" * 50)
    
    # Create test optimizer
    config = MockConfig()
    optimizer = ImageOptimizer(config)
    
    # Show configuration
    print("Configuration:")
    stats = optimizer.get_optimization_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    # Test with image if provided
    if len(sys.argv) > 1:
        test_image = Path(sys.argv[1])
        print(f"\nTesting with image: {test_image}")
        
        if test_image.exists():
            results = optimizer.test_optimization(test_image)
            
            if 'error' in results:
                print(f"❌ Error: {results['error']}")
            elif results['success']:
                print("✅ Optimization test successful!")
                print(f"Original: {results['original']['size_formatted']} "
                      f"({results['original']['dimensions'][0]}x{results['original']['dimensions'][1]}) "
                      f"{results['original']['format']}")
                print(f"Optimized: {results['optimized']['size_formatted']} "
                      f"({results['optimized']['dimensions'][0]}x{results['optimized']['dimensions'][1]}) "
                      f"{results['optimized']['format']}")
                print(f"Savings: {results['savings']['percentage']:.1f}% "
                      f"({results['savings']['bytes']} bytes)")
            else:
                print(f"⚠️  {results['message']}")
        else:
            print(f"❌ Test image not found: {test_image}")
    
    # Test batch optimization if folder provided
    elif len(sys.argv) > 2 and sys.argv[1] == "--batch":
        test_folder = Path(sys.argv[2])
        pattern = sys.argv[3] if len(sys.argv) > 3 else "*.jpg"
        
        print(f"\nTesting batch optimization:")
        print(f"  Folder: {test_folder}")
        print(f"  Pattern: {pattern}")
        
        if test_folder.exists():
            results = optimizer.batch_optimize(test_folder, pattern)
            
            if 'error' in results:
                print(f"❌ Error: {results['error']}")
            else:
                print("✅ Batch optimization completed!")
                print(f"  Files processed: {results['total_files']}")
                print(f"  Successful: {results['successful']}")
                print(f"  Failed: {results['failed']}")
                
                if 'total_savings_formatted' in results:
                    print(f"  Total savings: {results['total_savings_formatted']} ({results['savings_percent']:.1f}%)")
                
                if results['errors']:
                    print("  Errors:")
                    for error in results['errors'][:5]:  # Show first 5 errors
                        print(f"    - {error}")
        else:
            print(f"❌ Test folder not found: {test_folder}")
    else:
        print("\nUsage:")
        print("  Test single image: python3 image_optimizer.py /path/to/image.jpg")
        print("  Test batch: python3 image_optimizer.py --batch /path/to/folder *.jpg")
    
    print("\n🎉 Image optimizer test completed!")
