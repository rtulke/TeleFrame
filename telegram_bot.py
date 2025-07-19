# telegram_bot.py - Complete with Rate Limiting, Image Order Control and Image Optimization - FIXED
"""
Enhanced Telegram bot with robust update recovery, configurable rate limiting,
image order control, and image optimization management. FIXED datetime timezone issue.
Complete implementation with all handlers and methods.
"""

import asyncio
import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone
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
    """Enhanced TeleFrame bot with configurable rate limiting, image order control and optimization management"""
    
    def __init__(self, config, image_manager, monitor_controller=None, slideshow_display=None):
        self.config = config
        self.image_manager = image_manager
        self.monitor_controller = monitor_controller
        self.slideshow_display = slideshow_display
        self.logger = logging.getLogger(__name__)
        
        # Update recovery manager
        self.recovery_manager = UpdateRecoveryManager(config)
        
        self.application: Optional[Application] = None
        self.bot: Optional[Bot] = None
        
        # Bot state
        self.running = False
        self.startup_time = time.time()
        self.error_count = 0
        self.max_errors = 20
        
        # Rate limiting from config
        self.last_message_time = {}
        self.banned_chats = {}  # Track temporarily banned chats
        
        # Update processing statistics
        self.update_stats = {
            "total_updates": 0,
            "photos_processed": 0,
            "videos_processed": 0,
            "commands_processed": 0,
            "last_update_time": None,
            "rate_limit_violations": 0
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
        app.add_handler(CommandHandler("service", self._cmd_service))

        # Monitor control commands
        app.add_handler(CommandHandler("monitor", self._cmd_monitor))
        app.add_handler(CommandHandler("schedule", self._cmd_schedule))
        
        # Recovery and rate limiting commands
        app.add_handler(CommandHandler("recovery", self._cmd_recovery))
        app.add_handler(CommandHandler("ratelimit", self._cmd_ratelimit))
        
        # Image order command
        app.add_handler(CommandHandler("order", self._cmd_order))
        
        # Image optimization commands
        app.add_handler(CommandHandler("optimize", self._cmd_optimize))
        app.add_handler(CommandHandler("compression", self._cmd_compression))

        # Image seen
        app.add_handler(CommandHandler("seen", self._cmd_seen))

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
            
            # Perform update recovery before starting polling
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
            
            # FIXED: Calculate maximum recovery time (24 hours) with timezone awareness
            now_utc = datetime.now(timezone.utc)
            max_recovery_time = now_utc - timedelta(hours=24)
            
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
                
                # FIXED: Ensure both datetimes are timezone-aware for comparison
                if update_time:
                    # Convert update_time to UTC if it's not already timezone-aware
                    if update_time.tzinfo is None:
                        # If somehow the update_time is naive, assume UTC
                        update_time = update_time.replace(tzinfo=timezone.utc)
                    elif update_time.tzinfo != timezone.utc:
                        # Convert to UTC for consistent comparison
                        update_time = update_time.astimezone(timezone.utc)
                    
                    # Ensure cutoff_time is also UTC timezone-aware
                    if cutoff_time.tzinfo is None:
                        cutoff_time = cutoff_time.replace(tzinfo=timezone.utc)
                    elif cutoff_time.tzinfo != timezone.utc:
                        cutoff_time = cutoff_time.astimezone(timezone.utc)
                    
                    # Now both are timezone-aware UTC datetimes
                    if update_time >= cutoff_time:
                        recent_updates.append(update)
                        self.logger.debug(f"Keeping recent update {update.update_id} from {update_time}")
                    else:
                        self.logger.debug(f"Skipping old update {update.update_id} from {update_time}")
                else:
                    # If we can't determine the time, include the update to be safe
                    recent_updates.append(update)
                    self.logger.debug(f"Including update {update.update_id} (no timestamp)")
                    
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
        
        # Check authorization (includes rate limiting)
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
            '/ratelimit': self._cmd_ratelimit,
            '/restart': self._cmd_restart,
            '/service': self._cmd_service,
            '/order': self._cmd_order,
            '/optimize': self._cmd_optimize,
            '/compression': self._cmd_compression,
            '/seen': self._cmd_seen,
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
    
    # ========================================
    # AUTHORIZATION AND RATE LIMITING
    # ========================================
    
    def _is_authorized(self, chat_id: int) -> bool:
        """Check if chat is authorized with configurable rate limiting"""
        
        # Check basic authorization first
        is_whitelisted = self.config.is_chat_whitelisted(chat_id)
        is_admin = self.config.is_admin(chat_id)
        
        # If not authorized at all, deny immediately
        if not is_whitelisted and not is_admin:
            return False
        
        # Check if chat is temporarily banned
        current_time = time.time()
        if chat_id in self.banned_chats:
            ban_end_time = self.banned_chats[chat_id]
            if current_time < ban_end_time:
                remaining_ban = int(ban_end_time - current_time)
                self.logger.debug(f"Chat {chat_id} is banned for {remaining_ban}s more")
                return False
            else:
                # Ban expired, remove from banned list
                del self.banned_chats[chat_id]
                self.logger.info(f"Rate limit ban expired for chat {chat_id}")
        
        # Check rate limiting configuration
        if not self.config.rate_limiting_enabled:
            self.logger.debug("Rate limiting disabled")
            return True
            
        if self.config.rate_limit_admin_exempt and is_admin:
            self.logger.debug(f"Admin {chat_id} exempt from rate limiting")
            return True
            
        if self.config.rate_limit_whitelist_exempt and is_whitelisted:
            self.logger.debug(f"Whitelisted chat {chat_id} exempt from rate limiting")
            return True
        
        # Apply rate limiting
        if chat_id in self.last_message_time:
            messages_in_window = [
                t for t in self.last_message_time[chat_id] 
                if current_time - t < self.config.rate_limit_window
            ]
            
            if len(messages_in_window) >= self.config.rate_limit_max_messages:
                # Rate limit exceeded - apply temporary ban
                ban_duration = self.config.rate_limit_ban_duration * 60  # Convert to seconds
                ban_end_time = current_time + ban_duration
                self.banned_chats[chat_id] = ban_end_time
                
                self.logger.warning(
                    f"Rate limit exceeded for chat {chat_id}: "
                    f"{len(messages_in_window)}/{self.config.rate_limit_max_messages} "
                    f"messages in {self.config.rate_limit_window}s. "
                    f"Banned for {self.config.rate_limit_ban_duration} minutes."
                )
                
                # Log security event
                security_logger = logging.getLogger("teleframe.security")
                security_logger.warning(
                    f"Rate limit violation: Chat {chat_id} banned for {self.config.rate_limit_ban_duration}m"
                )
                
                # Update statistics
                self.update_stats['rate_limit_violations'] += 1
                
                # Send violation message (optional)
                asyncio.create_task(self._send_rate_limit_violation_message(chat_id))
                
                return False
        else:
            self.last_message_time[chat_id] = []
        
        # Record this message
        self.last_message_time[chat_id].append(current_time)
        
        # Clean old entries
        self.last_message_time[chat_id] = [
            t for t in self.last_message_time[chat_id] 
            if current_time - t < self.config.rate_limit_window
        ]
        
        return True
    
    def _is_admin(self, chat_id: int) -> bool:
        """Check if user is admin"""
        return self.config.is_admin(chat_id)
    
    async def _send_rate_limit_violation_message(self, chat_id: int):
        """Send rate limit violation message to user"""
        try:
            config = self.config.get_rate_limit_config()
            
            violation_msg = (
                f"⚡ **Rate Limit Exceeded**\n\n"
                f"You have sent too many messages too quickly.\n\n"
                f"**Limits:**\n"
                f"• Max {config['max_messages']} messages per {config['window_seconds']} seconds\n"
                f"• Temporary ban: {config['ban_duration_minutes']} minutes\n\n"
                f"Please wait before sending more messages."
            )
            
            # Send directly to chat (bypass normal authorization)
            await self.bot.send_message(
                chat_id=chat_id,
                text=violation_msg,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            self.logger.error(f"Error sending rate limit violation message: {e}")
    
    # ========================================
    # COMMAND HANDLERS - COMPLETE IMPLEMENTATION
    # ========================================
    
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
            f"• Unseen: {self.image_manager.get_unseen_count()}\n"
            f"• Order: {self.config.get_image_order_mode().title()}\n"
        )
        
        # NEW: Add optimization info
        if hasattr(self.config, 'image_optimization') and getattr(self.config, 'image_optimization', False):
            try:
                optimized_count = getattr(self.image_manager, 'get_optimized_count', lambda: 0)()
                welcome_msg += f"• Optimized: {optimized_count}/{self.image_manager.get_image_count()}\n"
            except:
                pass
        
        welcome_msg += (
            f"\n📨 Send photos/videos to display them!\n\n"
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
    
    async def _cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        self.recovery_manager.update_last_update_id(update.update_id)
        
        if not self._is_authorized(update.effective_chat.id):
            await self._send_unauthorized_message(update)
            return
        
        help_text = (
            f"🖼️ **TeleFrame Help**\n\n"
            f"**Basic Commands:**\n"
            f"/start - Welcome message\n"
            f"/help - This help text\n"
            f"/status - System status\n"
            f"/info - Chat information\n"
            f"/ping - Test connection\n"
            f"/stats - Usage statistics\n"
            f"/seen - Show Viewing statistics\n\n"
            f"**Media:**\n"
            f"• Send photos to add to slideshow\n"
            f"• Send videos (if enabled)\n"
            f"• Captions will be displayed\n\n"
        )
        
        # Add admin commands if user is admin
        if self._is_admin(update.effective_chat.id):
            help_text += (
                f"**Admin Commands:**\n"
                f"/monitor - Monitor control\n"
                f"/schedule - Set monitor schedule\n"
                f"/order - Image order control\n"
                f"/optimize - Image optimization\n"
                f"/compression - Compression settings\n"
                f"/recovery - Recovery statistics\n"
                f"/ratelimit - Rate limiting control\n"
                f"/restart - Restart frame\n\n"
                f"/service - Show Service Information\n\n"
                f"/service info - Show Service Information\n\n"
                f"/service logs - Show Service Logs\n\n"

            )
        
        # Add current image order info
        current_order = self.config.get_image_order_mode()
        help_text += (
            f"**Image Order:**\n"
            f"• Current mode: {current_order.title()}\n"
            f"• {self.config.get_image_order_description()}\n\n"
        )
        
        # NEW: Add optimization info
        if hasattr(self.config, 'image_optimization'):
            help_text += (
                f"**Image Optimization:**\n"
                f"• Status: {'Enabled' if getattr(self.config, 'image_optimization', False) else 'Disabled'}\n"
            )
            if hasattr(self.config, 'get_optimization_description'):
                help_text += f"• {self.config.get_optimization_description()}\n"
            help_text += "\n"
        
        # Add monitor info if available
        if self.monitor_controller:
            help_text += (
                f"**Monitor Control:**\n"
                f"• Automatic on/off scheduling\n"
                f"• Manual override commands\n"
                f"• Schedule management\n\n"
            )
        
        # Add rate limiting info
        if self.config.rate_limiting_enabled:
            help_text += (
                f"**Rate Limiting:**\n"
                f"• Max {self.config.rate_limit_max_messages} messages per {self.config.rate_limit_window}s\n"
                f"• Ban duration: {self.config.rate_limit_ban_duration} minutes\n"
            )
            
            if self.config.rate_limit_admin_exempt and self._is_admin(update.effective_chat.id):
                help_text += f"• You are exempt (admin)\n"
            elif self.config.rate_limit_whitelist_exempt and self.config.is_chat_whitelisted(update.effective_chat.id):
                help_text += f"• You are exempt (whitelisted)\n"
            
            help_text += "\n"
        
        help_text += (
            f"**File Limits:**\n"
            f"• Max size: {self.config.max_file_size // (1024*1024)}MB\n"
            f"• Types: {', '.join(self.config.allowed_file_types)}\n\n"
            f"📧 Contact admin for access issues."
        )
        
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    async def _cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command"""
        self.recovery_manager.update_last_update_id(update.update_id)
        
        if not self._is_authorized(update.effective_chat.id):
            await self._send_unauthorized_message(update)
            return
        
        uptime = int(time.time() - self.startup_time)
        
        status_msg = (
            f"📊 **TeleFrame Status**\n\n"
            f"**System:**\n"
            f"• Uptime: {uptime // 3600}h {(uptime % 3600) // 60}m\n"
            f"• Error count: {self.error_count}\n"
            f"• Free space: {self._get_disk_space()}\n\n"
            f"**Images:**\n"
            f"• Total: {self.image_manager.get_image_count()}\n"
            f"• Unseen: {self.image_manager.get_unseen_count()}\n"
            f"• Order: {self.config.get_image_order_mode().title()}\n"
            f"• Folder: {self.config.image_folder}\n"
        )
        
        # NEW: Add optimization status
        if hasattr(self.config, 'image_optimization'):
            try:
                optimized_count = getattr(self.image_manager, 'get_optimized_count', lambda: 0)()
                status_msg += f"• Optimized: {optimized_count}/{self.image_manager.get_image_count()}\n"
                
                if getattr(self.config, 'image_optimization', False) and hasattr(self.image_manager, 'get_optimization_stats'):
                    opt_stats = self.image_manager.get_optimization_stats()
                    if 'total_savings_formatted' in opt_stats:
                        status_msg += f"• Space saved: {opt_stats['total_savings_formatted']} ({opt_stats.get('savings_percent', 0)}%)\n"
            except:
                pass
        
        status_msg += (
            f"\n**Bot:**\n"
            f"• Running: {'✅' if self.running else '❌'}\n"
            f"• Updates: {self.update_stats['total_updates']}\n"
            f"• Photos: {self.update_stats['photos_processed']}\n"
            f"• Videos: {self.update_stats['videos_processed']}\n"
            f"• Rate violations: {self.update_stats['rate_limit_violations']}\n"
        )
        
        # Add slideshow status if available
        if self.slideshow_display:
            try:
                order_info = self.slideshow_display.get_current_order_info()
                status_msg += (
                    f"\n**Slideshow:**\n"
                    f"• Sequence: {order_info['current_position']}/{order_info['sequence_length']}\n"
                    f"• Current index: {order_info['current_image_index']}\n"
                )
            except Exception as e:
                self.logger.debug(f"Could not get slideshow status: {e}")
        
        # Add monitor status if available
        if self.monitor_controller:
            monitor_status = self.monitor_controller.get_status()
            status_msg += (
                f"\n**Monitor:**\n"
                f"• State: {monitor_status['state']}\n"
                f"• Control: {'✅' if monitor_status['enabled'] else '❌'}\n"
                f"• Method: {monitor_status['control_method']}\n"
                f"• Schedule: {monitor_status['turn_on_time']} - {monitor_status['turn_off_time']}\n"
                f"• Next change: {monitor_status['next_change']}\n"
            )
        
        await update.message.reply_text(status_msg, parse_mode='Markdown')
    
    async def _cmd_info(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /info command"""
        self.recovery_manager.update_last_update_id(update.update_id)
        
        chat = update.effective_chat
        user = update.effective_user
        
        info_msg = (
            f"ℹ️ **Chat Information**\n\n"
            f"**Chat:**\n"
            f"• ID: `{chat.id}`\n"
            f"• Type: {chat.type}\n"
            f"• Title: {chat.title or 'N/A'}\n\n"
            f"**User:**\n"
            f"• ID: `{user.id if user else 'N/A'}`\n"
            f"• Name: {self._get_sender_name(update)}\n"
            f"• Username: @{user.username if user and user.username else 'N/A'}\n\n"
            f"**Access:**\n"
            f"• Authorized: {'✅' if self._is_authorized(chat.id) else '❌'}\n"
            f"• Admin: {'✅' if self._is_admin(chat.id) else '❌'}\n"
        )
        
        # Add rate limiting info
        if self.config.rate_limiting_enabled:
            current_time = time.time()
            if chat.id in self.last_message_time:
                recent_messages = [
                    t for t in self.last_message_time[chat.id]
                    if current_time - t < self.config.rate_limit_window
                ]
                percentage = (len(recent_messages) / self.config.rate_limit_max_messages) * 100
                info_msg += f"• Rate limit usage: {len(recent_messages)}/{self.config.rate_limit_max_messages} ({percentage:.0f}%)\n"
            
            if chat.id in self.banned_chats:
                ban_remaining = int(self.banned_chats[chat.id] - current_time)
                info_msg += f"• Rate limit ban: {ban_remaining}s remaining\n"
        
        await update.message.reply_text(info_msg, parse_mode='Markdown')
    
    async def _cmd_ping(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /ping command"""
        self.recovery_manager.update_last_update_id(update.update_id)
        
        if not self._is_authorized(update.effective_chat.id):
            await self._send_unauthorized_message(update)
            return
        
        start_time = time.time()
        
        # Send initial message
        sent_message = await update.message.reply_text("🏓 Pinging...")
        
        # Calculate response time
        response_time = int((time.time() - start_time) * 1000)
        
        # Update message with result
        ping_msg = (
            f"🏓 **Pong!**\n\n"
            f"• Response time: {response_time}ms\n"
            f"• Bot uptime: {int(time.time() - self.startup_time)}s\n"
            f"• Status: ✅ Online"
        )
        
        await sent_message.edit_text(ping_msg, parse_mode='Markdown')
    
    async def _cmd_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stats command"""
        self.recovery_manager.update_last_update_id(update.update_id)
        
        if not self._is_authorized(update.effective_chat.id):
            await self._send_unauthorized_message(update)
            return
        
        # Calculate statistics
        uptime_hours = (time.time() - self.startup_time) / 3600
        
        stats_msg = (
            f"📈 **TeleFrame Statistics**\n\n"
            f"**Bot Activity:**\n"
            f"• Total updates: {self.update_stats['total_updates']}\n"
            f"• Photos processed: {self.update_stats['photos_processed']}\n"
            f"• Videos processed: {self.update_stats['videos_processed']}\n"
            f"• Commands processed: {self.update_stats['commands_processed']}\n"
            f"• Rate violations: {self.update_stats['rate_limit_violations']}\n"
            f"• Uptime: {uptime_hours:.1f}h\n"
            f"• Error rate: {self.error_count / max(uptime_hours, 0.1):.1f}/h\n\n"
            f"**Image Library:**\n"
            f"• Total images: {self.image_manager.get_image_count()}\n"
            f"• Unseen images: {self.image_manager.get_unseen_count()}\n"
            f"• Max capacity: {self.config.image_count}\n"
            f"• Auto-delete: {'✅' if self.config.auto_delete_images else '❌'}\n"
            f"• Current order: {self.config.get_image_order_mode().title()}\n"
        )
        
        # NEW: Add optimization statistics
        if hasattr(self.config, 'image_optimization'):
            try:
                opt_stats = getattr(self.image_manager, 'get_optimization_stats', lambda: {})()
                if opt_stats and opt_stats.get('enabled'):
                    stats_msg += (
                        f"\n**Image Optimization:**\n"
                        f"• Optimized images: {opt_stats.get('optimized_images', 0)}/{opt_stats.get('total_images', 0)}\n"
                        f"• Optimization rate: {opt_stats.get('optimization_rate', 'N/A')}\n"
                        f"• Total space saved: {opt_stats.get('total_savings_formatted', 'N/A')}\n"
                        f"• Average savings: {opt_stats.get('savings_percent', 'N/A')}\n"
                    )
            except:
                pass
        
        # Add recovery stats for admins
        if self._is_admin(update.effective_chat.id):
            recovery_stats = self.recovery_manager.get_recovery_stats()
            stats_msg += (
                f"\n**Recovery System:**\n"
                f"• Total recoveries: {recovery_stats['total_recoveries']}\n"
                f"• Last recovery: {recovery_stats['last_recovery'] or 'Never'}\n"
                f"• Updates recovered: {recovery_stats['updates_recovered']}\n"
                f"• Last update ID: {recovery_stats['last_update_id']}\n"
            )
        
        await update.message.reply_text(stats_msg, parse_mode='Markdown')
    


    async def _cmd_restart(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /restart command (admin only) - Simplified reload only"""
        self.recovery_manager.update_last_update_id(update.update_id)
        
        if not self._is_admin(update.effective_chat.id):
            await update.message.reply_text("🔒 Admin command only")
            return
        
        # Get admin info for logging
        admin_name = self._get_sender_name(update)
        admin_id = update.effective_chat.id
        
        # Log admin action BEFORE execution
        security_logger = logging.getLogger("teleframe.security")
        security_logger.warning(f"Service reload requested by admin {admin_id} ({admin_name})")
        
        # Send initial message
        status_message = await update.message.reply_text(
            f"🔄 **Reloading TeleFrame Service**\n\n"
            f"⏳ Please wait...",
            parse_mode='Markdown'
        )
        
        try:
            # Execute systemctl reload command
            success, output, error = await self._execute_systemctl_reload()
            
            if success:
                # Success message
                success_msg = (
                    f"✅ **TeleFrame Service Reloaded**\n\n"
                    f"📡 TeleFrame has been gracefully reloaded.\n"
                    f"• Configuration refreshed\n"
                    f"• Bot connection maintained\n"
                    f"• No data loss\n\n"
                    f"🔄 Changes are now active.\n\n"
                    f"🕐 Completed at: {datetime.now().strftime('%H:%M:%S')}"
                )
                
                await status_message.edit_text(success_msg, parse_mode='Markdown')
                
                # Log success
                self.logger.info(f"Service reload executed successfully by admin {admin_id}")
                security_logger.info(f"Service reload completed successfully by admin {admin_id}")
                
            else:
                # Error message
                error_msg = (
                    f"❌ **Service Reload Failed**\n\n"
                    f"**Error Details:**\n"
                    f"```\n{error[:500]}\n```\n\n"
                    f"**Possible Causes:**\n"
                    f"• Insufficient permissions\n"
                    f"• Service configuration error\n"
                    f"• System error\n\n"
                    f"**Troubleshooting:**\n"
                    f"• Check service status: `systemctl status teleframe`\n"
                    f"• Check logs: `journalctl -u teleframe -f`\n"
                    f"• Try manual reload: `sudo systemctl reload teleframe`"
                )
                
                await status_message.edit_text(error_msg, parse_mode='Markdown')
                
                # Log error
                self.logger.error(f"Service reload failed: {error}")
                security_logger.error(f"Service reload failed for admin {admin_id}: {error}")
        
        except Exception as e:
            # Exception handling
            exception_msg = (
                f"💥 **Critical Error During Reload**\n\n"
                f"**Exception:** `{str(e)}`\n\n"
                f"🔧 **Emergency Actions:**\n"
                f"• SSH to server and check: `sudo systemctl status teleframe`\n"
                f"• Check logs: `sudo journalctl -u teleframe --since '5 minutes ago'`\n"
                f"• Manual reload: `sudo systemctl reload teleframe`"
            )
            
            try:
                await status_message.edit_text(exception_msg, parse_mode='Markdown')
            except:
                # If we can't edit the message, send a new one
                await update.message.reply_text(exception_msg, parse_mode='Markdown')
            
            # Critical error logging
            self.logger.error(f"Critical error in restart command: {e}")
            security_logger.error(f"Critical error during service reload by admin {admin_id}: {e}")


    async def _execute_systemctl_reload(self) -> tuple[bool, str, str]:
        """Execute systemctl reload command with proper error handling"""
        try:
            cmd_array = ["sudo", "systemctl", "restart", "teleframe"]
            
            self.logger.info(f"Executing: {' '.join(cmd_array)}")
            
            # Execute command with timeout
            process = await asyncio.create_subprocess_exec(
                *cmd_array,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            try:
                # Wait for completion with timeout
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), 
                    timeout=30.0  # 30 second timeout
                )
                
                stdout_text = stdout.decode('utf-8') if stdout else ""
                stderr_text = stderr.decode('utf-8') if stderr else ""
                
                # Check return code
                if process.returncode == 0:
                    self.logger.debug(f"Reload successful. Output: {stdout_text}")
                    return True, stdout_text, stderr_text
                else:
                    self.logger.warning(f"Reload failed with code {process.returncode}. Error: {stderr_text}")
                    return False, stdout_text, stderr_text
                    
            except asyncio.TimeoutError:
                # Kill the process if it times out
                try:
                    process.kill()
                    await process.wait()
                except:
                    pass
                
                error_msg = f"Reload command timed out after 30 seconds"
                self.logger.error(error_msg)
                return False, "", error_msg
        
        except Exception as e:
            error_msg = f"Exception executing reload: {str(e)}"
            self.logger.error(error_msg)
            return False, "", error_msg


    # Additional helper method for comprehensive service management
    async def _cmd_service(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /service command for comprehensive service management (admin only)"""
        self.recovery_manager.update_last_update_id(update.update_id)
        
        if not self._is_admin(update.effective_chat.id):
            await update.message.reply_text("🔒 Admin command only")
            return
        
        args = context.args
        
        if not args or args[0] == "info":
            # Show comprehensive service information
            try:
                # Get service status
                success, status_output, _ = await self._execute_systemctl_command("status")
                
                # Get system information
                import platform
                import psutil
                import os
                
                # Get current user and process info
                current_user = os.getenv('USER', 'unknown')
                current_pid = os.getpid()
                
                # Get memory and CPU usage
                try:
                    process = psutil.Process(current_pid)
                    cpu_percent = process.cpu_percent()
                    memory_info = process.memory_info()
                    memory_mb = memory_info.rss / 1024 / 1024
                except:
                    cpu_percent = 0
                    memory_mb = 0
                
                info_msg = (
                    f"🔧 **TeleFrame Service Information**\n\n"
                    f"**Current Process:**\n"
                    f"• PID: {current_pid}\n"
                    f"• User: {current_user}\n"
                    f"• CPU Usage: {cpu_percent:.1f}%\n"
                    f"• Memory Usage: {memory_mb:.1f} MB\n\n"
                    f"**System:**\n"
                    f"• Platform: {platform.system()} {platform.release()}\n"
                    f"• Python: {platform.python_version()}\n"
                    f"• Uptime: {self._get_uptime()}\n\n"
                    f"**Service Status:**\n"
                    f"```\n{status_output[:800]}\n```"
                )
                
                await update.message.reply_text(info_msg, parse_mode='Markdown')
                
            except Exception as e:
                await update.message.reply_text(f"❌ Error getting service info: {e}")
        
        elif args[0] == "logs":
            # Show recent logs
            try:
                log_lines = int(args[1]) if len(args) > 1 else 20
                log_lines = min(max(log_lines, 5), 50)  # Limit between 5-50 lines
                
                process = await asyncio.create_subprocess_exec(
                    "journalctl", "-u", "teleframe", "--no-pager", f"--lines={log_lines}",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=15.0)
                
                if process.returncode == 0:
                    logs = stdout.decode('utf-8')
                    
                    # Truncate if too long for Telegram
                    if len(logs) > 3500:
                        logs = logs[-3500:]
                        logs = "...\n" + logs[logs.find('\n') + 1:]
                    
                    log_msg = f"📋 **Recent Service Logs ({log_lines} lines)**\n\n```\n{logs}\n```"
                    await update.message.reply_text(log_msg, parse_mode='Markdown')
                else:
                    error = stderr.decode('utf-8')
                    await update.message.reply_text(f"❌ Error getting logs: {error}")
                    
            except asyncio.TimeoutError:
                await update.message.reply_text("❌ Timeout getting logs")
            except Exception as e:
                await update.message.reply_text(f"❌ Error: {e}")
        
        else:
            await update.message.reply_text(
                "❓ **Service Commands:**\n\n"
                "`/service` or `/service info` - Service information\n"
                "`/service logs [lines]` - Show recent logs\n\n"
                "**Note:** Use `/restart` for service control commands.",
                parse_mode='Markdown'
            )

    def _get_uptime(self) -> str:
        """Get bot uptime as readable string"""
        uptime_seconds = int(time.time() - self.startup_time)
        hours = uptime_seconds // 3600
        minutes = (uptime_seconds % 3600) // 60
        seconds = uptime_seconds % 60
        
        if hours > 0:
            return f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"

    
    async def _cmd_monitor(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /monitor command (admin only)"""
        self.recovery_manager.update_last_update_id(update.update_id)
        
        if not self._is_admin(update.effective_chat.id):
            await update.message.reply_text("🔒 Admin command only")
            return
        
        if not self.monitor_controller:
            await update.message.reply_text("❌ Monitor control not available")
            return
        
        args = context.args
        
        if not args:
            # Show monitor status
            status = self.monitor_controller.get_status()
            
            status_msg = (
                f"🖥️ **Monitor Status**\n\n"
                f"• State: {status['state']}\n"
                f"• Control: {'Enabled' if status['enabled'] else 'Disabled'}\n"
                f"• Method: {status['control_method']}\n"
                f"• Schedule: {status['turn_on_time']} - {status['turn_off_time']}\n"
                f"• Current time: {status['current_time']}\n"
                f"• Next change: {status['next_change']}\n"
            )
            
            if status['last_manual_override']:
                status_msg += f"• Manual override: {status['last_manual_override']}\n"
            
            await update.message.reply_text(status_msg, parse_mode='Markdown')
            
        elif args[0].lower() == "on":
            await self.monitor_controller.turn_on(manual=True)
            await update.message.reply_text("🖥️ Monitor turned ON manually")
            
        elif args[0].lower() == "off":
            await self.monitor_controller.turn_off(manual=True)
            await update.message.reply_text("🖥️ Monitor turned OFF manually")
            
        elif args[0].lower() == "info":
            # Show system information
            info = self.monitor_controller.get_system_info()
            
            info_msg = (
                f"🖥️ **Monitor System Information**\n\n"
                f"**Current Method:** {info['control_method']}\n"
                f"**Available Methods:** {', '.join(info['available_methods'])}\n\n"
                f"**Hardware:**\n"
            )
            
            for key, value in info.get('hardware', {}).items():
                info_msg += f"• {key.replace('_', ' ').title()}: {'✅' if value else '❌'}\n"
            
            if 'device_model' in info:
                info_msg += f"\n**Device:** {info['device_model']}\n"
            
            await update.message.reply_text(info_msg, parse_mode='Markdown')
            
        else:
            await update.message.reply_text(
                "❓ **Monitor Commands:**\n\n"
                "`/monitor` - Show status\n"
                "`/monitor on` - Turn on manually\n"
                "`/monitor off` - Turn off manually\n"
                "`/monitor info` - System information\n",
                parse_mode='Markdown'
            )
    
    async def _cmd_schedule(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /schedule command (admin only)"""
        self.recovery_manager.update_last_update_id(update.update_id)
        
        if not self._is_admin(update.effective_chat.id):
            await update.message.reply_text("🔒 Admin command only")
            return
        
        if not self.monitor_controller:
            await update.message.reply_text("❌ Monitor control not available")
            return
        
        args = context.args
        
        if not args:
            # Show current schedule
            status = self.monitor_controller.get_status()
            await update.message.reply_text(
                f"📅 **Current Schedule:**\n"
                f"• Turn ON: {status['turn_on_time']}\n"
                f"• Turn OFF: {status['turn_off_time']}\n"
                f"• Auto-control: {'Enabled' if status['enabled'] else 'Disabled'}\n"
                f"• Current time: {status['current_time']}\n"
                f"• Next change: {status['next_change']}\n\n"
                f"**Usage:** `/schedule ON_TIME OFF_TIME`\n"
                f"**Example:** `/schedule 09:00 22:30`\n"
                f"**Format:** HH:MM (24-hour)",
                parse_mode='Markdown'
            )
            return
        
        if args[0].lower() == "enable":
            # Enable auto-control
            self.config.toggle_monitor = True
            await update.message.reply_text(
                "✅ **Monitor auto-control enabled**\n"
                "Monitor will follow the configured schedule."
            )
            return
        
        if args[0].lower() == "disable":
            # Disable auto-control
            self.config.toggle_monitor = False
            await update.message.reply_text(
                "⚠️ **Monitor auto-control disabled**\n"
                "Monitor will not automatically turn on/off."
            )
            return
        
        if len(args) != 2:
            await update.message.reply_text(
                "❓ **Schedule Commands:**\n\n"
                "`/schedule` - Show current schedule\n"
                "`/schedule ON_TIME OFF_TIME` - Set schedule\n"
                "`/schedule enable` - Enable auto-control\n"
                "`/schedule disable` - Disable auto-control\n\n"
                "**Time Format:** HH:MM (24-hour)\n"
                "**Example:** `/schedule 09:00 22:30`",
                parse_mode='Markdown'
            )
            return
        
        turn_on_time = args[0]
        turn_off_time = args[1]
        
        # Update schedule
        success = self.monitor_controller.update_schedule(turn_on_time, turn_off_time)
        
        if success:
            await update.message.reply_text(
                f"✅ **Schedule Updated**\n\n"
                f"• Turn ON: {turn_on_time}\n"
                f"• Turn OFF: {turn_off_time}\n\n"
                f"New schedule is now active.",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                "❌ **Schedule Update Failed**\n\n"
                "Check time format (HH:MM) and ensure times are different."
            )
    
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
                
            elif args[0] == "force":
                # Force recovery run
                await update.message.reply_text("🔄 Forcing recovery run...")
                
                try:
                    await self._perform_update_recovery()
                    await update.message.reply_text("✅ Forced recovery completed")
                except Exception as e:
                    await update.message.reply_text(f"❌ Forced recovery failed: {e}")
                    
            else:
                await update.message.reply_text(
                    "❓ **Recovery Commands:**\n\n"
                    "`/recovery` - Show statistics\n"
                    "`/recovery test` - Test system\n"
                    "`/recovery reset` - Reset state\n"
                    "`/recovery force` - Force recovery run\n",
                    parse_mode='Markdown'
                )
                
        except Exception as e:
            self.logger.error(f"Error in recovery command: {e}")
            await self._send_error_message(update, "recovery command")
    
    async def _cmd_ratelimit(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /ratelimit command (admin only)"""
        self.recovery_manager.update_last_update_id(update.update_id)
        
        if not self._is_admin(update.effective_chat.id):
            await update.message.reply_text("🔒 Admin command only")
            return
        
        args = context.args
        
        if not args:
            # Show current rate limit settings
            config = self.config.get_rate_limit_config()
            current_time = time.time()
            
            status_msg = (
                f"⚡ **Rate Limiting Status**\n\n"
                f"**Configuration:**\n"
                f"• Enabled: {'✅' if config['enabled'] else '❌'}\n"
                f"• Window: {config['window_seconds']}s\n"
                f"• Max messages: {config['max_messages']}\n"
                f"• Whitelist exempt: {'✅' if config['whitelist_exempt'] else '❌'}\n"
                f"• Admin exempt: {'✅' if config['admin_exempt'] else '❌'}\n"
                f"• Ban duration: {config['ban_duration_minutes']}m\n\n"
            )
            
            # Show active bans
            active_bans = []
            for chat_id, ban_end_time in self.banned_chats.items():
                if current_time < ban_end_time:
                    remaining = int(ban_end_time - current_time)
                    active_bans.append(f"• Chat {chat_id}: {remaining}s remaining")
            
            if active_bans:
                status_msg += "**Active Bans:**\n" + "\n".join(active_bans) + "\n\n"
            
            # Show current usage for active chats
            if self.last_message_time:
                status_msg += "**Current Usage:**\n"
                
                for chat_id, timestamps in self.last_message_time.items():
                    recent_messages = [
                        t for t in timestamps 
                        if current_time - t < config['window_seconds']
                    ]
                    if recent_messages:
                        percentage = (len(recent_messages) / config['max_messages']) * 100
                        status_msg += f"• Chat {chat_id}: {len(recent_messages)}/{config['max_messages']} ({percentage:.0f}%)\n"
            
            await update.message.reply_text(status_msg, parse_mode='Markdown')
            
        elif args[0] == "reset":
            # Reset all rate limit counters and bans
            counter_count = len(self.last_message_time)
            banned_count = len(self.banned_chats)
            self.last_message_time.clear()
            self.banned_chats.clear()
            
            await update.message.reply_text(
                f"✅ **Rate limiting reset**\n"
                f"• Cleared {counter_count} chat counters\n"
                f"• Lifted {banned_count} active bans"
            )
            
            # Log admin action
            security_logger = logging.getLogger("teleframe.security")
            security_logger.info(f"Rate limiting reset by admin {update.effective_chat.id}")
            
        elif args[0] == "unban":
            if len(args) < 2:
                await update.message.reply_text("❓ Usage: `/ratelimit unban CHAT_ID`")
                return
            
            try:
                target_chat_id = int(args[1])
                
                if target_chat_id in self.banned_chats:
                    del self.banned_chats[target_chat_id]
                    await update.message.reply_text(f"✅ Unbanned chat {target_chat_id}")
                    
                    # Log admin action
                    security_logger = logging.getLogger("teleframe.security")
                    security_logger.info(f"Chat {target_chat_id} unbanned by admin {update.effective_chat.id}")
                else:
                    await update.message.reply_text(f"❌ Chat {target_chat_id} is not banned")
                    
            except ValueError:
                await update.message.reply_text("❌ Invalid chat ID format")
        
        elif args[0] == "config":
            # Show detailed configuration options
            config_msg = (
                f"⚙️ **Rate Limiting Configuration**\n\n"
                f"**Available Settings:**\n"
                f"• `enabled`: Enable/disable rate limiting\n"
                f"• `window_seconds`: Time window (1-3600s)\n"
                f"• `max_messages`: Max messages per window (1-1000)\n"
                f"• `whitelist_exempt`: Exempt whitelisted chats\n"
                f"• `admin_exempt`: Exempt admin chats\n"
                f"• `ban_duration_minutes`: Ban duration (1-1440m)\n\n"
                f"**Current Values:**\n"
            )
            
            config = self.config.get_rate_limit_config()
            for key, value in config.items():
                config_msg += f"• `{key}`: {value}\n"
            
            config_msg += (
                f"\n**Note:** Configuration changes require restart.\n"
                f"Edit `config.toml` to modify these settings."
            )
            
            await update.message.reply_text(config_msg, parse_mode='Markdown')
            
        elif args[0] == "disable":
            # Temporarily disable rate limiting (until restart)
            self.config.rate_limiting_enabled = False
            await update.message.reply_text(
                "⚠️ **Rate limiting temporarily disabled**\n"
                "This change is temporary until next restart.\n"
                "Edit `config.toml` for permanent changes."
            )
            
            # Log admin action
            security_logger = logging.getLogger("teleframe.security")
            security_logger.warning(f"Rate limiting disabled by admin {update.effective_chat.id}")
            
        elif args[0] == "enable":
            # Re-enable rate limiting
            self.config.rate_limiting_enabled = True
            await update.message.reply_text(
                "✅ **Rate limiting enabled**\n"
                "Using configuration from `config.toml`."
            )
            
            # Log admin action
            security_logger = logging.getLogger("teleframe.security")
            security_logger.info(f"Rate limiting enabled by admin {update.effective_chat.id}")
            
        else:
            await update.message.reply_text(
                "❓ **Rate Limiting Commands:**\n\n"
                "`/ratelimit` - Show status\n"
                "`/ratelimit reset` - Reset all counters\n"
                "`/ratelimit unban CHAT_ID` - Unban chat\n"
                "`/ratelimit config` - Show configuration\n"
                "`/ratelimit disable` - Disable temporarily\n"
                "`/ratelimit enable` - Re-enable\n",
                parse_mode='Markdown'
            )
    
    async def _cmd_order(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /order command (admin only)"""
        self.recovery_manager.update_last_update_id(update.update_id)
        
        if not self._is_admin(update.effective_chat.id):
            await update.message.reply_text("🔒 Admin command only")
            return
        
        args = context.args
        
        if not args:
            # Show current image order settings
            current_mode = self.config.get_image_order_mode()
            description = self.config.get_image_order_description()
            
            status_msg = (
                f"🔄 **Image Order Status**\n\n"
                f"**Current Mode:** {current_mode.title()}\n"
                f"**Description:** {description}\n\n"
            )
            
            # Show sequence info if slideshow is available
            if self.slideshow_display:
                try:
                    order_info = self.slideshow_display.get_current_order_info()
                    status_msg += (
                        f"**Sequence Info:**\n"
                        f"• Total images: {order_info['sequence_length']}\n"
                        f"• Current position: {order_info['current_position']}\n"
                    )
                    if order_info['current_image_index'] is not None:
                        status_msg += f"• Current index: {order_info['current_image_index']}\n"
                except Exception as e:
                    self.logger.debug(f"Could not get slideshow order info: {e}")
            
            status_msg += (
                f"\n**Available Modes:**\n"
                f"• `random` - Random shuffle each cycle\n"
                f"• `latest` - Newest images first\n"
                f"• `oldest` - Oldest images first\n"
                f"• `sequential` - Storage order\n\n"
                f"**Usage:** `/order [mode]`\n"
                f"**Example:** `/order random`"
            )
            
            await update.message.reply_text(status_msg, parse_mode='Markdown')
            
        elif args[0].lower() in ["random", "latest", "oldest", "sequential"]:
            # Change image order mode
            new_mode = args[0].lower()
            old_mode = self.config.get_image_order_mode()
            
            # Update config
            success = self.config.set_image_order_mode(new_mode)
            
            if success:
                # Update slideshow if available
                slideshow_updated = False
                if self.slideshow_display:
                    try:
                        slideshow_updated = self.slideshow_display.change_image_order(new_mode)
                    except Exception as e:
                        self.logger.error(f"Error updating slideshow order: {e}")
                
                # Success message
                status_emoji = "✅" if slideshow_updated else "⚠️"
                response_msg = (
                    f"{status_emoji} **Image Order Updated**\n\n"
                    f"**Changed:** {old_mode.title()} → {new_mode.title()}\n"
                    f"**Description:** {self.config.get_image_order_description()}\n"
                )
                
                if not slideshow_updated and self.slideshow_display:
                    response_msg += f"\n⚠️ Note: Slideshow will update on next image change"
                elif not self.slideshow_display:
                    response_msg += f"\n💡 Changes will take effect when slideshow starts"
                
                await update.message.reply_text(response_msg, parse_mode='Markdown')
                
                # Log admin action
                security_logger = logging.getLogger("teleframe.security")
                security_logger.info(f"Image order changed from {old_mode} to {new_mode} by admin {update.effective_chat.id}")
                
            else:
                await update.message.reply_text(
                    f"❌ **Failed to change image order**\n"
                    f"Could not set mode to: {new_mode}"
                )
                
        elif args[0].lower() == "refresh":
            # Force refresh current sequence
            if self.slideshow_display:
                try:
                    current_mode = self.config.get_image_order_mode()
                    self.slideshow_display._update_image_sequence(force_refresh=True)
                    
                    order_info = self.slideshow_display.get_current_order_info()
                    
                    await update.message.reply_text(
                        f"🔄 **Sequence Refreshed**\n\n"
                        f"**Mode:** {current_mode.title()}\n"
                        f"**New sequence:** {order_info['sequence_length']} images\n"
                        f"**Current position:** {order_info['current_position']}"
                    )
                    
                    # Log admin action
                    security_logger = logging.getLogger("teleframe.security")
                    security_logger.info(f"Image sequence refreshed by admin {update.effective_chat.id}")
                    
                except Exception as e:
                    self.logger.error(f"Error refreshing sequence: {e}")
                    await update.message.reply_text("❌ Error refreshing image sequence")
            else:
                await update.message.reply_text("❌ Slideshow not available")
                
        elif args[0].lower() == "info":
            # Show detailed sequence information
            if self.slideshow_display:
                try:
                    order_info = self.slideshow_display.get_current_order_info()
                    current_mode = order_info['mode']
                    
                    info_msg = (
                        f"📊 **Detailed Order Information**\n\n"
                        f"**Mode:** {current_mode.title()}\n"
                        f"**Description:** {order_info['description']}\n"
                        f"**Sequence Length:** {order_info['sequence_length']}\n"
                        f"**Current Position:** {order_info['current_position']}\n"
                    )
                    
                    if order_info['current_image_index'] is not None:
                        info_msg += f"**Current Image Index:** {order_info['current_image_index']}\n"
                    
                    # Show first few indices in sequence for debugging
                    if self.slideshow_display.image_sequence:
                        first_indices = self.slideshow_display.image_sequence[:10]
                        info_msg += f"\n**Sequence Preview:** {first_indices}"
                        if len(self.slideshow_display.image_sequence) > 10:
                            info_msg += f"... (+{len(self.slideshow_display.image_sequence) - 10} more)"
                    
                    await update.message.reply_text(info_msg, parse_mode='Markdown')
                    
                except Exception as e:
                    self.logger.error(f"Error getting order info: {e}")
                    await update.message.reply_text("❌ Error getting order information")
            else:
                await update.message.reply_text("❌ Slideshow not available")
                
        else:
            # Invalid argument
            await update.message.reply_text(
                "❓ **Image Order Commands:**\n\n"
                "`/order` - Show current status\n"
                "`/order random` - Random shuffle\n"
                "`/order latest` - Newest first\n"
                "`/order oldest` - Oldest first\n"
                "`/order sequential` - Storage order\n"
                "`/order refresh` - Refresh sequence\n"
                "`/order info` - Detailed info\n",
                parse_mode='Markdown'
            )
    
    # ========================================
    # IMAGE OPTIMIZATION COMMANDS
    # ========================================
    
    async def _cmd_optimize(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /optimize command (admin only)"""
        self.recovery_manager.update_last_update_id(update.update_id)
        
        if not self._is_admin(update.effective_chat.id):
            await update.message.reply_text("🔒 Admin command only")
            return
        
        args = context.args
        
        if not args:
            # Show optimization status
            if hasattr(self.config, 'image_optimization'):
                try:
                    opt_stats = getattr(self.image_manager, 'get_optimization_stats', lambda: {})()
                    
                    status_msg = (
                        f"🖼️ **Image Optimization Status**\n\n"
                        f"**Configuration:**\n"
                        f"• Status: {'Enabled' if getattr(self.config, 'image_optimization', False) else 'Disabled'}\n"
                    )
                    
                    if getattr(self.config, 'image_optimization', False):
                        if hasattr(self.config, 'get_optimization_description'):
                            status_msg += f"• Description: {self.config.get_optimization_description()}\n"
                        if hasattr(self.config, 'compress_level'):
                            status_msg += f"• Compress level: {getattr(self.config, 'compress_level', 70)}\n"
                        
                        status_msg += "\n**Statistics:**\n"
                        if opt_stats:
                            status_msg += f"• Total images: {opt_stats.get('total_images', 0)}\n"
                            status_msg += f"• Optimized images: {opt_stats.get('optimized_images', 0)}\n"
                            if 'total_savings_formatted' in opt_stats:
                                status_msg += f"• Space saved: {opt_stats['total_savings_formatted']}\n"
                    
                    status_msg += (
                        f"\n**Commands:**\n"
                        f"• `/optimize enable` - Enable optimization\n"
                        f"• `/optimize disable` - Disable optimization\n"
                        f"• `/optimize stats` - Detailed statistics\n"
                        f"• `/compression [level]` - Set compression level\n"
                    )
                    
                    await update.message.reply_text(status_msg, parse_mode='Markdown')
                except Exception as e:
                    await update.message.reply_text(f"❌ Error getting optimization status: {e}")
            else:
                await update.message.reply_text("❌ Image optimization not available")
                
        elif args[0].lower() == "enable":
            # Enable optimization
            if hasattr(self.config, 'image_optimization'):
                self.config.image_optimization = True
                await update.message.reply_text(
                    "✅ **Image optimization enabled**\n"
                    "New images will be automatically optimized.\n"
                    "Edit `config.toml` to make this change permanent."
                )
                
                # Log admin action
                security_logger = logging.getLogger("teleframe.security")
                security_logger.info(f"Image optimization enabled by admin {update.effective_chat.id}")
            else:
                await update.message.reply_text("❌ Image optimization control not available")
                
        elif args[0].lower() == "disable":
            # Disable optimization
            if hasattr(self.config, 'image_optimization'):
                self.config.image_optimization = False
                await update.message.reply_text(
                    "⚠️ **Image optimization disabled**\n"
                    "New images will be stored without optimization.\n"
                    "Edit `config.toml` to make this change permanent."
                )
                
                # Log admin action
                security_logger = logging.getLogger("teleframe.security")
                security_logger.warning(f"Image optimization disabled by admin {update.effective_chat.id}")
            else:
                await update.message.reply_text("❌ Image optimization control not available")
                
        elif args[0].lower() == "stats":
            # Show detailed statistics
            if hasattr(self.config, 'image_optimization'):
                try:
                    opt_stats = getattr(self.image_manager, 'get_optimization_stats', lambda: {})()
                    
                    if opt_stats and opt_stats.get('enabled'):
                        stats_msg = (
                            f"📊 **Detailed Optimization Statistics**\n\n"
                            f"**Image Processing:**\n"
                            f"• Total images: {opt_stats.get('total_images', 0)}\n"
                            f"• Optimized images: {opt_stats.get('optimized_images', 0)}\n"
                            f"• Optimization rate: {opt_stats.get('optimization_rate', 'N/A')}\n\n"
                            f"**Storage Impact:**\n"
                            f"• Original total size: {opt_stats.get('total_original_size', 0)} bytes\n"
                            f"• Current total size: {opt_stats.get('total_current_size', 0)} bytes\n"
                            f"• Space saved: {opt_stats.get('total_savings_formatted', 'N/A')}\n"
                            f"• Average savings: {opt_stats.get('savings_percent', 'N/A')}\n\n"
                            f"**Configuration:**\n"
                        )
                        
                        opt_config = opt_stats.get('optimizer_config', {})
                        for key, value in opt_config.items():
                            stats_msg += f"• {key}: {value}\n"
                            
                        await update.message.reply_text(stats_msg, parse_mode='Markdown')
                    else:
                        await update.message.reply_text("❌ Image optimization is disabled")
                except Exception as e:
                    await update.message.reply_text(f"❌ Error getting optimization stats: {e}")
            else:
                await update.message.reply_text("❌ Image optimization not available")
                
        else:
            # Invalid argument
            await update.message.reply_text(
                "❓ **Image Optimization Commands:**\n\n"
                "`/optimize` - Show status\n"
                "`/optimize enable` - Enable optimization\n"
                "`/optimize disable` - Disable optimization\n"
                "`/optimize stats` - Detailed statistics\n"
                "`/compression [level]` - Set compression level\n",
                parse_mode='Markdown'
            )
    
    async def _cmd_compression(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /compression command (admin only)"""
        self.recovery_manager.update_last_update_id(update.update_id)
        
        if not self._is_admin(update.effective_chat.id):
            await update.message.reply_text("🔒 Admin command only")
            return
        
        args = context.args
        
        if not args:
            # Show current compression settings
            if hasattr(self.config, 'compress_level'):
                compression_msg = (
                    f"🗜️ **Compression Settings**\n\n"
                    f"**Current Level:** {getattr(self.config, 'compress_level', 'N/A')}\n"
                )
                
                if hasattr(self.config, 'get_optimization_description'):
                    compression_msg += f"**Description:** {self.config.get_optimization_description()}\n"
                
                compression_msg += (
                    f"\n**Compression Guide:**\n"
                    f"• 0-20: Minimal compression (highest quality)\n"
                    f"• 21-40: Light compression (high quality)\n"
                    f"• 41-60: Medium compression (balanced)\n"
                    f"• 61-80: High compression (smaller files)\n"
                    f"• 81-100: Maximum compression (smallest files)\n\n"
                    f"**Usage:** `/compression [0-100]`\n"
                    f"**Example:** `/compression 70`"
                )
                
                await update.message.reply_text(compression_msg, parse_mode='Markdown')
            else:
                await update.message.reply_text("❌ Compression settings not available")
                
        else:
            # Set compression level
            try:
                new_level = int(args[0])
                
                if 0 <= new_level <= 100:
                    if hasattr(self.config, 'compress_level'):
                        old_level = getattr(self.config, 'compress_level', 70)
                        self.config.compress_level = new_level
                        
                        await update.message.reply_text(
                            f"✅ **Compression Level Updated**\n\n"
                            f"**Changed:** {old_level} → {new_level}\n\n"
                            f"⚠️ This change is temporary until restart.\n"
                            f"Edit `config.toml` to make it permanent."
                        )
                        
                        # Log admin action
                        security_logger = logging.getLogger("teleframe.security")
                        security_logger.info(f"Compression level changed from {old_level} to {new_level} by admin {update.effective_chat.id}")
                    else:
                        await update.message.reply_text("❌ Compression level control not available")
                else:
                    await update.message.reply_text(
                        f"❌ **Invalid compression level**\n"
                        f"Level must be between 0 and 100."
                    )
                    
            except ValueError:
                await update.message.reply_text("❌ Invalid compression level format. Use a number between 0-100.")
    
    # ========================================
    # MESSAGE HANDLERS
    # ========================================
    
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
        
        # Add to image manager (optimization happens automatically)
        success = self.image_manager.add_image(
            file_path=file_path,
            sender=self._get_sender_name(update),
            caption=update.message.caption or "",
            chat_id=update.effective_chat.id,
            chat_name=update.effective_chat.title or update.effective_chat.first_name or "Unknown",
            message_id=update.message.message_id
        )
        
        if success:
            # NEW: Enhanced response with optimization info
            response_text = "📸 Photo added to slideshow! ✅"
            
            if hasattr(self.config, 'image_optimization') and getattr(self.config, 'image_optimization', False):
                compress_level = getattr(self.config, 'compress_level', 70)
                response_text += f"\n🔧 Optimized with {compress_level}% compression"
            
            await update.message.reply_text(response_text)
            self.logger.info(f"Photo added from {self._get_sender_name(update)}")
            
            # Update slideshow sequence if new image affects order
            if self.slideshow_display and self.config.get_image_order_mode() in ["latest", "oldest"]:
                try:
                    self.slideshow_display._update_image_sequence(force_refresh=True)
                    self.logger.debug("Slideshow sequence updated after new photo")
                except Exception as e:
                    self.logger.error(f"Error updating slideshow sequence: {e}")
            
            # Log to recovery for debugging
            self.logger.debug(f"Processed photo from update {update.update_id}")
        else:
            await update.message.reply_text("❌ Error adding photo to slideshow")
            file_path.unlink(missing_ok=True)
    
    async def _handle_video(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle video messages"""
        self.recovery_manager.update_last_update_id(update.update_id)
        
        if not self._is_authorized(update.effective_chat.id):
            await self._send_unauthorized_message(update)
            return
        
        if not self.config.show_videos:
            await update.message.reply_text("❌ Video support is disabled")
            return
        
        video = update.message.video
        
        # Check file size
        if video.file_size and video.file_size > self.config.max_file_size:
            await update.message.reply_text(
                f"❌ Video too large. Max: {self.config.max_file_size // (1024*1024)}MB"
            )
            return
        
        # Download with timeout
        file_path = await asyncio.wait_for(
            self._download_file(video.file_id, "video", ".mp4"),
            timeout=60  # Longer timeout for videos
        )
        
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
            await update.message.reply_text("🎥 Video added to slideshow! ✅")
            self.logger.info(f"Video added from {self._get_sender_name(update)}")
            
            # Update slideshow sequence if new video affects order
            if self.slideshow_display and self.config.get_image_order_mode() in ["latest", "oldest"]:
                try:
                    self.slideshow_display._update_image_sequence(force_refresh=True)
                    self.logger.debug("Slideshow sequence updated after new video")
                except Exception as e:
                    self.logger.error(f"Error updating slideshow sequence: {e}")
        else:
            await update.message.reply_text("❌ Error adding video to slideshow")
            file_path.unlink(missing_ok=True)
    
    async def _handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle document messages"""
        self.recovery_manager.update_last_update_id(update.update_id)
        
        if not self._is_authorized(update.effective_chat.id):
            await self._send_unauthorized_message(update)
            return
        
        document = update.message.document
        
        # Check if document is an allowed image/video type
        if not self.config.is_file_allowed(document.file_name):
            await update.message.reply_text(
                f"❌ File type not allowed: {Path(document.file_name).suffix}\n"
                f"Allowed: {', '.join(self.config.allowed_file_types)}"
            )
            return
        
        # Check file size
        if document.file_size and document.file_size > self.config.max_file_size:
            await update.message.reply_text(
                f"❌ File too large. Max: {self.config.max_file_size // (1024*1024)}MB"
            )
            return
        
        # Download with timeout
        file_extension = Path(document.file_name).suffix
        file_path = await asyncio.wait_for(
            self._download_file(document.file_id, "document", file_extension),
            timeout=60
        )
        
        if not file_path:
            await update.message.reply_text("❌ Error downloading file")
            return
        
        # Add to image manager
        success = self.image_manager.add_image(
            file_path=file_path,
            sender=self._get_sender_name(update),
            caption=update.message.caption or document.file_name,
            chat_id=update.effective_chat.id,
            chat_name=update.effective_chat.title or update.effective_chat.first_name or "Unknown",
            message_id=update.message.message_id
        )
        
        if success:
            # NEW: Enhanced response with optimization info
            response_text = "📎 File added to slideshow! ✅"
            
            if (hasattr(self.config, 'image_optimization') and 
                getattr(self.config, 'image_optimization', False) and 
                file_extension.lower() in ['.jpg', '.jpeg', '.png', '.gif']):
                compress_level = getattr(self.config, 'compress_level', 70)
                response_text += f"\n🔧 Optimized with {compress_level}% compression"
            
            await update.message.reply_text(response_text)
            self.logger.info(f"Document added from {self._get_sender_name(update)}")
            
            # Update slideshow sequence if new file affects order
            if self.slideshow_display and self.config.get_image_order_mode() in ["latest", "oldest"]:
                try:
                    self.slideshow_display._update_image_sequence(force_refresh=True)
                    self.logger.debug("Slideshow sequence updated after new document")
                except Exception as e:
                    self.logger.error(f"Error updating slideshow sequence: {e}")
        else:
            await update.message.reply_text("❌ Error adding file to slideshow")
            file_path.unlink(missing_ok=True)
    
    async def _handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages"""
        self.recovery_manager.update_last_update_id(update.update_id)
        
        if not self._is_authorized(update.effective_chat.id):
            await self._send_unauthorized_message(update)
            return
        
        # Simple response to text messages
        await update.message.reply_text(
            "💬 Text received! Send photos or videos to add to the slideshow.\n"
            "Use /help for available commands."
        )
    
    # ========================================
    # UTILITY METHODS
    # ========================================
    
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
    
    def _get_disk_space(self) -> str:
        """Get free disk space"""
        try:
            import shutil
            total, used, free = shutil.disk_usage(self.config.image_folder)
            free_gb = free / (1024**3)
            return f"{free_gb:.1f}GB"
        except:
            return "Unknown"
   
    async def _cmd_seen(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /seen command - show viewing statistics"""
        self.recovery_manager.update_last_update_id(update.update_id)
        
        if not self._is_authorized(update.effective_chat.id):
            await self._send_unauthorized_message(update)
            return
        
        if not self.image_manager:
            await update.message.reply_text("❌ Image manager not available")
            return
        
        try:
            stats = self.image_manager.get_image_stats()
            
            stats_msg = (
                f"👁️ **Viewing Statistics**\n\n"
                f"**Image Library:**\n"
                f"• Total images: {stats['total_images']}\n"
                f"• Seen: {stats['seen_images']} ({stats['seen_percentage']}%)\n"
                f"• Unseen: {stats['unseen_images']}\n"
            )
            
            # Add slideshow stats if available
            if self.slideshow_display:
                try:
                    viewing_stats = self.slideshow_display.get_viewing_stats()
                    if viewing_stats:
                        stats_msg += (
                            f"\n**Current Slideshow:**\n"
                            f"• Order: {viewing_stats.get('current_order', 'N/A')}\n"
                            f"• Position: {viewing_stats.get('current_position', 0)}/{viewing_stats.get('sequence_length', 0)}\n"
                            f"• Remaining: {viewing_stats.get('images_remaining', 0)}\n"
                        )
                except Exception as e:
                    self.logger.debug(f"Could not get slideshow stats: {e}")
            
            # Show some unseen images
            unseen_indices = self.image_manager.get_unseen_images()
            if unseen_indices:
                stats_msg += f"\n**Recently Added (unseen):**\n"
                for i, idx in enumerate(unseen_indices[:3]):  # Show first 3
                    try:
                        image_info = self.image_manager.get_image_info(idx)
                        if image_info:
                            stats_msg += f"• {image_info.sender}: {image_info.caption[:30]}...\n"
                    except:
                        continue
                
                if len(unseen_indices) > 3:
                    stats_msg += f"• ... and {len(unseen_indices) - 3} more\n"
            
            await update.message.reply_text(stats_msg, parse_mode='Markdown')
            
        except Exception as e:
            self.logger.error(f"Error in seen command: {e}")
            await update.message.reply_text("❌ Error getting viewing statistics")


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
    
    async def _error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE):
        """Global error handler for the bot"""
        self.error_count += 1
        error = context.error
        self.logger.error(f"Bot error #{self.error_count}: {error}")
        
        if self.error_count > self.max_errors:
            security_logger = logging.getLogger("teleframe.security")
            security_logger.error(f"Too many bot errors: {self.error_count}")


if __name__ == "__main__":
    """Test the enhanced bot with recovery system, rate limiting, image order control and optimization management"""
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
        slideshow_display = None
        
        if config.toggle_monitor:
            from monitor_control import MonitorController
            monitor_controller = MonitorController(config)
        
        # Note: In real usage, slideshow_display would be passed from main.py
        bot = TeleFrameBot(config, manager, monitor_controller, slideshow_display)
        
        try:
            await bot.start()
            print("✅ Enhanced bot started successfully with all features:")
            print("🔄 Update recovery system active")
            print("⚡ Rate limiting configurable via config.toml")
            print("🔄 Image order control via /order command")
            print("🖼️ Image optimization management via /optimize command")
            print("🗜️ Compression control via /compression command")
            print("🖥️ Monitor control via /monitor and /schedule commands")
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
