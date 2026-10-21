"""lookup_policy (vector search), calculate_monthly_repayment, and
check_account_balance (a mock account API) - the three tools the agent can
call. THIS FILE HAS NO OBSERVABILITY OF ANY KIND. That is the starting
point for the exercise: multi-tool calling already works correctly here -
the model correctly picks one or more of these three tools per question -
but which tool fired, how long it took, and whether it failed are all
completely invisible outside of whatever you can see by reading the
terminal running uvicorn. Step 3 of the outline is to give each of these
functions its own tool_call span."""
from vectorstore import build_or_load_collection, query as vs_query
from context import pack_context
from otel_setup import setup_tracing

tracer = setup_tracing(service_name="bfsi-assistant")

_collection = None

# A small, fixed set of mock accounts - good enough to demonstrate the tool
# without a real core-banking integration.
_MOCK_ACCOUNTS = {
    "ACC-10293": {"balance_gbp": 4210.55, "account_type": "Premier Current Account"},
    "ACC-55821": {"balance_gbp": 189.20, "account_type": "Standard Current Account"},
    "ACC-77410": {"balance_gbp": 32500.00, "account_type": "Premier Fixed Saver"},
}


def _get_collection():
    global _collection
    if _collection is None:
        _collection = build_or_load_collection()
    return _collection


def lookup_policy(query: str, n_results: int = 6) -> str:
    with tracer.start_as_current_span("tool_call") as span:
        span.set_attribute("gen_ai.tool.name", "lookup_policy")
        collection = _get_collection()
        hits = vs_query(collection, query, n_results=n_results)
        span.set_attribute("gen_ai.tool.lookup_policy.chunk_count", len(hits))
        return pack_context(hits)


def calculate_monthly_repayment(principal: float, annual_rate_pct: float, years: int) -> float:
    with tracer.start_as_current_span("tool_call") as span:
        span.set_attribute("gen_ai.tool.name", "calculate_monthly_repayment")
        monthly_rate = (annual_rate_pct / 100) / 12
        n_payments = years * 12
        if monthly_rate == 0:
            return round(principal / n_payments, 2)
        payment = principal * (monthly_rate * (1 + monthly_rate) ** n_payments) / \
            ((1 + monthly_rate) ** n_payments - 1)
        return round(payment, 2)


def check_account_balance(account_id: str) -> dict:
    """A mock account-balance lookup - the third tool, so a single question
    can plausibly need two or three different tools in one turn (e.g. 'what's
    my balance, and what would a GBP 5,000 top-up loan cost per month')."""
    with tracer.start_as_current_span("tool_call") as span:
        span.set_attribute("gen_ai.tool.name", "check_account_balance")
        account = _MOCK_ACCOUNTS.get(account_id.upper())
        if account is None:
            return {"found": False, "account_id": account_id}
        return {"found": True, "account_id": account_id.upper(), **account}


TOOL_SPECS = [
    {
        "type": "function",
        "function": {
            "name": "lookup_policy",
            "description": "Search Lloyds Financial policy/product documents for a relevant passage.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "What to search for"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_monthly_repayment",
            "description": "Calculate the monthly repayment for a loan/mortgage.",
            "parameters": {
                "type": "object",
                "properties": {
                    "principal": {"type": "number"},
                    "annual_rate_pct": {"type": "number"},
                    "years": {"type": "integer"},
                },
                "required": ["principal", "annual_rate_pct", "years"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_account_balance",
            "description": "Look up the current balance and account type for a given account ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "account_id": {"type": "string", "description": "e.g. ACC-10293"},
                },
                "required": ["account_id"],
            },
        },
    },
]

TOOL_FUNCTIONS = {
    "lookup_policy": lookup_policy,
    "calculate_monthly_repayment": calculate_monthly_repayment,
    "check_account_balance": check_account_balance,
}
