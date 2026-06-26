import os
from google.adk import workflow
from google.adk.agents import LlmAgent, MCPToolset
from google.adk.apps import App
from app.config import config

# ─────────────────────────────────────────────────────────────────────────────
# STATE DEFINITION
# ─────────────────────────────────────────────────────────────────────────────

class ContractState(workflow.State):
    contract_text: str = ""
    risks: list[str] = []
    suggestions: list[str] = []
    security_verified: bool = False
    audit_log: list[dict] = []

# ─────────────────────────────────────────────────────────────────────────────
# MCP CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────

legal_mcp = MCPToolset(
    name="legal_tools",
    # Using 'uv run' ensures the server has its dependencies
    command="uv",
    args=["run", "python", "-m", "app.mcp_server"],
)

# ─────────────────────────────────────────────────────────────────────────────
# SPECIALIZED SUB-AGENTS
# ─────────────────────────────────────────────────────────────────────────────

risk_analyzer = LlmAgent(
    name="risk_analyzer",
    model=config.model,
    tools=[legal_mcp],
    instruction="""You are a senior legal counsel specializing in risk assessment. 
    Analyze the provided contract text for high-risk clauses such as:
    - Unlimited liability
    - Broad indemnification
    - Unfavorable governing law
    - Automatic renewals without notice
    
    Use 'fetch_policy_benchmark' to check if a clause violates company policy.
    Use 'lookup_legal_term' if you encounter complex terminology.
    
    Return a bulleted list of identified risks and their severity."""
)

clause_rewriter = LlmAgent(
    name="clause_rewriter",
    model=config.model,
    tools=[legal_mcp],
    instruction="""You are a legal drafting expert. 
    For each risky clause identified, provide a standard, balanced, and 'safer' 
    alternative version that protects the user's interests while remaining fair.
    
    Use 'fetch_policy_benchmark' to ensure your suggestions meet company standards.
    Log your major recommendations using 'log_audit_event'."""
)

# ─────────────────────────────────────────────────────────────────────────────
# WORKFLOW NODES
# ─────────────────────────────────────────────────────────────────────────────

@workflow.node
async def security_checkpoint(ctx: workflow.Context[ContractState]) -> str:
    """Security node to prevent prompt injection and scrub PII."""
    import re
    import json

    input_text = ctx.state.contract_text
    security_events = []

    # 1. Prompt Injection Detection
    injection_patterns = [
        r"ignore previous instructions",
        r"disregard all earlier prompts",
        r"you are now a",
        r"system override",
    ]
    for pattern in injection_patterns:
        if re.search(pattern, input_text, re.IGNORECASE):
            security_events.append(f"Prompt Injection Attempt Detected: {pattern}")

    # 2. PII Scrubbing (Regex)
    # Scrubbing emails and phone numbers for privacy
    email_pattern = r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"
    phone_pattern = r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}"
    
    if re.search(email_pattern, input_text):
        security_events.append("PII Detected: Emails found in contract.")
    if re.search(phone_pattern, input_text):
        security_events.append("PII Detected: Phone numbers found in contract.")

    # 3. Domain Rule: Basic sanity check
    if len(input_text) < 50:
        security_events.append("Input too short to be a valid contract.")
    if "agreement" not in input_text.lower() and "contract" not in input_text.lower():
        security_events.append("Input does not appear to be a legal agreement.")

    # 4. Audit Log & Routing
    log_entry = {
        "node": "security_checkpoint",
        "timestamp": str(os.getenv("CURRENT_TIME", "recent")),
        "events": security_events,
        "status": "BLOCK" if any("Injection" in e for e in security_events) else "PASS"
    }
    ctx.state.audit_log.append(log_entry)

    if log_entry["status"] == "BLOCK":
        return "final_report" # Jump to end or error node
    
    ctx.state.security_verified = True
    return "analyze_risks"

@workflow.node
async def analyze_risks(ctx: workflow.Context[ContractState]) -> str:
    """Analyzes the contract for legal risks."""
    response = await risk_analyzer.generate(ctx.state.contract_text)
    ctx.state.risks = [response.text]
    ctx.state.audit_log.append({"event": "risk_analysis", "agent": "risk_analyzer"})
    return "rewrite_clauses"

@workflow.node
async def rewrite_clauses(ctx: workflow.Context[ContractState]) -> str:
    """Suggests alternative wording for identified risks."""
    risk_context = "\n".join(ctx.state.risks)
    response = await clause_rewriter.generate(f"Risks found:\n{risk_context}")
    ctx.state.suggestions = [response.text]
    ctx.state.audit_log.append({"event": "clause_rewriting", "agent": "clause_rewriter"})
    return "final_report"

@workflow.node
async def final_report(ctx: workflow.Context[ContractState]):
    """Synthesizes the final output for the user."""
    summary = "# Legal Review Report\n\n"
    
    # Check for security events
    security_entries = [e for e in ctx.state.audit_log if e.get("node") == "security_checkpoint"]
    if security_entries:
        events = security_entries[0].get("events", [])
        if events:
            summary += "## ⚠️ Security Alerts\n"
            for event in events:
                summary += f"- {event}\n"
            if security_entries[0].get("status") == "BLOCK":
                summary += "\n**CRITICAL: Process stopped due to security violations.**\n"
                return summary

    summary += "## Risks Identified\n"
    summary += "\n".join(ctx.state.risks) if ctx.state.risks else "No major risks identified."
    
    summary += "\n\n## Suggested Alternatives\n"
    summary += "\n".join(ctx.state.suggestions) if ctx.state.suggestions else "No changes suggested."
    
    return summary

# ─────────────────────────────────────────────────────────────────────────────
# GRAPH ORCHESTRATION
# ─────────────────────────────────────────────────────────────────────────────

review_workflow = workflow.Workflow(
    name="legal_contract_review_flow",
    state_type=ContractState,
)

# Edges
review_workflow.add_edge(workflow.START, security_checkpoint)
review_workflow.add_edge(security_checkpoint, analyze_risks)
review_workflow.add_edge(analyze_risks, rewrite_clauses)
review_workflow.add_edge(rewrite_clauses, final_report)
review_workflow.add_edge(final_report, workflow.END)

# root_agent for ADK 2.0 compatibility
root_agent = review_workflow.as_agent()

app = App(
    root_agent=root_agent,
    name="legal-contract-reviewer"
)
