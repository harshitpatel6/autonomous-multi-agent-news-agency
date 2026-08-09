"""
Unit tests for API key validation
"""
import os
import pytest
from unittest.mock import patch, MagicMock
from utils.api_validator import (
    validate_anthropic_key,
    validate_groq_key,
    validate_api_keys_on_startup
)


class TestAnthropicValidation:
    """Tests for Anthropic API key validation"""
    
    def test_missing_key(self):
        """Test when ANTHROPIC_API_KEY is not set"""
        with patch.dict(os.environ, {}, clear=True):
            valid, error = validate_anthropic_key()
            assert not valid
            assert "not set" in error.lower()
    
    def test_placeholder_key(self):
        """Test detection of placeholder keys"""
        placeholder_keys = [
            "sk_ant_YOUR_ACTUAL_KEY_HERE",
            "sk-ant-your_key_here",
            "sk-ant-placeholder123",
            "sk-ant-xxx"
        ]
        
        for key in placeholder_keys:
            with patch.dict(os.environ, {"ANTHROPIC_API_KEY": key}):
                valid, error = validate_anthropic_key()
                assert not valid
                assert "placeholder" in error.lower()
    
    def test_invalid_format(self):
        """Test detection of invalid key format"""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "invalid_key_format"}):
            valid, error = validate_anthropic_key()
            assert not valid
            assert "format" in error.lower()
    
    @patch('anthropic.Anthropic')
    def test_valid_key(self, mock_anthropic_class):
        """Test successful validation with valid key"""
        # Mock successful API call
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client
        mock_client.messages.create.return_value = MagicMock()
        
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-valid_key_12345"}):
            valid, error = validate_anthropic_key()
            assert valid
            assert error is None
    
    @patch('anthropic.Anthropic')
    def test_authentication_failure(self, mock_anthropic_class):
        """Test handling of authentication failures"""
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client
        # Simply raise a generic exception that mimics authentication failure
        mock_client.messages.create.side_effect = Exception("authentication failed: Invalid API key")
        
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-invalid_key_12345"}):
            valid, error = validate_anthropic_key()
            assert not valid
            assert "test failed" in error.lower()


class TestGroqValidation:
    """Tests for Groq API key validation"""
    
    def test_missing_key(self):
        """Test when GROQ_API_KEY is not set"""
        with patch.dict(os.environ, {}, clear=True):
            valid, error = validate_groq_key()
            assert not valid
            assert "not set" in error.lower()
    
    def test_placeholder_key(self):
        """Test detection of placeholder keys"""
        placeholder_keys = [
            "gsk_your_key_here",
            "gsk_placeholder123",
            "gsk_xxx"
        ]
        
        for key in placeholder_keys:
            with patch.dict(os.environ, {"GROQ_API_KEY": key}):
                valid, error = validate_groq_key()
                assert not valid
                assert "placeholder" in error.lower()
    
    def test_invalid_format(self):
        """Test detection of invalid key format"""
        with patch.dict(os.environ, {"GROQ_API_KEY": "invalid_key_format"}):
            valid, error = validate_groq_key()
            assert not valid
            assert "format" in error.lower()
    
    @patch('groq.Groq')
    def test_valid_key(self, mock_groq_class):
        """Test successful validation with valid key"""
        # Mock successful API call
        mock_client = MagicMock()
        mock_groq_class.return_value = mock_client
        mock_client.chat.completions.create.return_value = MagicMock()
        
        with patch.dict(os.environ, {"GROQ_API_KEY": "gsk_valid_key_12345"}):
            valid, error = validate_groq_key()
            assert valid
            assert error is None
    
    @patch('groq.Groq')
    def test_authentication_failure(self, mock_groq_class):
        """Test handling of authentication failures"""
        mock_client = MagicMock()
        mock_groq_class.return_value = mock_client
        mock_client.chat.completions.create.side_effect = Exception("401 Authentication failed")
        
        with patch.dict(os.environ, {"GROQ_API_KEY": "gsk_invalid_key_12345"}):
            valid, error = validate_groq_key()
            assert not valid
            assert "authentication failed" in error.lower()


class TestStartupValidation:
    """Tests for full startup validation"""
    
    @patch('utils.api_validator.validate_groq_key')
    @patch('utils.api_validator.validate_anthropic_key')
    def test_both_keys_valid(self, mock_anthropic, mock_groq):
        """Test when both API keys are valid"""
        mock_anthropic.return_value = (True, None)
        mock_groq.return_value = (True, None)
        
        result = validate_api_keys_on_startup()
        
        assert result["anthropic"]["valid"]
        assert result["groq"]["valid"]
        assert result["has_valid_key"]
        assert result["can_proceed"]
    
    @patch('utils.api_validator.validate_groq_key')
    @patch('utils.api_validator.validate_anthropic_key')
    def test_only_anthropic_valid(self, mock_anthropic, mock_groq):
        """Test when only Anthropic key is valid"""
        mock_anthropic.return_value = (True, None)
        mock_groq.return_value = (False, "Groq API failed")
        
        result = validate_api_keys_on_startup()
        
        assert result["anthropic"]["valid"]
        assert not result["groq"]["valid"]
        assert result["has_valid_key"]
        assert result["can_proceed"]
    
    @patch('utils.api_validator.validate_groq_key')
    @patch('utils.api_validator.validate_anthropic_key')
    def test_only_groq_valid(self, mock_anthropic, mock_groq):
        """Test when only Groq key is valid"""
        mock_anthropic.return_value = (False, "Anthropic API failed")
        mock_groq.return_value = (True, None)
        
        result = validate_api_keys_on_startup()
        
        assert not result["anthropic"]["valid"]
        assert result["groq"]["valid"]
        assert result["has_valid_key"]
        assert result["can_proceed"]
    
    @patch('utils.api_validator.validate_groq_key')
    @patch('utils.api_validator.validate_anthropic_key')
    def test_no_valid_keys(self, mock_anthropic, mock_groq):
        """Test when no API keys are valid - should raise RuntimeError"""
        mock_anthropic.return_value = (False, "Anthropic API failed")
        mock_groq.return_value = (False, "Groq API failed")
        
        with pytest.raises(RuntimeError) as exc_info:
            validate_api_keys_on_startup()
        
        assert "no valid api keys" in str(exc_info.value).lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
