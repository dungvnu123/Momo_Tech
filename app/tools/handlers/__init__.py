from .applications import get_application
from .relations import neighbors
from .money import money_flow, account_senders
from .evidence import get_evidence
from .reports import reports_mentioning
from .entities import entity_info
from .clusters import get_cluster, tech_profile
from .timeline import timeline
from .cluster_money import cluster_money_flow

HANDLERS = {
    "cluster_money_flow": cluster_money_flow,
    "get_application": get_application,
    "neighbors": neighbors,
    "money_flow": money_flow,
    "account_senders": account_senders,
    "get_evidence": get_evidence,
    "reports_mentioning": reports_mentioning,
    "entity_info": entity_info,
    "get_cluster": get_cluster,
    "tech_profile": tech_profile,
    "timeline": timeline,
}
