import os
import sys
import importlib.util
from typing import List, Dict, Any, Optional
from mcp.server.fastmcp import FastMCP

# Define the base directory for skills
SKILLS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "skills")
os.makedirs(SKILLS_DIR, exist_ok=True)

mcp = FastMCP("SkillManager")

@mcp.tool()
def create_skill(name: str, code: str, description: str) -> str:
    """
    Creates a new persistent skill (Python function) for the agent.
    The code should be a complete Python file with a function named 'run'.
    """
    file_path = os.path.join(SKILLS_DIR, f"{name}.py")
    try:
        with open(file_path, "w") as f:
            f.write(code)
        return f"Successfully created skill '{name}' in {file_path}. It is now available for use."
    except Exception as e:
        return f"Error creating skill: {e}"

@mcp.tool()
def list_skills() -> str:
    """Lists all available agent-generated skills."""
    skills = [f[:-3] for f in os.listdir(SKILLS_DIR) if f.endswith(".py")]
    if not skills:
        return "No skills found."
    return "Available skills: " + ", ".join(skills)

@mcp.tool()
def run_skill(name: str, arguments: Dict[str, Any]) -> str:
    """
    Executes a previously created skill.
    'arguments' should be a dictionary of keyword arguments for the skill's 'run' function.
    """
    file_path = os.path.join(SKILLS_DIR, f"{name}.py")
    if not os.path.exists(file_path):
        return f"Skill '{name}' not found."

    try:
        spec = importlib.util.spec_from_file_location(name, file_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        if not hasattr(module, "run"):
            return f"Error: Skill '{name}' does not have a 'run' function."
        
        result = module.run(**arguments)
        return f"Skill '{name}' result: {result}"
    except Exception as e:
        return f"Error executing skill '{name}': {e}"

if __name__ == "__main__":
    mcp.run()
