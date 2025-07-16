# image_manager.py - TeleFrame Image Management
"""
Secure image management with validation and metadata handling
"""

import json
import logging
import magic
import hashlib
import tempfile
import shutil
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
        """Load metadata with corruption recovery"""
        if not self.metadata_file.exists():
            self.logger.info("No existing metadata file found")
            return

        # Try to load main file
        if self._try_load_json_file(self.metadata_file):
            return

        self.logger.warning("Main metadata file corrupt, trying backup...")

        # Try backup file
        backup_file = self.metadata_file.with_suffix('.backup')
        if backup_file.exists() and self._try_load_json_file(backup_file):
            # Restore from backup
            try:
                shutil.copy2(backup_file, self.metadata_file)
                self.logger.info("Restored metadata from backup")
                return
            except Exception as e:
                self.logger.error(f"Could not restore from backup: {e}")

        self.logger.warning("Both main and backup files corrupt, attempting recovery...")

        # Try to recover by truncating corrupted entries
        if self._recover_corrupt_json():
            return

        # Last resort: start fresh
        self.logger.error("Could not recover metadata, starting with empty library")
        self.images = []
        try:
            self._save_metadata()
        except Exception as e:
            self.logger.error(f"Could not create new metadata file: {e}")


    def _save_metadata(self):
        """Atomic save with backup and validation"""
        try:
            data = [img.to_dict() for img in self.images]
        
            # Create temporary file in same directory (atomic move)
            temp_file = self.metadata_file.with_suffix('.tmp')
            backup_file = self.metadata_file.with_suffix('.backup')
        
            # Write to temporary file first
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        
            # Validate the written file
            if not self._validate_json_file(temp_file):
                raise ValueError("JSON validation failed after write")
        
            # Create backup of current file (if exists)
            if self.metadata_file.exists():
                try:
                    shutil.copy2(self.metadata_file, backup_file)
                    self.logger.debug("Created backup of existing metadata")
                except Exception as e:
                    self.logger.warning(f"Could not create backup: {e}")
        
            # Atomic move (should be atomic on most filesystems)
            shutil.move(str(temp_file), str(self.metadata_file))
        
            self.logger.debug("Metadata saved successfully with atomic write")
        
        except Exception as e:
            self.logger.error(f"Error saving metadata: {e}")
            # Clean up temp file if it exists
            temp_file = self.metadata_file.with_suffix('.tmp')
            if temp_file.exists():
                temp_file.unlink(missing_ok=True)
            # Re-raise to indicate save failure
            raise

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
    
    def _validate_json_file(self, file_path: Path) -> bool:
        """Validate JSON file structure"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Check if it's a list
            if not isinstance(data, list):
                self.logger.error("JSON validation failed: not a list")
                return False

            # Validate each entry has required fields
            required_fields = ['src', 'sender', 'timestamp', 'chat_id', 'message_id']
            for i, item in enumerate(data):
                if not isinstance(item, dict):
                    self.logger.error(f"JSON validation failed: item {i} is not a dictionary")
                    return False

                for field in required_fields:
                    if field not in item:
                        self.logger.error(f"JSON validation failed: item {i} missing field '{field}'")
                        return False

            self.logger.debug(f"JSON validation successful: {len(data)} entries")
            return True

        except json.JSONDecodeError as e:
            self.logger.error(f"JSON validation failed: invalid JSON - {e}")
            return False
        except Exception as e:
            self.logger.error(f"JSON validation failed: {e}")
            return False

    def _try_load_json_file(self, file_path: Path) -> bool:
        """Try to load a specific JSON file"""
        try:
            # First validate the file
            if not self._validate_json_file(file_path):
                return False

            # Load the data
            with open(file_path, 'r', encoding='utf-8') as f:
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
            self.logger.info(f"Loaded {len(self.images)} valid images from {file_path.name}")
            return True

        except Exception as e:
            self.logger.error(f"Error loading {file_path}: {e}")
            return False

    def _recover_corrupt_json(self) -> bool:
        """Attempt to recover from corrupted JSON by truncating bad entries"""
        try:
            self.logger.info("Attempting JSON recovery...")

            with open(self.metadata_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # Try to find the last valid JSON structure
            lines = content.split('\n')

            # Work backwards from the end
            for i in range(len(lines) - 1, -1, -1):
                try:
                    # Try to parse from start to this line
                    test_content = '\n'.join(lines[:i+1])

                    # If content doesn't end with ], try to fix it
                    if not test_content.strip().endswith(']'):
                        # Find last complete entry (ending with })
                        last_brace = test_content.rfind('}')
                        if last_brace > 0:
                            # Cut after last complete entry and add closing bracket
                            test_content = test_content[:last_brace+1] + '\n]'
                        else:
                            continue

                    # Try to parse the reconstructed JSON
                    data = json.loads(test_content)

                    if isinstance(data, list) and len(data) > 0:
                        # Validate and load entries
                        valid_entries = []
                        for entry in data:
                            try:
                                image_info = ImageInfo.from_dict(entry)
                                if Path(image_info.src).exists():
                                    valid_entries.append(image_info)
                            except Exception:
                                continue

                        if valid_entries:
                            self.images = valid_entries
                            # Save recovered data
                            self._save_metadata()
                            self.logger.info(f"Successfully recovered {len(valid_entries)} images from corrupted file")
                            return True

                except json.JSONDecodeError:
                    continue
                except Exception:
                    continue

            self.logger.error("Could not recover any valid entries from corrupted JSON")
            return False

        except Exception as e:
            self.logger.error(f"Recovery attempt failed: {e}")
            return False

    def verify_metadata_integrity(self) -> bool:
        """Verify metadata file integrity (for debugging)"""
        if not self.metadata_file.exists():
            self.logger.info("No metadata file to verify")
            return True

        try:
            is_valid = self._validate_json_file(self.metadata_file)
            if is_valid:
                self.logger.info("Metadata file integrity: OK")
            else:
                self.logger.warning("Metadata file integrity: FAILED")
            return is_valid
        except Exception as e:
            self.logger.error(f"Error verifying metadata integrity: {e}")
            return False


    def mark_image_seen(self, index: int) -> bool:
        """Mark specific image as seen"""
        if 0 <= index < len(self.images):
            if self.images[index].unseen:
                self.images[index].unseen = False
                self._save_metadata()  # Persistieren der Änderung
                self.logger.debug(f"Marked image {index} as seen: {self.images[index].src}")
                return True
            else:
                self.logger.debug(f"Image {index} was already seen")
                return False
        else:
            self.logger.warning(f"Cannot mark image {index} as seen: index out of range")
            return False

    def mark_images_seen(self, indices: List[int]) -> int:
        """Mark multiple images as seen, returns count of newly marked images"""
        marked_count = 0
        changes_made = False
        
        for index in indices:
            if 0 <= index < len(self.images):
                if self.images[index].unseen:
                    self.images[index].unseen = False
                    marked_count += 1
                    changes_made = True
                    self.logger.debug(f"Marked image {index} as seen: {self.images[index].src}")
        
        if changes_made:
            self._save_metadata()  # Einmal speichern für alle Änderungen
            self.logger.info(f"Marked {marked_count} images as seen")
        
        return marked_count

    def get_unseen_images(self) -> List[int]:
        """Get list of indices of unseen images"""
        unseen_indices = []
        for i, image in enumerate(self.images):
            if image.unseen:
                unseen_indices.append(i)
        return unseen_indices

    def reset_all_unseen(self) -> int:
        """Reset all images to unseen status (for testing/debugging)"""
        reset_count = 0
        for image in self.images:
            if not image.unseen:
                image.unseen = True
                reset_count += 1
        
        if reset_count > 0:
            self._save_metadata()
            self.logger.info(f"Reset {reset_count} images to unseen status")
        
        return reset_count

    def get_seen_count(self) -> int:
        """Get number of seen images"""
        try:
            seen_count = sum(1 for img in self.images if not img.unseen)
            return seen_count
        except Exception as e:
            self.logger.error(f"Error counting seen images: {e}")
            return 0

    def debug_unseen_status(self):
        """Debug method to show unseen status of all images"""
        self.logger.info("=== UNSEEN STATUS DEBUG ===")
        total = len(self.images)
        unseen_count = 0
        
        for i, image in enumerate(self.images):
            status = "UNSEEN" if image.unseen else "SEEN"
            self.logger.info(f"Image {i}: {status} - {Path(image.src).name}")
            if image.unseen:
                unseen_count += 1
        
        self.logger.info(f"Total: {total}, Unseen: {unseen_count}, Seen: {total - unseen_count}")
        self.logger.info("=== END DEBUG ===")


    def get_image_stats(self) -> Dict[str, int]:
        """Get comprehensive image statistics"""
        total = len(self.images)
        unseen = self.get_unseen_count()
        seen = self.get_seen_count()
        
        return {
            'total_images': total,
            'seen_images': seen,
            'unseen_images': unseen,
            'seen_percentage': round((seen / total * 100) if total > 0 else 0, 1)
        } 

if __name__ == "__main__":
    # Test image manager
    from config import TeleFrameConfig

    config = TeleFrameConfig()
    manager = ImageManager(config)

    print(f"Loaded {manager.get_image_count()} images")
    print(f"Unseen: {manager.get_unseen_count()}")
