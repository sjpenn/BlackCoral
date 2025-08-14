"""
Unified AI provider interface for BLACK CORAL
Supports Claude, Google Gemini, and OpenRouter with fallback capabilities
"""

import logging
import time
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass
from enum import Enum

import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


class AIProvider(Enum):
    """Available AI providers"""
    CLAUDE = "claude"
    GEMINI = "gemini"
    OPENROUTER = "openrouter"


class ModelType(Enum):
    """AI model capability types"""
    ANALYSIS = "analysis"
    GENERATION = "generation"
    SUMMARIZATION = "summarization"
    CLASSIFICATION = "classification"


@dataclass
class AIResponse:
    """Standardized AI response format"""
    content: str
    provider: AIProvider
    model: str
    tokens_used: Optional[int] = None
    cost: Optional[float] = None
    processing_time: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class AIRequest:
    """Standardized AI request format"""
    prompt: str
    system_prompt: Optional[str] = None
    model_type: ModelType = ModelType.ANALYSIS
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    context: Optional[Dict[str, Any]] = None


class BaseAIProvider(ABC):
    """Abstract base class for AI providers"""
    
    def __init__(self, api_key: str, **kwargs):
        self.api_key = api_key
        self.rate_limit_delay = kwargs.get('rate_limit_delay', 1.0)
        self._last_request_time = 0
        
    def _rate_limit(self):
        """Simple rate limiting"""
        current_time = time.time()
        time_since_last = current_time - self._last_request_time
        if time_since_last < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - time_since_last)
        self._last_request_time = time.time()
    
    @abstractmethod
    def get_available_models(self) -> List[str]:
        """Get list of available models for this provider"""
        pass
    
    @abstractmethod
    def generate_response(self, request: AIRequest) -> AIResponse:
        """Generate AI response for the given request"""
        pass
    
    @abstractmethod
    def get_recommended_model(self, model_type: ModelType) -> str:
        """Get recommended model for specific task type"""
        pass


class ClaudeProvider(BaseAIProvider):
    """Claude API provider using Anthropic's API"""
    
    BASE_URL = "https://api.anthropic.com/v1/messages"
    
    def __init__(self, api_key: str, **kwargs):
        super().__init__(api_key, **kwargs)
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'X-API-Key': self.api_key,
            'anthropic-version': '2023-06-01'
        })
    
    def get_available_models(self) -> List[str]:
        """Get available Claude models"""
        return [
            'claude-3-5-sonnet-20241022',
            'claude-3-5-haiku-20241022', 
            'claude-3-opus-20240229',
            'claude-3-sonnet-20240229',
            'claude-3-haiku-20240307'
        ]
    
    def get_recommended_model(self, model_type: ModelType) -> str:
        """Get recommended Claude model for task type"""
        recommendations = {
            ModelType.ANALYSIS: 'claude-3-5-sonnet-20241022',
            ModelType.GENERATION: 'claude-3-5-sonnet-20241022',
            ModelType.SUMMARIZATION: 'claude-3-5-haiku-20241022',
            ModelType.CLASSIFICATION: 'claude-3-5-haiku-20241022'
        }
        return recommendations.get(model_type, 'claude-3-5-sonnet-20241022')
    
    def generate_response(self, request: AIRequest) -> AIResponse:
        """Generate response using Claude API"""
        self._rate_limit()
        start_time = time.time()
        
        model = self.get_recommended_model(request.model_type)
        
        messages = []
        if request.system_prompt:
            messages.append({
                "role": "user",
                "content": f"{request.system_prompt}\n\n{request.prompt}"
            })
        else:
            messages.append({
                "role": "user", 
                "content": request.prompt
            })
        
        payload = {
            "model": model,
            "max_tokens": request.max_tokens or 4000,
            "messages": messages,
            "temperature": request.temperature or 0.7
        }
        
        try:
            response = self.session.post(self.BASE_URL, json=payload, timeout=60)
            response.raise_for_status()
            
            data = response.json()
            content = data['content'][0]['text']
            
            processing_time = time.time() - start_time
            
            return AIResponse(
                content=content,
                provider=AIProvider.CLAUDE,
                model=model,
                tokens_used=data.get('usage', {}).get('output_tokens'),
                processing_time=processing_time,
                metadata={'usage': data.get('usage')}
            )
            
        except Exception as e:
            logger.error(f"Claude API error: {e}")
            raise


