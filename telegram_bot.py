# telegram_bot.py - Enhanced with Update Recovery System
"""
Enhanced Telegram bot with robust update recovery for offline periods
Handles missed updates during bot downtime (up to 24 hours)
"""

import asyncio
import json
import logging
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any

from telegram import Update, Bot
from telegram.ext import (
    Application, 
    CommandHandler, 
    MessageHandler, 
    filters,
    ContextTypes
)

from telegram.error import (
    Conflict,
    Forbidden,
    BadRequest,
    TimedOut,
    NetworkError,
    TelegramError
)


class UpdateRecoveryManager:
    """Manages persistent update tracking and recovery"""
    
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.recovery")
        
        # State file for persistent update tracking
        self.state_file = Path("data/bot_state.json")
        self.state_file.parent.mkdir(exist_ok=True)
        
        # Recovery statistics
        self.recovery_stats = {
            "last_recovery": None,
            "updates_recovered": 0,
            "total_recoveries": 0,
            "last_update_id": 0,
            "bot_start_time": None
        }
        
        # Load persistent state
        self._load_state()
    
    def _load_state(self):
        """Load persistent bot state from file"""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    data = json.load(f)
                
                self.recovery_stats.update(data)
                self.logger.info(f"Loaded bot state - Last update ID: {self.recovery_stats['last_update_id']}")
                
            except Exception as e:
                self.logger.error(f"Error loading bot state: {e}")
                self._create_default_state()
        else:
            self._create_default_state()
    
    def _create_default_state(self):
        """Create default state file"""
        self.recovery_stats = {
            "last_recovery": None,
            "updates_recovered": 0,
            "total_recoveries": 0,
            "last_update_id": 0,
            "bot_start_time": datetime.now().isoformat()
        }
        self._save_state()
        self.logger.info("Created new bot state file")
    
    def _save_state(self):
        """Save current state to file"""
        try:
            with open(self.state_file, 'w') as f:
                json.dump(self.recovery_stats, f, indent=2, default=str)
        except Exception as e:
            self.logger.error(f"Error saving bot state: {e}")
    
    def update_last_update_id(self, update_id: int):
        """Update the last processed update ID"""
        if update_id > self.recovery_stats['last_update_id']:
            self.recovery_stats['last_update_id'] = update_id
            self._save_state()
    
    def get_recovery_offset(self) -> Optional[int]:
        """Get the offset for update recovery"""
        last_id = self.recovery_stats['last_update_id']
        if last_id > 0:
            return last_id + 1  # Next update after last processed
        return None
    
    def record_recovery(self, updates_count: int):
        """Record successful recovery statistics"""
        self.recovery_stats['last_recovery'] = datetime.now().isoformat()
        self.recovery_stats['updates_recovered'] = updates_count
        self.recovery_stats['total_recoveries'] += 1
        self._save_state()
        
        self.logger.info(f"Recovery completed: {updates_count} updates processed")
    
    def get_recovery_stats(self) -> Dict[str, Any]:
        """Get recovery statistics"""
        stats = self.recovery_stats.copy()
        
        # Calculate uptime
        if stats['bot_start_time']:
            try:
                start_time = datetime.fromisoformat(stats['bot_start_time'])
                uptime = datetime.now() - start_time
                stats['uptime_hours'] = round(uptime.total_seconds() / 3600, 1)
            except:
                stats['uptime_hours'] = 0
        
        return stats


