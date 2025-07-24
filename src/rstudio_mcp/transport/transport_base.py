"""Base transport layer interface."""

import asyncio
import logging
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Callable, Dict, Optional


class ConnectionState(Enum):
    """Connection state enumeration."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    ERROR = "error"


class TransportBase(ABC):
    """Base class for transport implementations."""
    
    def __init__(self, name: str):
        """Initialize transport.
        
        Args:
            name: Transport name
        """
        self.name = name
        self.logger = logging.getLogger(f"{__name__}.{name}")
        self.state = ConnectionState.DISCONNECTED
        self._message_handlers: Dict[str, Callable] = {}
        self._error_handlers: Dict[str, Callable] = {}
        self._connection_handlers: Dict[str, Callable] = {}
        
    @abstractmethod
    async def start(self, **kwargs) -> None:
        """Start the transport.
        
        Args:
            **kwargs: Transport-specific arguments
        """
        pass
    
    @abstractmethod
    async def stop(self) -> None:
        """Stop the transport."""
        pass
    
    @abstractmethod
    async def send_message(self, message: Dict[str, Any]) -> None:
        """Send a message through the transport.
        
        Args:
            message: Message to send
        """
        pass
    
    def register_message_handler(self, event: str, handler: Callable) -> None:
        """Register a message handler.
        
        Args:
            event: Event name
            handler: Handler function
        """
        self._message_handlers[event] = handler
        self.logger.debug(f"Registered message handler for event: {event}")
    
    def register_error_handler(self, event: str, handler: Callable) -> None:
        """Register an error handler.
        
        Args:
            event: Event name
            handler: Handler function
        """
        self._error_handlers[event] = handler
        self.logger.debug(f"Registered error handler for event: {event}")
    
    def register_connection_handler(self, event: str, handler: Callable) -> None:
        """Register a connection handler.
        
        Args:
            event: Event name (connect, disconnect, reconnect)
            handler: Handler function
        """
        self._connection_handlers[event] = handler
        self.logger.debug(f"Registered connection handler for event: {event}")
    
    async def _handle_message(self, event: str, *args, **kwargs) -> None:
        """Handle incoming message.
        
        Args:
            event: Event name
            *args: Event arguments
            **kwargs: Event keyword arguments
        """
        if event in self._message_handlers:
            try:
                await self._message_handlers[event](*args, **kwargs)
            except Exception as e:
                self.logger.error(f"Error handling message event '{event}': {e}")
                await self._handle_error("message_handler_error", e)
    
    async def _handle_error(self, event: str, error: Exception) -> None:
        """Handle transport error.
        
        Args:
            event: Error event name
            error: Error that occurred
        """
        self.logger.error(f"Transport error in event '{event}': {error}")
        
        if event in self._error_handlers:
            try:
                await self._error_handlers[event](error)
            except Exception as e:
                self.logger.error(f"Error in error handler for '{event}': {e}")
    
    async def _handle_connection_event(self, event: str, *args, **kwargs) -> None:
        """Handle connection event.
        
        Args:
            event: Connection event name
            *args: Event arguments
            **kwargs: Event keyword arguments
        """
        if event in self._connection_handlers:
            try:
                await self._connection_handlers[event](*args, **kwargs)
            except Exception as e:
                self.logger.error(f"Error handling connection event '{event}': {e}")
    
    def _set_state(self, new_state: ConnectionState) -> None:
        """Set connection state.
        
        Args:
            new_state: New connection state
        """
        if self.state != new_state:
            old_state = self.state
            self.state = new_state
            self.logger.info(f"Transport state changed: {old_state.value} -> {new_state.value}")