class GeminiProvider(BaseAIProvider):
    """Google Gemini provider"""
    
    BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    
    def __init__(self, api_key: str, **kwargs):
        super().__init__(api_key, **kwargs)
        self.session = requests.Session()
    
    def get_available_models(self) -> List[str]:
        """Get available Gemini models"""
        return [
            'gemini-1.5-pro',
            'gemini-1.5-flash',
            'gemini-1.0-pro'
        ]
    
    def get_recommended_model(self, model_type: ModelType) -> str:
        """Get recommended Gemini model for task type"""
        recommendations = {
            ModelType.ANALYSIS: 'gemini-1.5-pro',
            ModelType.GENERATION: 'gemini-1.5-pro',
            ModelType.SUMMARIZATION: 'gemini-1.5-flash',
            ModelType.CLASSIFICATION: 'gemini-1.5-flash'
        }
        return recommendations.get(model_type, 'gemini-1.5-flash')
    
    def generate_response(self, request: AIRequest) -> AIResponse:
        """Generate response using Gemini API"""
        self._rate_limit()
        start_time = time.time()
        
        model = self.get_recommended_model(request.model_type)
        url = self.BASE_URL.format(model=model)
        
        prompt_text = request.prompt
        if request.system_prompt:
            prompt_text = f"{request.system_prompt}\n\n{prompt_text}"
        
        payload = {
            "contents": [{
                "parts": [{"text": prompt_text}]
            }],
            "generationConfig": {
                "temperature": request.temperature or 0.7,
                "maxOutputTokens": request.max_tokens or 4000
            }
        }
        
        try:
            response = self.session.post(
                url,
                json=payload,
                params={'key': self.api_key},
                timeout=60
            )
            response.raise_for_status()
            
            data = response.json()
            content = data['candidates'][0]['content']['parts'][0]['text']
            
            processing_time = time.time() - start_time
            
            return AIResponse(
                content=content,
                provider=AIProvider.GEMINI,
                model=model,
                tokens_used=data.get('usageMetadata', {}).get('totalTokenCount'),
                processing_time=processing_time,
                metadata={'usageMetadata': data.get('usageMetadata')}
            )
            
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            raise


class OpenRouterProvider(BaseAIProvider):
    """OpenRouter provider for multiple AI models"""
    
    BASE_URL = "https://openrouter.ai/api/v1/chat/completions"
    
    def __init__(self, api_key: str, **kwargs):
        super().__init__(api_key, **kwargs)
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.api_key}',
            'HTTP-Referer': kwargs.get('site_url', 'https://blackcoral.ai'),
            'X-Title': kwargs.get('site_name', 'BLACK CORAL')
        })
    
    def get_available_models(self) -> List[str]:
        """Get available OpenRouter models (subset of popular ones)"""
        return [
            'openai/gpt-4o',
            'openai/gpt-4o-mini',
            'anthropic/claude-3.5-sonnet',
            'anthropic/claude-3-haiku',
            'google/gemini-pro',
            'meta-llama/llama-3.1-8b-instruct:free',
            'microsoft/wizardlm-2-8x22b'
        ]
    
    def get_recommended_model(self, model_type: ModelType) -> str:
        """Get recommended OpenRouter model for task type"""
        recommendations = {
            ModelType.ANALYSIS: 'anthropic/claude-3.5-sonnet',
            ModelType.GENERATION: 'openai/gpt-4o',
            ModelType.SUMMARIZATION: 'openai/gpt-4o-mini',
            ModelType.CLASSIFICATION: 'meta-llama/llama-3.1-8b-instruct:free'
        }
        return recommendations.get(model_type, 'openai/gpt-4o-mini')
    
    def generate_response(self, request: AIRequest) -> AIResponse:
        """Generate response using OpenRouter API"""
        self._rate_limit()
        start_time = time.time()
        
        model = self.get_recommended_model(request.model_type)
        
        messages = []
        if request.system_prompt:
            messages.append({
                "role": "system",
                "content": request.system_prompt
            })
        
        messages.append({
            "role": "user",
            "content": request.prompt
        })
        
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": request.max_tokens or 4000,
            "temperature": request.temperature or 0.7
        }
        
        try:
            response = self.session.post(self.BASE_URL, json=payload, timeout=60)
            response.raise_for_status()
            
            data = response.json()
            content = data['choices'][0]['message']['content']
            
            processing_time = time.time() - start_time
            
            return AIResponse(
                content=content,
                provider=AIProvider.OPENROUTER,
                model=model,
                tokens_used=data.get('usage', {}).get('total_tokens'),
                processing_time=processing_time,
                metadata={'usage': data.get('usage')}
            )
            
        except Exception as e:
            logger.error(f"OpenRouter API error: {e}")
            raise


