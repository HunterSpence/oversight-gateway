"""LangChain/LangGraph integration for Oversight Gateway

This module provides middleware for LangChain agents to automatically
route tool calls through Oversight Gateway for risk evaluation and
checkpoint triggering.

Usage:
    from oversight_gateway.integrations.langchain import OversightMiddleware
    from oversight_gateway_sdk import AsyncOversightClient
    
    client = AsyncOversightClient("http://localhost:8001", "your-api-key")
    middleware = OversightMiddleware(client=client, session_id="agent-session-1")
    
    # Use with LangChain agent
    # The middleware will intercept tool calls and evaluate them
"""
from typing import Optional, Dict, Any, Callable, Awaitable
import asyncio
import structlog

try:
    from langchain_core.tools import BaseTool
    from langchain_core.callbacks import AsyncCallbackHandler
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False
    BaseTool = object
    AsyncCallbackHandler = object

from oversight_gateway_sdk import AsyncOversightClient, EvaluationResult

logger = structlog.get_logger()


class OversightCallback(AsyncCallbackHandler):
    """LangChain callback for Oversight Gateway integration"""
    
    def __init__(
        self,
        client: AsyncOversightClient,
        session_id: str = "default",
        on_checkpoint: Optional[Callable[[EvaluationResult], Awaitable[bool]]] = None
    ):
        """
        Initialize Oversight callback.
        
        Args:
            client: AsyncOversightClient instance
            session_id: Session identifier for risk tracking
            on_checkpoint: Async callback function to handle checkpoints
                          Should return True to approve, False to reject
        """
        self.client = client
        self.session_id = session_id
        self.on_checkpoint = on_checkpoint
    
    async def on_tool_start(
        self,
        serialized: Dict[str, Any],
        input_str: str,
        **kwargs: Any
    ) -> None:
        """Called when a tool starts executing"""
        tool_name = serialized.get("name", "unknown_tool")
        
        logger.info("evaluating_tool_call", tool=tool_name, input=input_str[:100])
        
        # Evaluate with Oversight Gateway
        result = await self.client.evaluate(
            action=tool_name,
            session_id=self.session_id,
            target=input_str[:200],  # Use input as target (truncated)
            metadata={
                "tool_input": input_str,
                "serialized": serialized,
            }
        )
        
        # If checkpoint needed, invoke callback
        if result.needs_checkpoint:
            logger.warning(
                "checkpoint_triggered",
                tool=tool_name,
                risk_score=result.risk_score,
                reason=result.checkpoint_reason
            )
            
            if self.on_checkpoint:
                approved = await self.on_checkpoint(result)
                
                # Record approval in gateway
                await self.client.approve(
                    result.action_id,
                    approved=approved,
                    channel="langchain"
                )
                
                if not approved:
                    raise PermissionError(
                        f"Action '{tool_name}' rejected by Oversight Gateway. "
                        f"Risk: {result.risk_score:.3f}, Reason: {result.checkpoint_reason}"
                    )
            else:
                # No callback provided - auto-reject high-risk actions
                logger.error("no_checkpoint_handler", tool=tool_name)
                raise PermissionError(
                    f"Action '{tool_name}' requires approval but no checkpoint handler is configured. "
                    f"Risk: {result.risk_score:.3f}"
                )
        else:
            logger.info(
                "action_approved",
                tool=tool_name,
                risk_score=result.risk_score
            )
    
    async def on_tool_end(
        self,
        output: str,
        **kwargs: Any
    ) -> None:
        """Called when a tool finishes executing"""
        # Could be used to record actual outcomes vs predicted risk
        pass
    
    async def on_tool_error(
        self,
        error: BaseException,
        **kwargs: Any
    ) -> None:
        """Called when a tool encounters an error"""
        # Could record as near-miss if error was preventable
        pass


class OversightMiddleware:
    """
    Middleware wrapper for LangChain agents with Oversight Gateway integration.
    
    Example:
        client = AsyncOversightClient("http://localhost:8001", "api-key")
        
        async def approval_handler(result: EvaluationResult) -> bool:
            print(f"Approval needed: {result.checkpoint_reason}")
            response = input("Approve? (y/n): ")
            return response.lower() == 'y'
        
        middleware = OversightMiddleware(
            client=client,
            session_id="my-session",
            on_checkpoint=approval_handler
        )
        
        # Add to LangChain agent callbacks
        agent.run("do something", callbacks=[middleware.callback])
    """
    
    def __init__(
        self,
        gateway_url: Optional[str] = None,
        api_key: Optional[str] = None,
        client: Optional[AsyncOversightClient] = None,
        session_id: str = "default",
        on_checkpoint: Optional[Callable[[EvaluationResult], Awaitable[bool]]] = None
    ):
        """
        Initialize Oversight middleware.
        
        Args:
            gateway_url: Gateway URL (if client not provided)
            api_key: API key (if client not provided)
            client: Pre-configured AsyncOversightClient
            session_id: Session identifier
            on_checkpoint: Async callback for handling checkpoints
        """
        if not LANGCHAIN_AVAILABLE:
            raise ImportError(
                "LangChain integration requires langchain-core. "
                "Install with: pip install langchain-core"
            )
        
        if client:
            self.client = client
        elif gateway_url and api_key:
            self.client = AsyncOversightClient(gateway_url, api_key)
        else:
            raise ValueError("Either 'client' or both 'gateway_url' and 'api_key' must be provided")
        
        self.session_id = session_id
        self.callback = OversightCallback(self.client, session_id, on_checkpoint)
    
    def get_callback(self) -> OversightCallback:
        """Get the LangChain callback instance"""
        return self.callback


# Convenience function for wrapping tools

async def wrap_tool_with_oversight(
    tool: BaseTool,
    client: AsyncOversightClient,
    session_id: str = "default",
    on_checkpoint: Optional[Callable[[EvaluationResult], Awaitable[bool]]] = None
) -> BaseTool:
    """
    Wrap a LangChain tool with Oversight Gateway evaluation.
    
    Args:
        tool: LangChain tool to wrap
        client: AsyncOversightClient instance
        session_id: Session identifier
        on_checkpoint: Async callback for handling checkpoints
        
    Returns:
        Wrapped tool that evaluates actions before execution
    """
    original_run = tool._arun if hasattr(tool, "_arun") else tool._run
    
    async def oversight_run(*args, **kwargs):
        # Evaluate action
        result = await client.evaluate(
            action=tool.name,
            session_id=session_id,
            target=str(args[0]) if args else "unknown",
            metadata={"args": str(args), "kwargs": str(kwargs)}
        )
        
        # Check for checkpoint
        if result.needs_checkpoint:
            if on_checkpoint:
                approved = await on_checkpoint(result)
                await client.approve(result.action_id, approved, channel="langchain")
                if not approved:
                    raise PermissionError(f"Action rejected: {result.checkpoint_reason}")
            else:
                raise PermissionError(f"Checkpoint required: {result.checkpoint_reason}")
        
        # Execute original tool
        return await original_run(*args, **kwargs)
    
    # Replace the run method
    if hasattr(tool, "_arun"):
        tool._arun = oversight_run
    else:
        tool._run = lambda *args, **kwargs: asyncio.run(oversight_run(*args, **kwargs))
    
    return tool


__all__ = [
    "OversightCallback",
    "OversightMiddleware",
    "wrap_tool_with_oversight",
]
