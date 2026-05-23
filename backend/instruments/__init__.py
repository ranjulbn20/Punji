from .base import InstrumentHandler
from .mutual_fund import MutualFundHandler
from .stock import StockHandler
from .fixed_deposit import FixedDepositHandler
from .ppf import PPFHandler
from .nps import NPSHandler

_REGISTRY: dict[str, InstrumentHandler] = {
    "mutual_fund": MutualFundHandler(),
    "stock": StockHandler(),
    "fixed_deposit": FixedDepositHandler(),
    "ppf": PPFHandler(),
    "nps": NPSHandler(),
}


def get_handler(instrument_type: str) -> InstrumentHandler | None:
    return _REGISTRY.get(instrument_type)
