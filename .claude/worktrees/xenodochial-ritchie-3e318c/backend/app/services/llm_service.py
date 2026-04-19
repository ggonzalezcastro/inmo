"""
DEPRECATED: Use app.services.llm_service_facade.LLMServiceFacade instead.

This module is kept for backward compatibility. All call sites have been
migrated to llm_service_facade. New code must use LLMServiceFacade or
the provider abstraction (app.services.llm.factory.get_llm_provider).
"""
import logging
import warnings

from app.services.llm.facade import LLMServiceFacade

logger = logging.getLogger(__name__)

warnings.warn(
    "app.services.llm_service.LLMService is deprecated; use app.services.llm_service_facade.LLMServiceFacade instead.",
    DeprecationWarning,
    stacklevel=2,
)
logger.warning(
    "llm_service.LLMService is deprecated. Use llm_service_facade.LLMServiceFacade instead."
)

# Re-export facade as LLMService so any remaining imports keep working
LLMService = LLMServiceFacade
