"""Utilities for token counting and context management."""

import tiktoken
from typing import List
from .schemas import Message


class TokenCounter:
    """
    Token counter using tiktoken for accurate token counting.
    Implements the 'plus' requirement of using tokenizer-based counting.
    """
    
    def __init__(self, model: str = "gpt-4"):
        """
        Initialize token counter with a specific model encoding.
        
        Args:
            model: OpenAI model name for encoding selection
        """
        try:
            self.encoding = tiktoken.encoding_for_model(model)
        except KeyError:
            # Fallback to cl100k_base for newer models
            self.encoding = tiktoken.get_encoding("cl100k_base")
    
    def count_tokens(self, text: str) -> int:
        """
        Count tokens in a text string.
        
        Args:
            text: Input text
        
        Returns:
            Number of tokens
        """
        return len(self.encoding.encode(text))
    
    def count_message_tokens(self, message: Message) -> int:
        """
        Count tokens in a message, including role overhead.
        Approximates OpenAI's message token counting.
        
        Args:
            message: Message object
        
        Returns:
            Token count including overhead
        """
        # Format: role + content + structural tokens
        tokens = self.count_tokens(message.content)
        tokens += self.count_tokens(message.role)
        tokens += 4  # Overhead for message structure
        return tokens
    
    def count_messages_tokens(self, messages: List[Message]) -> int:
        """
        Count total tokens in a list of messages.
        
        Args:
            messages: List of Message objects
        
        Returns:
            Total token count
        """
        return sum(self.count_message_tokens(msg) for msg in messages)
    
    def estimate_token_count(self, text: str) -> int:
        """
        Quick estimation using heuristic (for fallback).
        Core requirement: ~4 characters per token.
        
        Args:
            text: Input text
        
        Returns:
            Estimated token count
        """
        return len(text) // 4
