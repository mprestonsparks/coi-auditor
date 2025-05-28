"""Terminal formatting utilities with proper ANSI color support and progress display."""

import sys
import os
import re
from typing import Optional, Dict, Any
from datetime import datetime
import threading
import time

class TerminalFormatter:
    """Handles terminal color formatting and progress display."""
    
    # ANSI color codes
    COLORS = {
        'black': '\033[30m',
        'red': '\033[31m',
        'green': '\033[32m',
        'yellow': '\033[33m',
        'blue': '\033[34m',
        'magenta': '\033[35m',
        'cyan': '\033[36m',
        'white': '\033[37m',
        'bright_black': '\033[90m',
        'bright_red': '\033[91m',
        'bright_green': '\033[92m',
        'bright_yellow': '\033[93m',
        'bright_blue': '\033[94m',
        'bright_magenta': '\033[95m',
        'bright_cyan': '\033[96m',
        'bright_white': '\033[97m',
    }
    
    # ANSI style codes
    STYLES = {
        'bold': '\033[1m',
        'dim': '\033[2m',
        'italic': '\033[3m',
        'underline': '\033[4m',
        'blink': '\033[5m',
        'reverse': '\033[7m',
        'strikethrough': '\033[9m',
    }
    
    # Reset code
    RESET = '\033[0m'
    
    # Cursor control
    CURSOR_UP = '\033[A'
    CURSOR_DOWN = '\033[B'
    CURSOR_FORWARD = '\033[C'
    CURSOR_BACK = '\033[D'
    SAVE_CURSOR = '\033[s'
    RESTORE_CURSOR = '\033[u'
    CLEAR_LINE = '\033[K'
    CLEAR_SCREEN = '\033[2J'
    MOVE_TO_COLUMN = '\033[{}G'
    MOVE_TO_POSITION = '\033[{};{}H'
    
    def __init__(self, force_color: bool = False):
        """Initialize the terminal formatter.
        
        Args:
            force_color: Force color output even if not detected as supported
        """
        self.force_color = force_color
        self.color_supported = self._detect_color_support()
        self.progress_active = False
        self.progress_thread = None
        self.progress_data = {}
        self.progress_lock = threading.Lock()
        
    def _detect_color_support(self) -> bool:
        """Detect if the terminal supports color output."""
        if self.force_color:
            return True
            
        # Check environment variables
        if os.getenv('NO_COLOR'):
            return False
            
        if os.getenv('FORCE_COLOR'):
            return True
            
        # Check if we're in a terminal
        if not sys.stdout.isatty():
            return False
            
        # Check TERM environment variable
        term = os.getenv('TERM', '').lower()
        if any(term_type in term for term_type in ['color', 'ansi', 'xterm', 'screen']):
            return True
            
        # Windows-specific checks
        if os.name == 'nt':
            # Windows 10 version 1607 and later support ANSI escape sequences
            try:
                import platform
                version = platform.version()
                if version:
                    # Extract build number
                    build = int(version.split('.')[-1])
                    return build >= 14393  # Windows 10 build 1607
            except (ValueError, AttributeError):
                pass
                
            # Check for Windows Terminal or other modern terminals
            if os.getenv('WT_SESSION') or os.getenv('TERM_PROGRAM'):
                return True
                
        return False
    
    def colorize(self, text: str, color: Optional[str] = None, style: Optional[str] = None) -> str:
        """Apply color and style to text.
        
        Args:
            text: Text to colorize
            color: Color name from COLORS dict
            style: Style name from STYLES dict
            
        Returns:
            Formatted text with ANSI codes if supported, plain text otherwise
        """
        if not self.color_supported:
            return text
            
        codes = []
        
        if style and style in self.STYLES:
            codes.append(self.STYLES[style])
            
        if color and color in self.COLORS:
            codes.append(self.COLORS[color])
            
        if codes:
            return ''.join(codes) + text + self.RESET
        
        return text
    
    def parse_rich_markup(self, text: str) -> str:
        """Parse Rich-style markup tags and convert to ANSI codes.
        
        Args:
            text: Text with Rich markup tags like [blue]text[/blue]
            
        Returns:
            Text with ANSI color codes
        """
        if not self.color_supported:
            # Remove all markup tags if colors aren't supported
            return re.sub(r'\[/?[^\]]+\]', '', text)
        
        # Handle combined style and color tags like [bold red]
        def replace_combined_tag(match):
            tag_content = match.group(1)
            is_closing = tag_content.startswith('/')
            
            if is_closing:
                return self.RESET
            
            parts = tag_content.split()
            codes = []
            
            for part in parts:
                if part in self.STYLES:
                    codes.append(self.STYLES[part])
                elif part in self.COLORS:
                    codes.append(self.COLORS[part])
                # Handle color aliases
                elif part == 'grey':
                    codes.append(self.COLORS['bright_black'])
                elif part == 'orange':
                    codes.append(self.COLORS['yellow'])
            
            return ''.join(codes)
        
        # Replace combined tags first
        text = re.sub(r'\[([^\]]+)\]', replace_combined_tag, text)
        
        # Handle closing tags that might have been missed
        text = re.sub(r'\[/[^\]]+\]', self.RESET, text)
        
        return text
    
    def format_message(self, message: str, level: str = 'INFO') -> str:
        """Format a log message with appropriate colors.
        
        Args:
            message: The message to format
            level: Log level (INFO, WARNING, ERROR, DEBUG)
            
        Returns:
            Formatted message
        """
        # Parse Rich markup first
        formatted_message = self.parse_rich_markup(message)
        
        # Add level-specific formatting
        level_colors = {
            'DEBUG': ('bright_black', None),
            'INFO': ('bright_blue', None),
            'WARNING': ('yellow', 'bold'),
            'ERROR': ('red', 'bold'),
            'CRITICAL': ('bright_red', 'bold'),
        }
        
        if level.upper() in level_colors:
            color, style = level_colors[level.upper()]
            timestamp = datetime.now().strftime('%H:%M:%S')
            level_tag = self.colorize(f'[{level}]', color, style)
            time_tag = self.colorize(f'[{timestamp}]', 'bright_black')
            return f'{time_tag} {level_tag} {formatted_message}'
        
        return formatted_message
    
    def print_header(self, title: str, width: int = 80) -> None:
        """Print a formatted header.
        
        Args:
            title: Header title
            width: Total width of the header
        """
        border = '=' * width
        title_line = f' {title} '.center(width, '=')
        
        print(self.colorize(border, 'cyan', 'bold'))
        print(self.colorize(title_line, 'cyan', 'bold'))
        print(self.colorize(border, 'cyan', 'bold'))
    
    def print_section(self, title: str, width: int = 60) -> None:
        """Print a formatted section header.
        
        Args:
            title: Section title
            width: Total width of the section header
        """
        border = '-' * width
        title_line = f' {title} '.center(width, '-')
        
        print(self.colorize(title_line, 'yellow', 'bold'))
    
    def start_progress(self, total: int, description: str = "Processing") -> None:
        """Start a progress display at the bottom of the screen.
        
        Args:
            total: Total number of items to process
            description: Description of the progress
        """
        with self.progress_lock:
            self.progress_data = {
                'total': total,
                'current': 0,
                'description': description,
                'start_time': time.time(),
                'current_item': '',
                'status': 'OK'
            }
            self.progress_active = True
            
        # Start progress display thread
        self.progress_thread = threading.Thread(target=self._progress_display_loop, daemon=True)
        self.progress_thread.start()
    
    def update_progress(self, current: int, current_item: str = '', status: str = 'OK') -> None:
        """Update the progress display.
        
        Args:
            current: Current progress count
            current_item: Description of current item being processed
            status: Status of current item (OK, ERROR, WARNING)
        """
        with self.progress_lock:
            if self.progress_active:
                self.progress_data['current'] = current
                self.progress_data['current_item'] = current_item
                self.progress_data['status'] = status
    
    def stop_progress(self) -> None:
        """Stop the progress display."""
        with self.progress_lock:
            self.progress_active = False
            
        if self.progress_thread and self.progress_thread.is_alive():
            self.progress_thread.join(timeout=1.0)
            
        # Clear the progress line
        if self.color_supported:
            print('\r' + ' ' * 100 + '\r', end='', flush=True)
    
    def _progress_display_loop(self) -> None:
        """Internal method to display progress in a loop."""
        while True:
            with self.progress_lock:
                if not self.progress_active:
                    break
                    
                data = self.progress_data.copy()
            
            # Calculate progress
            if data['total'] > 0:
                percentage = (data['current'] / data['total']) * 100
                bar_width = 30
                filled_width = int((data['current'] / data['total']) * bar_width)
                bar = '█' * filled_width + '░' * (bar_width - filled_width)
            else:
                percentage = 0
                bar = '░' * 30
            
            # Calculate elapsed time and ETA
            elapsed = time.time() - data['start_time']
            if data['current'] > 0 and data['total'] > 0:
                eta = (elapsed / data['current']) * (data['total'] - data['current'])
                eta_str = f"{int(eta//60):02d}:{int(eta%60):02d}"
            else:
                eta_str = "--:--"
            
            # Format status color
            status_colors = {
                'OK': 'green',
                'ERROR': 'red',
                'WARNING': 'yellow'
            }
            status_color = status_colors.get(data['status'], 'white')
            
            # Build progress line
            progress_line = (
                f"\r{self.colorize(data['description'], 'cyan')}: "
                f"{self.colorize(bar, 'blue')} "
                f"{percentage:5.1f}% "
                f"({data['current']}/{data['total']}) "
                f"ETA: {eta_str} "
                f"[{self.colorize(data['status'], status_color)}] "
                f"{data['current_item'][:30]:<30}"
            )
            
            # Print progress line
            print(progress_line, end='', flush=True)
            
            time.sleep(0.1)  # Update 10 times per second
    
    def success(self, message: str) -> None:
        """Print a success message."""
        formatted = self.colorize('✓ SUCCESS: ', 'green', 'bold') + self.parse_rich_markup(message)
        print(formatted)
    
    def warning(self, message: str) -> None:
        """Print a warning message."""
        formatted = self.colorize('⚠ WARNING: ', 'yellow', 'bold') + self.parse_rich_markup(message)
        print(formatted)
    
    def error(self, message: str) -> None:
        """Print an error message."""
        formatted = self.colorize('✗ ERROR: ', 'red', 'bold') + self.parse_rich_markup(message)
        print(formatted)
    
    def info(self, message: str) -> None:
        """Print an info message."""
        formatted = self.colorize('ℹ INFO: ', 'blue', 'bold') + self.parse_rich_markup(message)
        print(formatted)


# Global formatter instance
_formatter = None

def get_formatter() -> TerminalFormatter:
    """Get the global terminal formatter instance."""
    global _formatter
    if _formatter is None:
        _formatter = TerminalFormatter()
    return _formatter

def colorize(text: str, color: Optional[str] = None, style: Optional[str] = None) -> str:
    """Convenience function to colorize text."""
    return get_formatter().colorize(text, color, style)

def parse_rich_markup(text: str) -> str:
    """Convenience function to parse Rich markup."""
    return get_formatter().parse_rich_markup(text)

def format_message(message: str, level: str = 'INFO') -> str:
    """Convenience function to format a message."""
    return get_formatter().format_message(message, level)