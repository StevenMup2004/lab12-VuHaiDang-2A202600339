import os
import re
import json
import time
from typing import List, Dict, Any, Optional
from src.core.llm_provider import LLMProvider
from src.telemetry.logger import logger
from src.telemetry.metrics import tracker


class ReActAgent:
    """
    ReAct Agent: Implements the Thought -> Action -> Observation loop.
    
    v1: Basic ReAct with JSON action parsing.
    v2: Improved prompts, retry logic, guardrails.
    """
    
    def __init__(self, llm: LLMProvider, tools: List[Dict[str, Any]], max_steps: int = 10, version: str = "v1"):
        self.llm = llm
        self.tools = tools
        self.max_steps = max_steps
        self.version = version
        self.history = []
        self.step_logs = []

    def get_system_prompt(self) -> str:
        """
        System prompt that instructs the LLM to follow the ReAct pattern.
        v1: Basic instructions.
        v2: Enhanced with few-shot examples and guardrails.
        """
        tool_descriptions = "\n".join([
            f"  - {t['name']}: {t['description']}" for t in self.tools
        ])
        
        # Get today's date for context
        from datetime import datetime, timedelta
        today = datetime.now().strftime("%Y-%m-%d")
        next_saturday = (datetime.now() + timedelta(days=(5 - datetime.now().weekday()) % 7 or 7)).strftime("%Y-%m-%d")
        next_sunday = (datetime.now() + timedelta(days=(6 - datetime.now().weekday()) % 7 or 7)).strftime("%Y-%m-%d")

        base_prompt = f"""You are a Travel Planning Assistant.
You help users plan trips by checking weather, finding hotels, and suggesting activities.

Today's date is {today}. The upcoming weekend is {next_saturday} (Saturday) to {next_sunday} (Sunday).

You have access to these tools:
{tool_descriptions}

You MUST follow this EXACT format for EVERY step:

Thought: <your reasoning about what to do next>
Action: <JSON object with "tool" and "args" keys>
Observation: <result from the tool — this will be provided to you>

When you have gathered enough information to answer the user, respond with:
Thought: I now have all the information needed to provide a complete answer.
Final Answer: <your final response to the user>

RULES:
1. The Action MUST be a valid JSON object. Example:
   {{"tool": "check_weather", "args": {{"location": "Da Lat", "date": "{next_saturday}"}}}}

2. Only use tools listed above. Do NOT make up tool names.

3. Use the Observation from one tool to decide the next action (branching logic).

4. "this weekend" refers to {next_saturday} to {next_sunday}.

5. Budget conversion:
   - "500k" = 500000
   - "1 million" = 1000000
   - "200k" = 200000

6. ALWAYS output raw JSON for Action:
   - No markdown
   - No backticks
   - No extra text

7. After every Observation, ALWAYS start with a new Thought.

8. ALWAYS respond in the SAME language as the user's input.
   - English input → English output
   - Vietnamese input → Vietnamese output
"""

        if self.version == "v2":
            base_prompt += f"""
        === FEW-SHOT EXAMPLE ===

        User: I want to visit Da Lat this weekend. Check the weather for me.

        Thought: The user wants to visit Da Lat this weekend. I should check the weather first.
        Action: {{"tool": "check_weather", "args": {{"location": "Da Lat", "date": "{next_saturday}"}}}}
        Observation: Weather in Da Lat on {next_saturday}: Clear, Temperature: 22°C, Humidity: 65%, Wind: 3.2 m/s. No rain expected.

        Thought: The weather is clear with no rain. I can now provide the weather information.
        Final Answer: The weather in Da Lat this weekend ({next_saturday}) is clear with a temperature of 22°C and no rain expected. This is great for outdoor activities.

        === IMPORTANT GUARDRAILS ===

        - If a tool returns an error, DO NOT retry. Report the error.
        - Weather rules:
        - Rain / Drizzle / Thunderstorm → indoor activities
        - Clear / Clouds → outdoor activities
        - MAXIMUM {self.max_steps} steps.
        - If near max steps, provide best possible answer.
        """
        
        return base_prompt

    def run(self, user_input: str) -> str:
        """
        Execute the ReAct loop:
        1. Generate Thought + Action from LLM.
        2. Parse Action JSON and execute tool.
        3. Append Observation and continue.
        4. Return Final Answer when found.
        """
        start_time = time.time()
        logger.log_event("AGENT_START", {
            "input": user_input, 
            "model": self.llm.model_name,
            "version": self.version,
            "max_steps": self.max_steps
        })
        
        # Build the conversation history
        current_prompt = user_input
        conversation = ""
        steps = 0
        total_tokens = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

        while steps < self.max_steps:
            steps += 1
            step_start = time.time()
            
            # Build the full prompt with conversation history
            full_prompt = current_prompt
            if conversation:
                full_prompt = f"{current_prompt}\n\n{conversation}"
            
            # Generate LLM response
            try:
                result = self.llm.generate(
                    prompt=full_prompt,
                    system_prompt=self.get_system_prompt()
                )
            except Exception as e:
                logger.log_event("AGENT_ERROR", {
                    "step": steps, 
                    "error": f"LLM generation failed: {str(e)}"
                })
                return f"Error: LLM call failed — {str(e)}"
            
            llm_output = result["content"]
            usage = result.get("usage", {})
            latency = result.get("latency_ms", 0)
            
            # Track metrics
            total_tokens["prompt_tokens"] += usage.get("prompt_tokens", 0)
            total_tokens["completion_tokens"] += usage.get("completion_tokens", 0)
            total_tokens["total_tokens"] += usage.get("total_tokens", 0)
            
            tracker.track_request(
                provider=result.get("provider", "openai"),
                model=self.llm.model_name,
                usage=usage,
                latency_ms=latency
            )
            
            logger.log_event("AGENT_STEP", {
                "step": steps,
                "llm_output_preview": llm_output[:300],
                "tokens": usage,
                "latency_ms": latency
            })
            
            print(f"\n{'='*60}")
            print(f"📍 Step {steps}/{self.max_steps}")
            print(f"{'='*60}")
            print(llm_output)
            
            # Check for Final Answer
            final_answer = self._extract_final_answer(llm_output)
            if final_answer:
                total_time = int((time.time() - start_time) * 1000)
                logger.log_event("AGENT_END", {
                    "steps": steps,
                    "total_tokens": total_tokens,
                    "total_latency_ms": total_time,
                    "status": "success",
                    "version": self.version
                })
                print(f"\n✅ Agent completed in {steps} steps, {total_time}ms, {total_tokens['total_tokens']} tokens")
                return final_answer
            
            # Parse Action
            action = self._parse_action(llm_output)
            
            if action is None:
                # No action found — retry with hint (v2) or fail
                if self.version == "v2" and steps < self.max_steps:
                    conversation += f"\n{llm_output}\n\nSystem: You must provide an Action in JSON format or a Final Answer. Please try again."
                    logger.log_event("AGENT_PARSE_ERROR", {
                        "step": steps,
                        "error": "No valid Action or Final Answer found",
                        "raw_output": llm_output[:200]
                    })
                    continue
                else:
                    logger.log_event("AGENT_PARSE_ERROR", {
                        "step": steps,
                        "error": "No valid Action found",
                        "raw_output": llm_output[:200]
                    })
                    # Try to extract any useful content
                    return llm_output
            
            # Execute the tool
            tool_name = action.get("tool", "")
            tool_args = action.get("args", {})
            
            print(f"\n🔧 Executing: {tool_name}({tool_args})")
            
            observation = self._execute_tool(tool_name, tool_args)
            
            print(f"\n👁️ Observation:\n{observation}")
            
            logger.log_event("TOOL_CALL", {
                "step": steps,
                "tool": tool_name,
                "args": tool_args,
                "observation_preview": observation[:300],
                "status": "success"
            })
            
            # Append to conversation history
            # Include the thought and action from LLM output, then add observation
            conversation += f"\n{llm_output}\nObservation: {observation}\n"
        
        # Max steps reached
        total_time = int((time.time() - start_time) * 1000)
        logger.log_event("AGENT_END", {
            "steps": steps,
            "total_tokens": total_tokens,
            "total_latency_ms": total_time,
            "status": "max_steps_reached",
            "version": self.version
        })
        
        # Try to give a final answer based on what we have
        final_prompt = f"{current_prompt}\n\n{conversation}\n\nYou have reached the maximum number of steps. Please provide your Final Answer based on the information gathered so far."
        try:
            result = self.llm.generate(
                prompt=final_prompt,
                system_prompt=self.get_system_prompt()
            )
            return self._extract_final_answer(result["content"]) or result["content"]
        except Exception:
            return f"Agent reached maximum steps ({self.max_steps}) without completing. Partial conversation:\n{conversation}"

    def _parse_action(self, llm_output: str) -> Optional[Dict[str, Any]]:
        """
        Parse the Action from the LLM output.
        Expects format: Action: {"tool": "...", "args": {...}}
        Handles common issues: markdown backticks, extra whitespace, etc.
        """
        # Try to find Action line
        action_match = re.search(r'Action:\s*(.+?)(?:\n|$)', llm_output, re.DOTALL)
        
        if not action_match:
            return None
        
        action_str = action_match.group(1).strip()
        
        # Remove markdown backticks if present
        action_str = re.sub(r'^```(?:json)?\s*', '', action_str)
        action_str = re.sub(r'\s*```$', '', action_str)
        
        # Try to extract JSON object
        # First, try direct parse
        try:
            action = json.loads(action_str)
            if "tool" in action:
                return action
        except json.JSONDecodeError:
            pass
        
        # Try to find JSON in the string (may have trailing text)
        json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)?\}', action_str)
        if json_match:
            try:
                action = json.loads(json_match.group())
                if "tool" in action:
                    return action
            except json.JSONDecodeError:
                pass
        
        # Try multiline JSON (Action may span multiple lines)
        multiline_match = re.search(r'Action:\s*(\{.*?\})\s*(?:Observation|Thought|Final|$)', 
                                     llm_output, re.DOTALL)
        if multiline_match:
            try:
                action = json.loads(multiline_match.group(1))
                if "tool" in action:
                    return action
            except json.JSONDecodeError:
                pass
        
        # Legacy format: Action: tool_name(args)
        legacy_match = re.search(r'Action:\s*(\w+)\((.+?)\)', llm_output, re.DOTALL)
        if legacy_match:
            tool_name = legacy_match.group(1)
            args_str = legacy_match.group(2)
            # Try to parse args as key=value pairs
            args = {}
            for pair in args_str.split(","):
                pair = pair.strip()
                if "=" in pair:
                    key, value = pair.split("=", 1)
                    key = key.strip().strip('"').strip("'")
                    value = value.strip().strip('"').strip("'")
                    try:
                        value = float(value) if '.' in value else int(value)
                    except ValueError:
                        pass
                    args[key] = value
                else:
                    args["input"] = pair.strip('"').strip("'")
            return {"tool": tool_name, "args": args}
        
        logger.log_event("PARSE_FAILURE", {
            "raw_action": action_str[:200],
            "error": "Could not parse any valid action format"
        })
        return None

    def _extract_final_answer(self, llm_output: str) -> Optional[str]:
        """Extract the Final Answer from the LLM output."""
        match = re.search(r'Final Answer:\s*(.+)', llm_output, re.DOTALL)
        if match:
            answer = match.group(1).strip()
            # Remove any trailing "Thought:" or "Action:" that might be appended
            answer = re.split(r'\n\s*(?:Thought|Action):', answer)[0].strip()
            return answer
        return None

    def _execute_tool(self, tool_name: str, args: Dict[str, Any]) -> str:
        """
        Execute a tool by name with the given arguments.
        Returns the tool's output as a string.
        """
        for tool in self.tools:
            if tool['name'] == tool_name:
                func = tool.get('function')
                if func is None:
                    return f"Error: Tool '{tool_name}' has no callable function."
                try:
                    # Call the function with the provided args
                    result = func(**args)
                    return str(result)
                except TypeError as e:
                    logger.log_event("TOOL_ERROR", {
                        "tool": tool_name,
                        "args": str(args),
                        "error": f"Wrong arguments: {str(e)}"
                    })
                    return f"Error calling {tool_name}: Wrong arguments — {str(e)}. Check the tool description for correct parameter names and types."
                except Exception as e:
                    logger.log_event("TOOL_ERROR", {
                        "tool": tool_name,
                        "args": str(args),
                        "error": str(e)
                    })
                    return f"Error calling {tool_name}: {str(e)}"
        
        # Tool not found — hallucination
        available = ", ".join([t['name'] for t in self.tools])
        logger.log_event("TOOL_HALLUCINATION", {
            "attempted_tool": tool_name,
            "available_tools": available
        })
        return f"Error: Tool '{tool_name}' does not exist. Available tools: {available}"
