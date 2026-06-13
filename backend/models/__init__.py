from .user import User
from .risk_profile import RiskProfile
from .stock import Stock
from .mutual_fund import MutualFund
from .fixed_deposit import FixedDeposit
from .ppf import PPFAccount
from .nps import NPSAccount
from .transaction import Transaction
from .goal import Goal
from .alert import Alert
from .agent_memory import AgentMemory
from .portfolio_snapshot import PortfolioSnapshot
from .fund_composition import FundComposition
from .business_group import BusinessGroupMapping
from .import_job import ImportJob
from .conversation import Conversation, ConversationMessage

# Legacy — kept until migration drops the table
from .holding import Holding

__all__ = [
    "User", "RiskProfile",
    "Stock", "MutualFund", "FixedDeposit", "PPFAccount", "NPSAccount",
    "Transaction", "Goal", "Alert", "AgentMemory", "PortfolioSnapshot",
    "FundComposition", "BusinessGroupMapping", "ImportJob",
    "Conversation", "ConversationMessage",
    "Holding",  # legacy
]

# Convenience map: instrument_type string → model class
INSTRUMENT_MODEL_MAP = {
    "stock": Stock,
    "mutual_fund": MutualFund,
    "fixed_deposit": FixedDeposit,
    "ppf": PPFAccount,
    "nps": NPSAccount,
}