class AIManager:
    """Unified AI manager with fallback capabilities"""
    
    def __init__(self):
        self.providers = {}
        self._initialize_providers()
    
    def _initialize_providers(self):
        """Initialize available AI providers based on configuration"""
        
        # Claude provider
        if hasattr(settings, 'ANTHROPIC_API_KEY') and settings.ANTHROPIC_API_KEY:
            try:
                self.providers[AIProvider.CLAUDE] = ClaudeProvider(
                    api_key=settings.ANTHROPIC_API_KEY
                )
                logger.info("Claude provider initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Claude provider: {e}")
        
        # Gemini provider
        if hasattr(settings, 'GOOGLE_AI_API_KEY') and settings.GOOGLE_AI_API_KEY:
            try:
                self.providers[AIProvider.GEMINI] = GeminiProvider(
                    api_key=settings.GOOGLE_AI_API_KEY
                )
                logger.info("Gemini provider initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Gemini provider: {e}")
        
        # OpenRouter provider
        if hasattr(settings, 'OPENROUTER_API_KEY') and settings.OPENROUTER_API_KEY:
            try:
                self.providers[AIProvider.OPENROUTER] = OpenRouterProvider(
                    api_key=settings.OPENROUTER_API_KEY,
                    site_url=getattr(settings, 'SITE_URL', 'https://blackcoral.ai'),
                    site_name=getattr(settings, 'SITE_NAME', 'BLACK CORAL')
                )
                logger.info("OpenRouter provider initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize OpenRouter provider: {e}")
    
    def get_available_providers(self) -> List[AIProvider]:
        """Get list of available providers"""
        return list(self.providers.keys())
    
    def generate_response(self, request: AIRequest, 
                         preferred_provider: Optional[AIProvider] = None,
                         fallback: bool = True) -> AIResponse:
        """Generate AI response with optional fallback"""
        
        if not self.providers:
            raise Exception("No AI providers available")
        
        # Determine provider order
        providers_to_try = []
        if preferred_provider and preferred_provider in self.providers:
            providers_to_try.append(preferred_provider)
        
        # Add remaining providers for fallback
        if fallback:
            for provider in self.providers.keys():
                if provider not in providers_to_try:
                    providers_to_try.append(provider)
        
        last_error = None
        for provider in providers_to_try:
            try:
                logger.info(f"Attempting AI request with {provider.value}")
                response = self.providers[provider].generate_response(request)
                logger.info(f"AI request successful with {provider.value}")
                return response
            except Exception as e:
                logger.warning(f"AI request failed with {provider.value}: {e}")
                last_error = e
                continue
        
        # If all providers failed
        if last_error:
            raise last_error
        else:
            raise Exception("No AI providers succeeded")
    
    def get_model_info(self) -> Dict[str, List[str]]:
        """Get available models for each provider"""
        info = {}
        for provider, client in self.providers.items():
            try:
                info[provider.value] = client.get_available_models()
            except Exception as e:
                logger.warning(f"Could not get models for {provider.value}: {e}")
                info[provider.value] = []
        return info


# Global AI manager instance
ai_manager = AIManager()