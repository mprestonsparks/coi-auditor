"""Fixed Rich logging handler that properly processes markup tags."""

import logging
from typing import Optional
from rich.logging import RichHandler
from rich.console import Console
from rich.text import Text
from .terminal_formatter import get_formatter

class FixedRichHandler(RichHandler):
    """A Rich logging handler that properly processes markup tags."""
    
    def __init__(self, *args, **kwargs):
        # Extract our custom parameters
        self.use_ansi_fallback = kwargs.pop('use_ansi_fallback', True)
        
        # Initialize the parent RichHandler
        super().__init__(*args, **kwargs)
        
        # Get our terminal formatter for fallback
        self.formatter_instance = get_formatter()
    
    def emit(self, record: logging.LogRecord) -> None:
        """Emit a log record with proper markup processing."""
        try:
            # Get the formatted message
            message = self.format(record)
            
            # Check if Rich markup is working properly
            if self.use_ansi_fallback and not self._rich_markup_working():
                # Use our ANSI formatter as fallback
                formatted_message = self.formatter_instance.format_message(message, record.levelname)
                print(formatted_message)
                return
            
            # Try to use Rich's normal processing
            super().emit(record)
            
        except Exception:
            # If Rich fails, fall back to our ANSI formatter
            if self.use_ansi_fallback:
                try:
                    message = self.format(record)
                    formatted_message = self.formatter_instance.format_message(message, record.levelname)
                    print(formatted_message)
                except Exception:
                    # Last resort: plain text
                    print(f"[{record.levelname}] {record.getMessage()}")
            else:
                self.handleError(record)
    
    def _rich_markup_working(self) -> bool:
        """Check if Rich markup is working properly."""
        try:
            # Test if Rich can properly render markup
            test_console = Console(file=None, force_terminal=True)
            test_text = Text.from_markup("[blue]test[/blue]")
            
            # If we can create the markup without error and it has styling, Rich is working
            return len(test_text.spans) > 0
        except Exception:
            return False

class PlainRichHandler(logging.Handler):
    """A simple handler that uses our terminal formatter directly."""
    
    def __init__(self, level: int = logging.NOTSET):
        super().__init__(level)
        self.formatter_instance = get_formatter()
    
    def emit(self, record: logging.LogRecord) -> None:
        """Emit a log record using our terminal formatter."""
        try:
            message = self.format(record)
            formatted_message = self.formatter_instance.format_message(message, record.levelname)
            print(formatted_message)
        except Exception:
            # Last resort: plain text
            print(f"[{record.levelname}] {record.getMessage()}")