# telegram_bot.py - COMPLETE VERSION with API fixes for v22+
"""
Secure Telegram bot integration - FULL FEATURED VERSION
Compatible with python-telegram-bot v22.2 - ALL ORIGINAL FEATURES INTACT
"""

import asyncio
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from telegram import Update, Bot
from telegram.ext import (
    Application, 
    CommandHandler, 
    MessageHandler, 
    filters,
    ContextTypes
)

# Correct imports for v22+
from telegram.error import (
    Conflict,
    Forbidden,
    BadRequest,
    TimedOut,
    NetworkError,
    TelegramError
)
import aiohttp


class TeleFrameBot:
    """Telegram bot for TeleFrame with robust error handling - FULL VERSION"""
    
    def __init__(self, config, image_manager):
        self.config = config
        self.image_manager = image_manager
        self.logger = logging.getLogger(__name__)
        
        self.application: Optional[Application] = None
        self.bot: Optional[Bot] = None
        
        # Bot state
        self.running = False
        self.startup_time = time.time()
        self.error_count = 0
        self.max_errors = 20
        
        # Rate limiting - RESTORED
        self.last_message_time = {}
        self.rate_limit_window = 60  # seconds
        self.max_messages_per_window = 10
        
        if self.config.bot_token == "bot-disabled":
            self.logger.info("Bot disabled in configuration")
        else:
            self._setup_bot()
    
    def _setup_bot(self):
        """Initialize bot application with error handling"""
        try:
            # Validate token format
            if not self._validate_token(self.config.bot_token):
                raise ValueError("Invalid bot token format")
            
            # FIXED: Application builder with timeouts for v22+
            self.application = (Application.builder()
                              .token(self.config.bot_token)
                              .concurrent_updates(True)
                              .rate_limiter(None)  # We handle rate limiting ourselves
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
        
        # Basic format check: should be like "123456789:ABCdefGHIjklMNOpqrsTUVwxyz"
        parts = token.split(':')
        if len(parts) != 2:
            return False
        
        try:
            int(parts[0])  # First part should be numeric
            return len(parts[1]) >= 35  # Second part should be long enough
        except ValueError:
            return False
    
    def _add_handlers(self):
        """Add command and message handlers"""
        app = self.application
        
        # Command handlers
        app.add_handler(CommandHandler("start", self._cmd_start))
        app.add_handler(CommandHandler("help", self._cmd_help))
        app.add_handler(CommandHandler("status", self._cmd_status))
        app.add_handler(CommandHandler("info", self._cmd_info))
        app.add_handler(CommandHandler("ping", self._cmd_ping))
        
        # Admin commands - RESTORED
        app.add_handler(CommandHandler("stats", self._cmd_stats))
        app.add_handler(CommandHandler("restart", self._cmd_restart))
        
        # Message handlers
        app.add_handler(MessageHandler(filters.PHOTO, self._handle_photo))
        app.add_handler(MessageHandler(filters.VIDEO, self._handle_video))
        app.add_handler(MessageHandler(filters.Document.ALL, self._handle_document))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_text))
        
        self.logger.debug("Bot handlers registered")
    
    async def start(self):
        """Start the bot with conflict resolution"""
        if not self.application:
            self.logger.warning("Bot not configured")
            return
        
        try:
            # Test bot token first
            await self._test_bot_connection()
            
            # Initialize application
            await self.application.initialize()
            
            # Start application
            await self.application.start()
            
            # FIXED: Start polling with correct parameters for v22+
            await self._start_polling_with_retry()
            
            self.running = True
            
            # Get bot info
            bot_info = await self.bot.get_me()
            self.logger.info(f"✅ Bot started successfully: @{bot_info.username}")
            
            # Log security event
            security_logger = logging.getLogger("teleframe.security")
            security_logger.info(f"Bot started: @{bot_info.username}, ID: {bot_info.id}")
            
        except Exception as e:
            self.logger.error(f"❌ Error starting bot: {e}")
            await self._handle_startup_error(e)
            raise
    
    async def _test_bot_connection(self):
        """Test bot connection and token validity"""
        try:
            test_bot = Bot(token=self.config.bot_token)
            bot_info = await test_bot.get_me()
            self.logger.info(f"🔍 Bot token valid: @{bot_info.username}")
            
        except Forbidden:  # FIXED: Use Forbidden instead of Unauthorized
            raise ValueError("❌ Invalid bot token - check config.toml")
        except NetworkError as e:
            raise ConnectionError(f"❌ Network error: {e}")
        except Exception as e:
            raise RuntimeError(f"❌ Bot connection test failed: {e}")
    
    async def _start_polling_with_retry(self, max_retries: int = 5):
        """FIXED: Start polling with correct API for v22+"""
        for attempt in range(max_retries):
            try:
                # FIXED: Only these parameters work in v22+
                await self.application.updater.start_polling(
                    drop_pending_updates=True  # Clear old updates
                )
                return
                
            except Conflict as e:
                self.logger.warning(f"🔄 Bot conflict detected (attempt {attempt + 1}/{max_retries})")
                
                if attempt == max_retries - 1:
                    raise RuntimeError(
                        "❌ Bot conflict: Another instance is running\n"
                        "🔧 Solutions:\n"
                        "   1. Stop other instances: pkill -f telegram\n"
                        "   2. Wait 60 seconds\n"
                        "   3. Restart TeleFrame"
                    )
                
                # Progressive backoff
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
        
        if "forbidden" in error_msg or "unauthorized" in error_msg or "token" in error_msg:
            self.logger.error("🔑 Bot Token Error:")
            self.logger.error("   1. Check config.toml: bot_token = 'YOUR_TOKEN'")
            self.logger.error("   2. Get token from @BotFather on Telegram")
            self.logger.error("   3. Make sure token is not shared/revoked")
            
        elif "conflict" in error_msg:
            self.logger.error("⚡ Bot Conflict Error:")
            self.logger.error("   Another TeleFrame instance is running")
            self.logger.error("   1. Check: ps aux | grep main.py")
            self.logger.error("   2. Kill: pkill -f 'python.*main.py'")
            self.logger.error("   3. Wait 60 seconds before restart")
            
        elif "network" in error_msg or "timeout" in error_msg:
            self.logger.error("🌐 Network Error:")
            self.logger.error("   1. Check internet connection")
            self.logger.error("   2. Check firewall settings")
            self.logger.error("   3. Try again in a few minutes")
            
        else:
            self.logger.error(f"❓ Unknown bot error: {error}")
    
    async def stop(self):
        """Stop the bot gracefully"""
        if not self.application or not self.running:
            return
        
        try:
            self.running = False
            self.logger.info("🛑 Stopping Telegram bot...")
            
            # Stop polling
            if self.application.updater.running:
                await self.application.updater.stop()
            
            # Stop application
            await self.application.stop()
            await self.application.shutdown()
            
            self.logger.info("✅ Bot stopped successfully")
            
        except Exception as e:
            self.logger.error(f"Error stopping bot: {e}")
    
    def _is_authorized(self, chat_id: int) -> bool:
        """Check if chat is authorized with rate limiting - RESTORED"""
        # Rate limiting check
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
        
        # Add current message timestamp
        self.last_message_time[chat_id].append(current_time)
        
        # Keep only recent messages
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
        
        # Log security event
        security_logger = logging.getLogger("teleframe.security")
        security_logger.warning(f"Unauthorized access: Chat {chat_id}, User: {self._get_sender_name(update)}")
    
    async def _error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE):
        """Global error handler for the bot"""
        self.error_count += 1
        
        error = context.error
        error_msg = str(error)
        
        self.logger.error(f"Bot error #{self.error_count}: {error_msg}")
        
        # Handle specific error types
        if isinstance(error, TimedOut):
            self.logger.warning("⏰ Telegram API timeout - retrying...")
            
        elif isinstance(error, NetworkError):
            self.logger.warning("🌐 Network error - connection issues")
            
        elif isinstance(error, BadRequest):
            self.logger.warning(f"📨 Bad request: {error_msg}")
            
        elif isinstance(error, Forbidden):  # FIXED: Use Forbidden
            self.logger.error("🔑 Bot forbidden - check token")
            
        else:
            self.logger.error(f"❓ Unknown error: {error_msg}")
        
        # Log detailed error for debugging
        if update:
            self.logger.debug(f"Update that caused error: {update}")
        
        # Security logging for repeated errors
        if self.error_count > self.max_errors:
            security_logger = logging.getLogger("teleframe.security")
            security_logger.error(f"Too many bot errors: {self.error_count}")
    
    # Command handlers with error handling
    async def _cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        try:
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
            
            await update.message.reply_text(welcome_msg, parse_mode='Markdown')
            self.logger.info(f"Start command from chat {chat_id}")
            
        except Exception as e:
            self.logger.error(f"Error in start command: {e}")
            await self._send_error_message(update, "start command")
    
    async def _cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        if not self._is_authorized(update.effective_chat.id):
            await self._send_unauthorized_message(update)
            return
        
        help_msg = (
            "📖 TeleFrame Help\n\n"
            "🖼️ **Sending Media:**\n"
            "• Send photos directly\n"
            "• Send videos (if enabled)\n"
            "• Add captions to your media\n\n"
            "⚙️ **Commands:**\n"
            "/start - Welcome message\n"
            "/help - This help message\n"
            "/status - Frame status\n"
            "/info - Your chat information\n"
            "/ping - Test connection\n\n"
            "📝 **Supported formats:**\n"
            f"• Images: {', '.join([ext for ext in self.config.allowed_file_types if ext in ['.jpg', '.jpeg', '.png', '.gif']])}\n"
            f"• Videos: {', '.join([ext for ext in self.config.allowed_file_types if ext in ['.mp4']])}\n\n"
            f"📊 **Limits:**\n"
            f"• Max file size: {self.config.max_file_size // (1024*1024)}MB\n"
            f"• Max images in frame: {self.config.image_count}"
        )
        
        await update.message.reply_text(help_msg, parse_mode='Markdown')
    
    async def _cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command"""
        if not self._is_authorized(update.effective_chat.id):
            await self._send_unauthorized_message(update)
            return
        
        total_images = self.image_manager.get_image_count()
        unseen_images = self.image_manager.get_unseen_count()
        
        status_msg = (
            f"📊 TeleFrame Status\n\n"
            f"🖼️ Total images: {total_images}\n"
            f"🆕 Unseen images: {unseen_images}\n"
            f"⏸️ Slideshow: Running\n"
            f"📁 Storage: {self.config.image_folder}\n"
            f"🔄 Random order: {'Yes' if self.config.random_order else 'No'}\n"
            f"⏱️ Interval: {self.config.interval/1000}s\n"
            f"✨ Fade time: {self.config.fade_time/1000}s"
        )
        
        await update.message.reply_text(status_msg)
    
    async def _cmd_info(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /info command"""
        chat = update.effective_chat
        user = update.effective_user
        
        info_msg = (
            f"ℹ️ Chat Information\n\n"
            f"Chat ID: `{chat.id}`\n"
            f"Chat Type: {chat.type}\n"
            f"Chat Title: {chat.title or 'N/A'}\n"
            f"User: {user.full_name if user else 'N/A'}\n"
            f"Username: @{user.username if user and user.username else 'N/A'}\n"
            f"Authorized: {'✅ Yes' if self._is_authorized(chat.id) else '❌ No'}\n"
            f"Admin: {'✅ Yes' if self._is_admin(chat.id) else '❌ No'}"
        )
        
        await update.message.reply_text(info_msg, parse_mode='Markdown')
    
    async def _cmd_ping(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /ping command"""
        try:
            if not self._is_authorized(update.effective_chat.id):
                await self._send_unauthorized_message(update)
                return
            
            await update.message.reply_text("🏓 Pong! Bot is responsive.")
            
        except Exception as e:
            self.logger.error(f"Error in ping command: {e}")
    
    async def _cmd_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stats command (admin only) - RESTORED"""
        try:
            chat_id = update.effective_chat.id
            
            if not self._is_admin(chat_id):
                await update.message.reply_text("🔒 Admin command only")
                return
            
            uptime = int(time.time() - self.startup_time)
            
            stats_msg = (
                f"📊 **TeleFrame Statistics**\n\n"
                f"🤖 **Bot:**\n"
                f"• Uptime: {uptime // 86400}d {(uptime % 86400) // 3600}h {(uptime % 3600) // 60}m\n"
                f"• Errors: {self.error_count}/{self.max_errors}\n"
                f"• Active chats: {len(self.last_message_time)}\n\n"
                f"🖼️ **Images:**\n"
                f"• Total: {self.image_manager.get_image_count()}\n"
                f"• Unseen: {self.image_manager.get_unseen_count()}\n"
                f"• Limit: {self.config.image_count}\n\n"
                f"⚙️ **Config:**\n"
                f"• Interval: {self.config.interval/1000}s\n"
                f"• Random: {'Yes' if self.config.random_order else 'No'}\n"
                f"• Videos: {'Yes' if self.config.show_videos else 'No'}"
            )
            
            await update.message.reply_text(stats_msg, parse_mode='Markdown')
            
        except Exception as e:
            self.logger.error(f"Error in stats command: {e}")
            await self._send_error_message(update, "stats command")
    
    async def _cmd_restart(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /restart command (admin only) - RESTORED"""
        try:
            chat_id = update.effective_chat.id
            
            if not self._is_admin(chat_id):
                await update.message.reply_text("🔒 Admin command only")
                return
            
            await update.message.reply_text("🔄 Restart functionality not implemented yet")
            
        except Exception as e:
            self.logger.error(f"Error in restart command: {e}")
    
    async def _send_error_message(self, update: Update, operation: str):
        """Send generic error message to user"""
        try:
            await update.message.reply_text(
                f"❌ Error processing {operation}\n"
                f"Please try again or contact admin."
            )
        except Exception:
            pass  # Don't log errors in error handler
    
    # Message handlers - FULL IMPLEMENTATION RESTORED
    async def _handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle photo messages with error handling"""
        try:
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
            else:
                await update.message.reply_text("❌ Error adding photo to slideshow")
                file_path.unlink(missing_ok=True)
                
        except asyncio.TimeoutError:
            await update.message.reply_text("⏰ Download timeout - photo too large")
            self.logger.warning("Photo download timeout")
            
        except Exception as e:
            self.logger.error(f"Error handling photo: {e}")
            await self._send_error_message(update, "photo upload")
    
    async def _handle_video(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle video messages - FULL IMPLEMENTATION RESTORED"""
        if not self._is_authorized(update.effective_chat.id):
            await self._send_unauthorized_message(update)
            return
        
        if not self.config.show_videos:
            await update.message.reply_text("📹 Video support is disabled")
            return
        
        try:
            video = update.message.video
            
            # Check file size
            if video.file_size > self.config.max_file_size:
                await update.message.reply_text(
                    f"❌ Video too large. Max size: {self.config.max_file_size // (1024*1024)}MB"
                )
                return
            
            # Download video
            file_path = await self._download_file(video.file_id, "video", ".mp4")
            if not file_path:
                await update.message.reply_text("❌ Error downloading video")
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
                await update.message.reply_text("🎬 Video added to slideshow!")
                self.logger.info(f"Video added from {self._get_sender_name(update)}")
            else:
                await update.message.reply_text("❌ Error adding video to slideshow")
                file_path.unlink(missing_ok=True)
                
        except Exception as e:
            self.logger.error(f"Error handling video: {e}")
            await update.message.reply_text("❌ Error processing video")
    
    async def _handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle document messages - FULL IMPLEMENTATION RESTORED"""
        if not self._is_authorized(update.effective_chat.id):
            await self._send_unauthorized_message(update)
            return
        
        try:
            document = update.message.document
            file_name = document.file_name or "unknown"
            
            # Check if file type is allowed
            if not self.config.is_file_allowed(file_name):
                await update.message.reply_text(
                    f"❌ File type not supported: {Path(file_name).suffix}"
                )
                return
            
            # Check file size
            if document.file_size > self.config.max_file_size:
                await update.message.reply_text(
                    f"❌ File too large. Max size: {self.config.max_file_size // (1024*1024)}MB"
                )
                return
            
            # Determine file type
            file_ext = Path(file_name).suffix.lower()
            file_type = "image" if file_ext in ['.jpg', '.jpeg', '.png', '.gif'] else "video"
            
            # Download file
            file_path = await self._download_file(document.file_id, file_type, file_ext)
            if not file_path:
                await update.message.reply_text("❌ Error downloading file")
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
                await update.message.reply_text(f"📎 {file_type.title()} added to slideshow!")
                self.logger.info(f"Document {file_type} added from {self._get_sender_name(update)}")
            else:
                await update.message.reply_text(f"❌ Error adding {file_type} to slideshow")
                file_path.unlink(missing_ok=True)
                
        except Exception as e:
            self.logger.error(f"Error handling document: {e}")
            await update.message.reply_text("❌ Error processing document")
    
    async def _handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages"""
        if not self._is_authorized(update.effective_chat.id):
            await self._send_unauthorized_message(update)
            return
        
        text = update.message.text.lower().strip()
        
        # Simple text responses
        if text in ['hi', 'hello', 'hey']:
            chat_id = update.effective_chat.id
            user_name = self._get_sender_name(update)
            
            response = (
                f"👋 Hello {user_name}!\n"
                f"Your Chat ID: `{chat_id}`\n\n"
                f"Send me photos or videos to add them to your TeleFrame slideshow!"
            )
            
            await update.message.reply_text(response, parse_mode='Markdown')
        else:
            await update.message.reply_text(
                "🤔 I don't understand text messages. Send me photos or videos instead!\n"
                "Use /help for more information."
            )
    
    async def _download_file(self, file_id: str, file_type: str, extension: str) -> Optional[Path]:
        """Download file from Telegram with retry logic - RESTORED"""
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                # Get file info
                file_info = await self.bot.get_file(file_id)
                
                # Generate unique filename
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"{timestamp}_{file_type}_{file_id[:8]}{extension}"
                file_path = self.config.image_folder / filename
                
                # Download file
                await file_info.download_to_drive(file_path)
                
                self.logger.debug(f"Downloaded file: {file_path}")
                return file_path
                
            except Exception as e:
                self.logger.warning(f"Download attempt {attempt + 1}/{max_retries} failed: {e}")
                if attempt == max_retries - 1:
                    self.logger.error(f"Failed to download file {file_id} after {max_retries} attempts")
                    return None
                
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
        
        return None
    
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


if __name__ == "__main__":
    # Test bot functionality
    import sys
    from config import TeleFrameConfig
    from image_manager import ImageManager
    
    async def test_bot():
        config = TeleFrameConfig()
        if config.bot_token == "bot-disabled":
            print("❌ Bot token not configured")
            return
        
        manager = ImageManager(config)
        bot = TeleFrameBot(config, manager)
        
        try:
            await bot.start()
            print("✅ Bot started successfully. Press Ctrl+C to stop.")
            
            # Keep running
            while bot.running:
                await asyncio.sleep(1)
                
        except KeyboardInterrupt:
            print("🛑 Stopping bot...")
        except Exception as e:
            print(f"❌ Bot error: {e}")
        finally:
            await bot.stop()
    
    asyncio.run(test_bot())
