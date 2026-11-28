from .catalog.architecture import kien_truc
from .catalog.fraud_case import ca_an_giang
from .catalog.investigation import agent_loop
from .catalog.lifecycle import vong_doi
from .catalog.realtime import realtime
from .catalog.queue import hang_doi
from .catalog.wallet import app_khach
from .catalog.simulation import mo_phong
from .catalog.infrastructure import ha_tang
from .backend_agent import backend_agent_pipeline
from .batch_ai import batch_ai_pipeline
from .realtime_ai import realtime_ai_pipeline

BUILDERS = (
    kien_truc,
    ca_an_giang,
    agent_loop,
    vong_doi,
    realtime,
    hang_doi,
    backend_agent_pipeline,
    batch_ai_pipeline,
    app_khach,
    mo_phong,
    ha_tang,
    realtime_ai_pipeline,
)
