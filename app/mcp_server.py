import asyncio
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("legal-contract-reviewer-mcp")

# ─────────────────────────────────────────────────────────────────────────────
# TOOLS
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
async def lookup_legal_term(term: str) -> str:
    """Provides definitions for legal terms to ensure clarity during review."""
    dictionary = {
        "indemnification": "A contractual agreement where one party agrees to pay for potential losses or damages caused by another party.",
        "limitation of liability": "A clause that caps the amount a party has to pay in damages under a contract.",
        "governing law": "The jurisdiction whose laws will be used to interpret the contract.",
        "force majeure": "Unforeseeable circumstances that prevent someone from fulfilling a contract.",
        "arbitration": "A form of alternative dispute resolution outside of courts.",
    }
    return dictionary.get(term.lower(), f"Term '{term}' not found in internal legal dictionary.")

@mcp.tool()
async def fetch_policy_benchmark(clause_type: str) -> str:
    """Retrieves standard company policy benchmarks for specific clause types."""
    policies = {
        "liability": "Standard policy: Liability must be capped at 1x annual contract value. NO unlimited liability allowed.",
        "indemnity": "Standard policy: Mutual indemnification required for IP infringement. No broad general indemnity.",
        "payment_terms": "Standard policy: Net 30 days. High risk if > 45 days.",
        "data_privacy": "Standard policy: Must comply with GDPR and CCPA. Data must be encrypted at rest and in transit.",
    }
    return policies.get(clause_type.lower(), f"No specific policy benchmark found for '{clause_type}'. Default to conservative review.")

@mcp.tool()
async def log_audit_event(event_type: str, details: str) -> str:
    """Records complex audit metadata to a simulated persistent log."""
    # In a real app, this would write to a DB or cloud logging
    print(f"[AUDIT LOG] {event_type.upper()}: {details}")
    return f"Event '{event_type}' successfully recorded in audit log."

if __name__ == "__main__":
    mcp.run()
