from .handlers.reports import analysis_view, reports_mentioning
from .handlers.entities import decision_view, entity_info
from .handlers.money import account_senders
from .handlers.clusters import get_cluster, tech_profile
from .handlers.timeline import timeline

AI_HANDLERS = {"get_cluster": get_cluster, "account_senders": account_senders,
               "reports_mentioning": reports_mentioning, "timeline": timeline,
               "tech_profile": tech_profile, "entity_info": entity_info}