class TeleFrameBot:
    """Enhanced TeleFrame bot with update recovery capabilities"""
    
    def __init__(self, config, image_manager, monitor_controller=None):
        self.config = config
        self.image_manager = image_manager
        self.monitor_controller = monitor_controller
        self.logger = logging.getLogger(__name__)
        
        # NEW: Update recovery manager
        self.recovery_manager = UpdateRecoveryManager(config)
        
        self.application: Optional[Application] = None
        self.bot: Optional[Bot] = None
        
        # Bot state
        self.running = False
        self.startup_time = time.time()
        self.error_count = 0
        self.max_errors = 20
        
        # Rate limiting
        self.last_message_time = {}
        self.rate_limit_window = 60
        self.max_messages_per_window = 10
        
        # NEW: Update processing statistics
        self.update_stats = {
            "total_updates": 0,
            "photos_processed": 0,
            "videos_processed": 0,
            "commands_processed": 0,
            "last_update_time": None
        }
        
        if self.config.bot_token == "bot-disabled":
            self.logger.info("Bot disabled in configuration")
        else:
            self._setup_bot()
    
    def _setup_bot(self):
        """Initialize bot application with error handling"""
        try:
            if not self._validate_token(self.config.bot_token):
                raise ValueError("Invalid bot token format")
            
            # Application builder with enhanced configuration
            self.application = (Application.builder()
                              .token(self.config.bot_token)
                              .concurrent_updates(True)
                              .rate_limiter(None)
                              .read_timeout(30)
                              .write_timeout(30)
                              .connect_timeout(30)
                              .pool_timeout(30)
                              .build())
            
            self.bot = self.application.bot
            
            # Add handlers
            self._add_handlers()
            
            # Add error handler
            self.application.add_error_handler(self._error_handler)
            
            self.logger.info("Telegram bot initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Error setting up bot: {e}")
            raise
    
    def _validate_token(self, token: str) -> bool:
        """Validate bot token format"""
        if not token or token == "YOUR_BOT_TOKEN_HERE":
            return False
        
        parts = token.split(':')
        if len(parts) != 2:
            return False
        
        try:
            int(parts[0])
            return len(parts[1]) >= 35
        except ValueError:
            return False
    
    def _add_handlers(self):
        """Add command and message handlers"""
        app = self.application
        
        # Basic commands
        app.add_handler(CommandHandler("start", self._cmd_start))
        app.add_handler(CommandHandler("help", self._cmd_help))
        app.add_handler(CommandHandler("status", self._cmd_status))
        app.add_handler(CommandHandler("info", self._cmd_info))
        app.add_handler(CommandHandler("ping", self._cmd_ping))
        app.add_handler(CommandHandler("stats", self._cmd_stats))
        app.add_handler(CommandHandler("restart", self._cmd_restart))
        
        # Monitor control commands
        app.add_handler(CommandHandler("monitor", self._cmd_monitor))
        app.add_handler(CommandHandler("schedule", self._cmd_schedule))
        
        # NEW: Recovery commands
        app.add_handler(CommandHandler("recovery", self._cmd_recovery))
        
        # Message handlers
        app.add_handler(MessageHandler(filters.PHOTO, self._handle_photo))
        app.add_handler(MessageHandler(filters.VIDEO, self._handle_video))
        app.add_handler(MessageHandler(filters.Document.ALL, self._handle_document))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_text))
        
        self.logger.debug("Bot handlers registered")
    
    async def start(self):
        """Start the bot with update recovery"""
        if not self.application:
            self.logger.warning("Bot not configured")
            return
        
        try:
            await self._test_bot_connection()
            await self.application.initialize()
            await self.application.start()
            
            # NEW: Perform update recovery before starting polling
            await self._perform_update_recovery()
            
            await self._start_polling_with_retry()
            
            self.running = True
            
            bot_info = await self.bot.get_me()
            self.logger.info(f"✅ Bot started successfully: @{bot_info.username}")
            
            # Update recovery stats
            self.recovery_manager.recovery_stats['bot_start_time'] = datetime.now().isoformat()
            self.recovery_manager._save_state()
            
            security_logger = logging.getLogger("teleframe.security")
            security_logger.info(f"Bot started: @{bot_info.username}, ID: {bot_info.id}")
            
        except Exception as e:
            self.logger.error(f"❌ Error starting bot: {e}")
            await self._handle_startup_error(e)
            raise
    
    async def _perform_update_recovery(self):
        """Recover missed updates from Telegram"""
        self.logger.info("🔄 Checking for missed updates...")
        
        try:
            # Get recovery offset
            offset = self.recovery_manager.get_recovery_offset()
            
            if offset is None:
                self.logger.info("No previous update ID found - starting fresh")
                return
            
            # Calculate maximum recovery time (24 hours)
            max_recovery_time = datetime.now() - timedelta(hours=24)
            
            # Get pending updates
            self.logger.info(f"Fetching updates from offset {offset}...")
            updates = await self._get_pending_updates(offset)
            
            if not updates:
                self.logger.info("No missed updates found")
                return
            
            # Filter updates by age (keep only < 24 hours)
            recent_updates = self._filter_recent_updates(updates, max_recovery_time)
            
            if not recent_updates:
                self.logger.info("All missed updates are too old (>24h) - skipping")
                return
            
            # Process recovered updates
            self.logger.info(f"Processing {len(recent_updates)} recovered updates...")
            processed_count = await self._process_recovered_updates(recent_updates)
            
            # Record recovery statistics
            self.recovery_manager.record_recovery(processed_count)
            
            self.logger.info(f"✅ Update recovery completed: {processed_count} updates processed")
            
        except Exception as e:
            self.logger.error(f"❌ Update recovery failed: {e}")
            # Continue with normal operation even if recovery fails
    
    async def _get_pending_updates(self, offset: int) -> List[Update]:
        """Get pending updates from Telegram"""
        try:
            # Use getUpdates with offset to get missed updates
            raw_updates = await self.bot.get_updates(
                offset=offset,
                limit=100,  # Process in batches
                timeout=10,
                allowed_updates=None  # All update types
            )
            
            # Convert to Update objects
            updates = []
            for raw_update in raw_updates:
                try:
                    update = Update.de_json(raw_update.to_dict(), self.bot)
                    if update:
                        updates.append(update)
                except Exception as e:
                    self.logger.warning(f"Failed to parse update: {e}")
            
            return updates
            
        except Exception as e:
            self.logger.error(f"Error fetching pending updates: {e}")
            return []
    
    def _filter_recent_updates(self, updates: List[Update], cutoff_time: datetime) -> List[Update]:
        """Filter updates to keep only recent ones (< 24 hours)"""
        recent_updates = []
        
        for update in updates:
            try:
                # Get update timestamp
                update_time = None
                
                if update.message:
                    update_time = update.message.date
                elif update.edited_message:
                    update_time = update.edited_message.date
                elif update.callback_query:
                    update_time = update.callback_query.message.date if update.callback_query.message else None
                
                # Keep update if it's recent enough
                if update_time and update_time >= cutoff_time:
                    recent_updates.append(update)
                else:
                    self.logger.debug(f"Skipping old update {update.update_id}")
                    
            except Exception as e:
                self.logger.warning(f"Error filtering update {update.update_id}: {e}")
                # Include update if we can't determine age
                recent_updates.append(update)
        
        return recent_updates
    
    async def _process_recovered_updates(self, updates: List[Update]) -> int:
        """Process recovered updates sequentially"""
        processed_count = 0
        
        for update in updates:
            try:
                self.logger.debug(f"Processing recovered update {update.update_id}")
                
                # Process update through normal handlers
                await self._process_single_update(update)
                
                # Update last processed ID
                self.recovery_manager.update_last_update_id(update.update_id)
                
                processed_count += 1
                
                # Small delay between updates to prevent overwhelming
                await asyncio.sleep(0.1)
                
            except Exception as e:
                self.logger.error(f"Error processing recovered update {update.update_id}: {e}")
                # Continue with next update
        
        return processed_count
    
    async def _process_single_update(self, update: Update):
        """Process a single update through the normal handler system"""
        try:
            # Create a minimal context for the update
            context = ContextTypes.DEFAULT_TYPE(self.application)
            
            # Route to appropriate handler
            if update.message:
                await self._route_message(update, context)
            elif update.edited_message:
                # Handle edited messages if needed
                pass
            elif update.callback_query:
                # Handle callback queries if needed
                pass
            
            # Update processing statistics
            self.update_stats['total_updates'] += 1
            self.update_stats['last_update_time'] = datetime.now().isoformat()
            
        except Exception as e:
            self.logger.error(f"Error processing update {update.update_id}: {e}")
    
    async def _route_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Route message to appropriate handler"""
        message = update.message
        
        if not message:
            return
        
        # Check authorization
        if not self._is_authorized(message.chat.id):
            await self._send_unauthorized_message(update)
            return
        
        try:
            # Route based on message type
            if message.photo:
                await self._handle_photo(update, context)
                self.update_stats['photos_processed'] += 1
            elif message.video:
                await self._handle_video(update, context)
                self.update_stats['videos_processed'] += 1
            elif message.document:
                await self._handle_document(update, context)
            elif message.text:
                if message.text.startswith('/'):
                    await self._handle_command(update, context)
                    self.update_stats['commands_processed'] += 1
                else:
                    await self._handle_text(update, context)
            
        except Exception as e:
            self.logger.error(f"Error routing message: {e}")
    
    async def _handle_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle command messages during recovery"""
        command = update.message.text.split()[0].lower()
        
        # Map commands to handlers
        command_handlers = {
            '/start': self._cmd_start,
            '/help': self._cmd_help,
            '/status': self._cmd_status,
            '/info': self._cmd_info,
            '/ping': self._cmd_ping,
            '/stats': self._cmd_stats,
            '/monitor': self._cmd_monitor,
            '/schedule': self._cmd_schedule,
            '/recovery': self._cmd_recovery,
        }
        
        handler = command_handlers.get(command)
        if handler:
            await handler(update, context)
        else:
            self.logger.debug(f"Unknown command in recovery: {command}")
    
    async def _test_bot_connection(self):
        """Test bot connection and token validity"""
        try:
            test_bot = Bot(token=self.config.bot_token)
            bot_info = await test_bot.get_me()
            self.logger.info(f"🔍 Bot token valid: @{bot_info.username}")
            
        except Forbidden:
            raise ValueError("❌ Invalid bot token - check config.toml")
        except NetworkError as e:
            raise ConnectionError(f"❌ Network error: {e}")
        except Exception as e:
            raise RuntimeError(f"❌ Bot connection test failed: {e}")
    
    async def _start_polling_with_retry(self, max_retries: int = 5):
        """Start polling with conflict resolution"""
        for attempt in range(max_retries):
            try:
                await self.application.updater.start_polling(
                    drop_pending_updates=True  # We handle recovery manually
                )
                return
                
            except Conflict as e:
                self.logger.warning(f"🔄 Bot conflict detected (attempt {attempt + 1}/{max_retries})")
                
                if attempt == max_retries - 1:
                    raise RuntimeError("❌ Bot conflict: Another instance is running")
                
                wait_time = 15 * (2 ** attempt)
                self.logger.info(f"   Waiting {wait_time}s before retry...")
                await asyncio.sleep(wait_time)
                
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                await asyncio.sleep(5)
    
    async def _handle_startup_error(self, error: Exception):
        """Handle startup errors with helpful messages"""
        error_msg = str(error).lower()
        
        if "forbidden" in error_msg or "unauthorized" in error_msg:
            self.logger.error("🔑 Bot Token Error - Check config.toml")
        elif "conflict" in error_msg:
            self.logger.error("⚡ Bot Conflict - Another instance running")
        elif "network" in error_msg:
            self.logger.error("🌐 Network Error - Check connection")
        else:
            self.logger.error(f"❓ Unknown bot error: {error}")
    
    async def stop(self):
        """Stop the bot gracefully"""
        if not self.application or not self.running:
            return
        
        try:
            self.running = False
            self.logger.info("🛑 Stopping Telegram bot...")
            
            if self.application.updater.running:
                await self.application.updater.stop()
            
            await self.application.stop()
            await self.application.shutdown()
            
            self.logger.info("✅ Bot stopped successfully")
            
        except Exception as e:
            self.logger.error(f"Error stopping bot: {e}")
    
    # NEW: Recovery command
    async def _cmd_recovery(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /recovery command (admin only)"""
        try:
            chat_id = update.effective_chat.id
            
            if not self._is_admin(chat_id):
                await update.message.reply_text("🔒 Admin command only")
                return
            
            args = context.args
            
            if not args:
                # Show recovery statistics
                stats = self.recovery_manager.get_recovery_stats()
                
                msg = f"🔄 **Update Recovery Statistics**\n\n"
                msg += f"**Last Update ID:** {stats['last_update_id']}\n"
                msg += f"**Total Recoveries:** {stats['total_recoveries']}\n"
                msg += f"**Last Recovery:** {stats['last_recovery'] or 'Never'}\n"
                msg += f"**Updates Recovered:** {stats['updates_recovered']}\n"
                msg += f"**Bot Uptime:** {stats.get('uptime_hours', 0)}h\n"
                
                msg += f"\n**Processing Stats:**\n"
                msg += f"• Total Updates: {self.update_stats['total_updates']}\n"
                msg += f"• Photos: {self.update_stats['photos_processed']}\n"
                msg += f"• Videos: {self.update_stats['videos_processed']}\n"
                msg += f"• Commands: {self.update_stats['commands_processed']}\n"
                
                await update.message.reply_text(msg, parse_mode='Markdown')
                
            elif args[0] == "test":
                # Test recovery system
                await update.message.reply_text("🔄 Testing recovery system...")
                
                try:
                    offset = self.recovery_manager.get_recovery_offset()
                    updates = await self._get_pending_updates(offset or 0)
                    
                    msg = f"✅ **Recovery Test Results**\n\n"
                    msg += f"**Current Offset:** {offset or 'None'}\n"
                    msg += f"**Pending Updates:** {len(updates)}\n"
                    
                    if updates:
                        msg += f"**Update IDs:** {[u.update_id for u in updates[:5]]}"
                        if len(updates) > 5:
                            msg += f"... and {len(updates) - 5} more"
                    
                    await update.message.reply_text(msg, parse_mode='Markdown')
                    
                except Exception as e:
                    await update.message.reply_text(f"❌ Recovery test failed: {e}")
                    
            elif args[0] == "reset":
                # Reset recovery state
                self.recovery_manager._create_default_state()
                await update.message.reply_text("✅ Recovery state reset")
                
            else:
                await update.message.reply_text("❓ Usage: `/recovery [test|reset]`")
                
        except Exception as e:
            self.logger.error(f"Error in recovery command: {e}")
            await self._send_error_message(update, "recovery command")
    
    # Override update handling to track update IDs
    async def _handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle photo messages with update ID tracking"""
        try:
            # Update last processed ID
            self.recovery_manager.update_last_update_id(update.update_id)
            
            # Process normally
            await self._process_photo_message(update, context)
            
        except Exception as e:
            self.logger.error(f"Error handling photo: {e}")
    
    async def _process_photo_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Process photo message (existing logic)"""
        if not self._is_authorized(update.effective_chat.id):
            await self._send_unauthorized_message(update)
            return
        
        # Get the largest photo
        photo = update.message.photo[-1]
        
        # Check file size
        if photo.file_size and photo.file_size > self.config.max_file_size:
            await update.message.reply_text(
                f"❌ Photo too large. Max: {self.config.max_file_size // (1024*1024)}MB"
            )
            return
        
        # Download with timeout
        file_path = await asyncio.wait_for(
            self._download_file(photo.file_id, "photo", ".jpg"),
            timeout=30
        )
        
        if not file_path:
            await update.message.reply_text("❌ Error downloading photo")
            return
        
        # Add to image manager
        success = self.image_manager.add_image(
            file_path=file_path,
            sender=self._get_sender_name(update),
            caption=update.message.caption or "",
            chat_id=update.effective_chat.id,
            chat_name=update.effective_chat.title or update.effective_chat.first_name or "Unknown",
            message_id=update.message.message_id
        )
        
        if success:
            await update.message.reply_text("📸 Photo added to slideshow! ✅")
            self.logger.info(f"Photo added from {self._get_sender_name(update)}")
            
            # Log to recovery for debugging
            self.logger.debug(f"Processed photo from update {update.update_id}")
        else:
            await update.message.reply_text("❌ Error adding photo to slideshow")
            file_path.unlink(missing_ok=True)
    
    # [Include all other existing methods from the previous telegram_bot.py]
    # ... (rest of the existing methods remain the same)
    
    def _is_authorized(self, chat_id: int) -> bool:
        """Check if chat is authorized with rate limiting"""
        current_time = time.time()
        
        if chat_id in self.last_message_time:
            messages_in_window = [
                t for t in self.last_message_time[chat_id] 
                if current_time - t < self.rate_limit_window
            ]
            
            if len(messages_in_window) >= self.max_messages_per_window:
                self.logger.warning(f"Rate limit exceeded for chat {chat_id}")
                return False
        else:
            self.last_message_time[chat_id] = []
        
        self.last_message_time[chat_id].append(current_time)
        
        self.last_message_time[chat_id] = [
            t for t in self.last_message_time[chat_id] 
            if current_time - t < self.rate_limit_window
        ]
        
        return self.config.is_chat_whitelisted(chat_id)
    
    def _is_admin(self, chat_id: int) -> bool:
        """Check if user is admin"""
        return self.config.is_admin(chat_id)
    
    async def _send_unauthorized_message(self, update: Update):
        """Send unauthorized access message"""
        chat_id = update.effective_chat.id
        
        try:
            await update.message.reply_text(
                f"🚫 **Access Denied**\n\n"
                f"Chat ID: `{chat_id}`\n"
                f"Contact admin to whitelist your chat.\n\n"
                f"ℹ️ Send this Chat ID to the TeleFrame admin.",
                parse_mode='Markdown'
            )
        except Exception as e:
            self.logger.error(f"Error sending unauthorized message: {e}")
        
        security_logger = logging.getLogger("teleframe.security")
        security_logger.warning(f"Unauthorized access: Chat {chat_id}")
    
    async def _error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE):
        """Global error handler for the bot"""
        self.error_count += 1
        error = context.error
        self.logger.error(f"Bot error #{self.error_count}: {error}")
        
        if self.error_count > self.max_errors:
            security_logger = logging.getLogger("teleframe.security")
            security_logger.error(f"Too many bot errors: {self.error_count}")
    
    def _get_sender_name(self, update: Update) -> str:
        """Get sender display name"""
        user = update.effective_user
        chat = update.effective_chat
        
        if user:
            if user.first_name and user.last_name:
                return f"{user.first_name} {user.last_name}"
            elif user.first_name:
                return user.first_name
            elif user.username:
                return f"@{user.username}"
        
        if chat.title:
            return chat.title
        
        return "Unknown"
    
    async def _send_error_message(self, update: Update, operation: str):
        """Send generic error message to user"""
        try:
            await update.message.reply_text(
                f"❌ Error processing {operation}\n"
                f"Please try again or contact admin."
            )
        except Exception:
            pass
    
    async def _download_file(self, file_id: str, file_type: str, extension: str) -> Optional[Path]:
        """Download file from Telegram with retry logic"""
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                file_info = await self.bot.get_file(file_id)
                
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"{timestamp}_{file_type}_{file_id[:8]}{extension}"
                file_path = self.config.image_folder / filename
                
                await file_info.download_to_drive(file_path)
                
                self.logger.debug(f"Downloaded file: {file_path}")
                return file_path
                
            except Exception as e:
                self.logger.warning(f"Download attempt {attempt + 1}/{max_retries} failed: {e}")
                if attempt == max_retries - 1:
                    self.logger.error(f"Failed to download file {file_id} after {max_retries} attempts")
                    return None
                
                await asyncio.sleep(2 ** attempt)
        
        return None
    
    # Placeholder methods for existing functionality
    # (Include all other methods from the original telegram_bot.py)
    
    async def _cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        self.recovery_manager.update_last_update_id(update.update_id)
        
        chat_id = update.effective_chat.id
        
        if not self._is_authorized(chat_id):
            await self._send_unauthorized_message(update)
            return
        
        uptime = int(time.time() - self.startup_time)
        
        welcome_msg = (
            f"🖼️ **TeleFrame Active** ✅\n\n"
            f"📊 **Status:**\n"
            f"• Uptime: {uptime // 3600}h {(uptime % 3600) // 60}m\n"
            f"• Images: {self.image_manager.get_image_count()}\n"
            f"• Unseen: {self.image_manager.get_unseen_count()}\n\n"
            f"📨 Send photos/videos to display them!\n\n"
            f"⚙️ **Commands:**\n"
            f"/help - Show help\n"
            f"/status - Frame status\n"
            f"/info - Chat info\n"
            f"/ping - Test connection"
        )
        
        # Add monitor info if available
        if self.monitor_controller:
            status = self.monitor_controller.get_status()
            welcome_msg += f"\n\n🖥️ **Monitor:** {status['state']}"
            if status['enabled']:
                welcome_msg += f" (Next: {status['next_change']})"
        
        await update.message.reply_text(welcome_msg, parse_mode='Markdown')
        self.logger.info(f"Start command from chat {chat_id}")
    
    # ... (include all other existing command methods)


if __name__ == "__main__":
    """Test the enhanced bot with recovery system"""
    import sys
    from config import TeleFrameConfig
    from image_manager import ImageManager
    
    async def test_bot():
        config = TeleFrameConfig()
        if config.bot_token == "bot-disabled":
            print("❌ Bot token not configured")
            return
        
        manager = ImageManager(config)
        monitor_controller = None
        
        if config.toggle_monitor:
            from monitor_control import MonitorController
            monitor_controller = MonitorController(config)
        
        bot = TeleFrameBot(config, manager, monitor_controller)
        
        try:
            await bot.start()
            print("✅ Enhanced bot started successfully with recovery system")
            print("🔄 Update recovery is active - missed messages will be recovered")
            print("Press Ctrl+C to stop.")
            
            while bot.running:
                await asyncio.sleep(1)
                
        except KeyboardInterrupt:
            print("🛑 Stopping bot...")
        except Exception as e:
            print(f"❌ Bot error: {e}")
        finally:
            await bot.stop()
    
    asyncio.run(test_bot())
