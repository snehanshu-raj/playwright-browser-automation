from prompt import SYSTEM_PROMPT_MANUAL
import os
import sys
import io
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import asyncio
from google import genai
from typing import Optional

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

def create_tool_descriptions(tools):
    """Create concise tool descriptions."""
    descriptions = []
    for tool in tools:
        schema = tool.inputSchema
        required = schema.get('required', [])
        props = schema.get('properties', {})
        
        req_params = [f"{p}" for p in required if p in props]
        params_str = ", ".join(req_params) if req_params else "none"
        
        descriptions.append(f"• {tool.name}({params_str})")
    
    return "\n".join(descriptions)

async def run_agent(query: str, max_iter: int = 15, verbose: bool = False, log_callback: Optional[callable] = None):
    def log(message: str, level: str = "info"):
        if verbose:
            print(message)
        if log_callback:
            log_callback(message, level)
    
    # Suppress stderr errors, this was mainly because MCP sever was sending some invalid messages not as per JSONRPC 2.0
    if not verbose:
        _old_stderr = sys.stderr
        sys.stderr = io.StringIO()
    
    try:
        log("Starting agent...")

        server_params = StdioServerParameters(
            command="npx",
            args=["-y", "@executeautomation/playwright-mcp-server"],
            env={**os.environ.copy(), "NODE_ENV": "production"}
        )

        stdio_ctx = None
        session_ctx = None
        
        try:
            if verbose:
                _old_stderr = sys.stderr
                sys.stderr = io.StringIO()
            
            stdio_ctx = stdio_client(server_params)
            read, write = await stdio_ctx.__aenter__()
            
            session_ctx = ClientSession(read, write)
            session = await session_ctx.__aenter__()
            await session.initialize()
            
            if verbose:
                sys.stderr = _old_stderr
            
            tools = (await session.list_tools()).tools
            log(f"{len(tools)} tools ready from MCP Server ready")
            
            tools_desc = create_tool_descriptions(tools)
            
            log(f"User's Goal: {query}")
            
            history = []
            execution_log = []
            
            for i in range(max_iter):
                log(f"\nIteration {i+1}/{max_iter}")
                
                if i == 0:
                    prompt = f"""{SYSTEM_PROMPT_MANUAL}
                                  GOAL: {query}
                                  Return the FIRST tool call.
                              """
                else:
                    recent_history = "\n".join(history[-3:])
                    prompt = f"""{SYSTEM_PROMPT_MANUAL}

                                COMPLETE_TOOLS_DESCRIPTION: {tools_desc}
                                GOAL: {query}

                                ACTIONS COMPLETED:
                                {recent_history}

                                IMPORTANT: Review the results above. If you successfully extracted the data you need (price, text, etc.), return FINAL_ANSWER immediately. Don't keep retrying if you already have valid data.

                                Return the NEXT tool call or FINAL_ANSWER."""
                
                try:
                    response = await client.aio.models.generate_content(
                        model="gemini-2.0-flash-lite",
                        contents=prompt,
                        config={"temperature": 0.1}
                    )
                    text = response.text.strip()
                    log(f"{text}")
                    
                    execution_log.append({
                        "iteration": i + 1,
                        "response": text
                    })
                    
                except Exception as e:
                    err_str = str(e)
                    if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                        log(f"Rate limit - waiting 10s...", "warning")
                        await asyncio.sleep(10)
                        continue
                    else:
                        log(f"{err_str[:100]}", "error")
                        break
                
                if "TOOL_CALL:" in text:
                    lines = text.split('\n')
                    tool_call_line = None
                    for line in lines:
                        if line.strip().startswith("TOOL_CALL:"):
                            tool_call_line = line.strip()
                            break
                    
                    if not tool_call_line:
                        log("No valid TOOL_CALL", "warning")
                        history.append(f"Invalid response format")
                        continue
                    
                    parts_raw = tool_call_line.replace("TOOL_CALL:", "").strip()
                    
                    if "|" in parts_raw:
                        first_pipe = parts_raw.index("|")
                        tool_name = parts_raw[:first_pipe].strip()
                        remaining = parts_raw[first_pipe+1:].strip()
                        
                        if tool_name == "playwright_evaluate":
                            params = [remaining]
                        else:
                            params = [p.strip() for p in remaining.split("|")]
                    else:
                        tool_name = parts_raw
                        params = []
                    
                    log(f"{tool_name} | {params}")
                    
                    tool = next((t for t in tools if t.name == tool_name), None)
                    if not tool:
                        log("Unknown tool", "error")
                        history.append(f"Tool '{tool_name}' not found")
                        continue
                    
                    try:
                        args = {}
                        schema_props = tool.inputSchema.get('properties', {})
                        
                        for idx, (param_name, param_info) in enumerate(schema_props.items()):
                            if idx < len(params):
                                val = params[idx]
                                ptype = param_info.get('type', 'string')
                                
                                if ptype == 'integer':
                                    args[param_name] = int(val)
                                elif ptype == 'number':
                                    args[param_name] = float(val)
                                elif ptype == 'boolean':
                                    args[param_name] = val.lower() in ['true', '1', 'yes']
                                else:
                                    args[param_name] = str(val)
                        
                        log(f"Executing: {args}")
                        result = await session.call_tool(tool_name, arguments=args)
                        
                        if hasattr(result, 'content'):
                            if isinstance(result.content, list):
                                rtext = "\n".join([str(getattr(x, 'text', x)) for x in result.content])
                            else:
                                rtext = str(result.content)
                        else:
                            rtext = str(result)
                        
                        display_text = rtext[:200] if len(rtext) > 200 else rtext
                        
                        if "failed" in rtext.lower() or "timeout" in rtext.lower() or "error" in rtext.lower():
                            log(f"!! {display_text}", "warning")
                            history.append(f"!! {tool_name} FAILED: {display_text[:80]}")
                            execution_log[-1]["status"] = "failed"
                            execution_log[-1]["result"] = display_text[:80]
                        else:
                            log(f"{display_text}")
                            if tool_name == "playwright_evaluate" and rtext and rtext.strip() not in ['null', 'undefined', '']:
                                history.append(f"{tool_name} returned: \"{rtext.strip()[:100]}\"")
                            else:
                                history.append(f"{tool_name} succeeded")
                            execution_log[-1]["status"] = "success"
                            execution_log[-1]["result"] = display_text[:200]
                        
                    except Exception as e:
                        log(f"{e}", "error")
                        history.append(f"{tool_name} error: {str(e)[:50]}")
                        execution_log[-1]["status"] = "error"
                        execution_log[-1]["error"] = str(e)[:100]
                
                elif "FINAL_ANSWER:" in text:
                    ans_line = None
                    for line in text.split('\n'):
                        if "FINAL_ANSWER:" in line:
                            ans_line = line
                            break
                    
                    if ans_line:
                        ans = ans_line.replace("FINAL_ANSWER:", "").strip()
                        log(f"DONE: {ans}")
                        
                        return {
                            "success": True,
                            "result": ans,
                            "iterations": i + 1,
                            "history": history,
                            "execution_log": execution_log
                        }
                else:
                    log("Invalid format", "warning")
                    history.append(f"Invalid response format")
            
            log("!! Max iterations reached", "warning")
            return {
                "success": False,
                "result": "Max iterations reached without completing task",
                "iterations": max_iter,
                "history": history,
                "execution_log": execution_log
            }
        
        finally:
            if not verbose:
                sys.stderr = io.StringIO()
            
            if session_ctx:
                try: await session_ctx.__aexit__(None, None, None)
                except: pass
            if stdio_ctx:
                try: await stdio_ctx.__aexit__(None, None, None)
                except: pass
            
            if not verbose:
                sys.stderr = _old_stderr
    
    finally:
        if not verbose:
            sys.stderr = _old_stderr

# for CLI
async def main():
    try:
        sys.stderr = sys.__stderr__
        query = input("Enter your goal: ").strip() or "Go to google.com and search for hello"
        result = await run_agent(query, verbose=True)
        print(f"Final Result: {result}")
    except Exception as e:
        sys.stderr = sys.__stderr__
        if "Shutdown" not in str(e):
            print(f"Error: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception:
        pass
