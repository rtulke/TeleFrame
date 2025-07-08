# image_manager.py - TeleFrame Image Management
"""
Secure image management with validation and metadata handling
"""

import json
import logging
import magic
import hashlib
from datetime import datetime
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Optional, Dict, Any
from PIL import Image, ImageOps


@dataclass
class ImageInfo:
    """Image metadata structure"""
    src: str
    sender: str
    caption: str
    chat_id: int
    chat_name: str
    message_id: int
    timestamp: datetime
    starred: bool = False
    unseen: bool = True
    file_hash: Optional[str] = None
    file_size: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ImageInfo':
        """Create from dictionary"""
        data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        return cls(**data)


class ImageManager:
    """Manages image storage, metadata, and validation"""

    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.images: List[ImageInfo] = []

        # Ensure directories exist
        self.image_folder = Path(config.image_folder)
        self.image_folder.mkdir(parents=True, exist_ok=True)

        self.metadata_file = self.image_folder / "images.json"

        # Load existing images
        self._load_metadata()

        self.logger.info(f"ImageManager initialized with {len(self.images)} images")

    def _load_metadata(self):
        """Load image metadata from JSON file"""
        if not self.metadata_file.exists():
            self.logger.info("No existing metadata file found")
            return

        try:
            with open(self.metadata_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            loaded_images = []
            for item in data:
                try:
                    image_info = ImageInfo.from_dict(item)

                    # Verify file still exists
                    if Path(image_info.src).exists():
                        loaded_images.append(image_info)
                    else:
                        self.logger.warning(f"Image file missing: {image_info.src}")

                except Exception as e:
                    self.logger.error(f"Error loading image metadata: {e}")

            self.images = loaded_images
            self.logger.info(f"Loaded {len(self.images)} valid images from metadata")

        except Exception as e:
            self.logger.error(f"Error loading metadata file: {e}")
            self.images = []

    def _save_metadata(self):
        """Save image metadata to JSON file"""
        try:
            data = [img.to_dict() for img in self.images]

            with open(self.metadata_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            self.logger.debug("Metadata saved successfully")

        except Exception as e:
            self.logger.error(f"Error saving metadata: {e}")

    def validate_file(self, file_path: Path) -> bool:
        """Validate file type and size"""
        try:
            # Check file exists
            if not file_path.exists():
                self.logger.warning(f"File does not exist: {file_path}")
                return False

            # Check file size
            file_size = file_path.stat().st_size
            if file_size > self.config.max_file_size:
                self.logger.warning(f"File too large: {file_size} bytes")
                return False

            # Check file extension
            if not self.config.is_file_allowed(file_path.name):
                self.logger.warning(f"File type not allowed: {file_path.suffix}")
                return False

            # Check MIME type using python-magic
            mime_type = magic.from_file(str(file_path), mime=True)
            allowed_mimes = {
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.png': 'image/png',
                '.gif': 'image/gif',
                '.mp4': 'video/mp4'
            }

            expected_mime = allowed_mimes.get(file_path.suffix.lower())
            if expected_mime and not mime_type.startswith(expected_mime.split('/')[0]):
                self.logger.warning(f"MIME type mismatch: {mime_type}")
                return False

            # For images, try to open with PIL
            if file_path.suffix.lower() in ['.jpg', '.jpeg', '.png', '.gif']:
                try:
                    with Image.open(file_path) as img:
                        img.verify()
                except Exception as e:
                    self.logger.warning(f"Invalid image file: {e}")
                    return False

            return True

        except Exception as e:
            self.logger.error(f"Error validating file {file_path}: {e}")
            return False

    def _calculate_file_hash(self, file_path: Path) -> str:
        """Calculate SHA256 hash of file"""
        hash_sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()

    def add_image(self, file_path: Path, sender: str, caption: str,
                  chat_id: int, chat_name: str, message_id: int) -> bool:
        """Add new image to collection"""
        try:
            # Validate file
            if not self.validate_file(file_path):
                return False

            # Calculate file hash to detect duplicates
            file_hash = self._calculate_file_hash(file_path)

            # Check for duplicates
            for existing in self.images:
                if existing.file_hash == file_hash:
                    self.logger.info(f"Duplicate image detected: {file_path}")
                    return False

            # Create image info
            image_info = ImageInfo(
                src=str(file_path),
                sender=sender,
                caption=caption or "",
                chat_id=chat_id,
                chat_name=chat_name,
                message_id=message_id,
                timestamp=datetime.now(),
                file_hash=file_hash,
                file_size=file_path.stat().st_size
            )

            # Add to beginning of list (newest first)
            self.images.insert(0, image_info)

            # Cleanup old images if necessary
            self._cleanup_old_images()

            # Save metadata
            self._save_metadata()

            self.logger.info(f"Added image: {file_path} from {sender}")
            return True

        except Exception as e:
            self.logger.error(f"Error adding image: {e}")
            return False

    def _cleanup_old_images(self):
        """Remove old images beyond the configured limit"""
        if len(self.images) <= self.config.image_count:
            return

        # Count non-starred images
        non_starred = [img for img in self.images if not img.starred]
        starred = [img for img in self.images if img.starred]

        # Calculate how many to remove
        total_limit = self.config.image_count
        starred_count = len(starred)

        if starred_count >= total_limit:
            # Too many starred images, keep newest starred ones
            to_keep = starred[:total_limit]
            to_remove = starred[total_limit:] + non_starred
        else:
            # Keep all starred + newest non-starred
            non_starred_limit = total_limit - starred_count
            to_keep = starred + non_starred[:non_starred_limit]
            to_remove = non_starred[non_starred_limit:]

        # Remove files and metadata
        for image_info in to_remove:
            if self.config.auto_delete_images:
                try:
                    Path(image_info.src).unlink(missing_ok=True)
                    self.logger.debug(f"Deleted file: {image_info.src}")
                except Exception as e:
                    self.logger.error(f"Error deleting file {image_info.src}: {e}")

        # Update images list
        self.images = to_keep
        self.logger.info(f"Cleaned up {len(to_remove)} old images")

    def star_image(self, index: int) -> bool:
        """Toggle star status of image"""
        if 0 <= index < len(self.images):
            self.images[index].starred = not self.images[index].starred
            self._save_metadata()
            self.logger.info(f"Toggled star for image {index}")
            return True
        return False

    def delete_image(self, index: int) -> bool:
        """Delete specific image"""
        if 0 <= index < len(self.images):
            image_info = self.images[index]

            # Delete file
            try:
                Path(image_info.src).unlink(missing_ok=True)
                self.logger.info(f"Deleted file: {image_info.src}")
            except Exception as e:
                self.logger.error(f"Error deleting file: {e}")

            # Remove from list
            del self.images[index]
            self._save_metadata()

            self.logger.info(f"Deleted image at index {index}")
            return True
        return False

    def mark_all_seen(self):
        """Mark all images as seen"""
        for image in self.images:
            image.unseen = False
        self._save_metadata()
        self.logger.info("Marked all images as seen")

    def get_image_count(self) -> int:
        """Get total number of images"""
        return len(self.images)

    def get_unseen_count(self) -> int:
        """Get number of unseen images"""
        return sum(1 for img in self.images if img.unseen)

    def get_image_info(self, index: int) -> Optional[ImageInfo]:
        """Get image info by index"""
        if 0 <= index < len(self.images):
            return self.images[index]
        return None

    def get_image_path(self, index: int) -> Optional[Path]:
        """Get image file path by index"""
        image_info = self.get_image_info(index)
        if image_info:
            return Path(image_info.src)
        return None


if __name__ == "__main__":
    # Test image manager
    from config import TeleFrameConfig

    config = TeleFrameConfig()
    manager = ImageManager(config)

    print(f"Loaded {manager.get_image_count()} images")
    print(f"Unseen: {manager.get_unseen_count()}")
