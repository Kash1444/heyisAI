# app/agents/memory_agent.py

import json
import logging
import google.generativeai as genai
from google.generativeai import protos

from app.core.config import settings
from app.mcp.gmail_mcp_server import GMAIL_TOOLS, execute_tool

logger = logging.getLogger(__name__)

genai.configure(api_key=settings.gemini_api_key)


class MemoryAgent:
    """
    AI agent that uses Gmail tools to answer questions.

    Upgrade from RAG:
    - RAG: question → always vector search → generate
    - Agent: question → Gemini picks the right tool → execute → generate
    """

    def __init__(self):
        self.gemini_tools = self._build_gemini_tools()
        self.model = genai.GenerativeModel(
            model_name=settings.gemini_model,
            tools=self.gemini_tools,
        )

    def _build_gemini_tools(self):
        """
        Convert our MCP tool registry to Gemini function declarations.
        Uses plain dict format — works across all library versions.
        """
        from google.generativeai.types import FunctionDeclaration, Tool

        type_map = {
            "string": "string",
            "integer": "integer",
            "boolean": "boolean",
            "number": "number",
        }

        declarations = []

        for tool in GMAIL_TOOLS:
            properties = {}
            required_params = []

            for param_name, param_info in tool["parameters"].items():
                properties[param_name] = {
                    "type": type_map.get(param_info["type"], "string"),
                    "description": param_info.get("description", ""),
                }
                if "default" not in param_info:
                    required_params.append(param_name)

            parameters_schema = {
                "type": "object",
                "properties": properties,
            }

            if required_params:
                parameters_schema["required"] = required_params

            declaration = FunctionDeclaration(
                name=tool["name"],
                description=tool["description"],
                parameters=parameters_schema,
            )
            declarations.append(declaration)

        return [Tool(function_declarations=declarations)]

    def _extract_text(self, response) -> str:
        """
        Safely extract text from a Gemini response.

        Never call response.text directly — it crashes when
        the response contains non-text parts (function calls etc).
        This method safely collects only text parts.
        """
        text_parts = []

        try:
            for part in response.parts:
                if hasattr(part, 'text') and part.text:
                    text_parts.append(part.text)
        except Exception as e:
            logger.warning(f"[Agent] Text extraction warning: {e}")
            try:
                return response.candidates[0].content.parts[0].text
            except Exception:
                return "Unable to generate a response. Please try again."

        if text_parts:
            return "\n".join(text_parts)

        return "I found the information but had trouble formatting the response."

    def run(self, question: str) -> dict:
        """
        Run the agent: question → tool selection → execution → answer.
        """
        logger.info(f"[Agent] Running for: '{question}'")

        tools_used = []
        final_answer = ""

        try:
            chat = self.model.start_chat()

            system_context = (
                "You are a personal AI email assistant. "
                "You have access to the user's Gmail through tools. "
                "Always use the appropriate tool to find information "
                "before answering. Be specific about subjects, senders, "
                "and dates. If you need more information, ask one "
                "clear clarification question."
            )

            # Step 1: Send question to Gemini with tools available
            response = chat.send_message(
                f"{system_context}\n\nUser question: {question}"
            )

            # Step 2: Check if Gemini requested a tool call
            tool_result = None

            for part in response.parts:
                if hasattr(part, 'function_call') and part.function_call.name:
                    fn_call = part.function_call
                    tool_name = fn_call.name
                    tool_params = {k: v for k, v in fn_call.args.items()}

                    logger.info(
                        f"[Agent] Gemini requested tool: {tool_name} "
                        f"with params: {tool_params}"
                    )

                    # Step 3: Execute the tool
                    tool_result = execute_tool(tool_name, tool_params)
                    tools_used.append({
                        "tool": tool_name,
                        "params": tool_params,
                        "result_summary": str(
                            tool_result.get("count", "completed")
                        )
                    })

                    logger.info(
                        f"[Agent] Tool '{tool_name}' result: "
                        f"{tool_result.get('message', 'ok')}"
                    )

                    # Step 4: Send tool result back to Gemini
                    tool_response = chat.send_message(
                        protos.Content(
                            role="user",
                            parts=[protos.Part(
                                function_response=protos.FunctionResponse(
                                    name=tool_name,
                                    response={
                                        "result": json.dumps(
                                            tool_result, default=str
                                        )
                                    }
                                )
                            )]
                        )
                    )

                    # Step 5: Safely extract final answer
                    final_answer = self._extract_text(tool_response)
                    break

            else:
                # No tool call — Gemini answered directly
                final_answer = self._extract_text(response)
                logger.info("[Agent] Gemini answered directly")

            return {
                "answer": final_answer,
                "tools_used": tools_used,
                "tool_result": tool_result,
            }

        except Exception as e:
            logger.error(f"[Agent] Failed: {e}", exc_info=True)
            return {
                "answer": "I encountered an error. Please try again.",
                "tools_used": tools_used,
                "error": str(e),
            }


# Singleton
memory_agent = MemoryAgent()