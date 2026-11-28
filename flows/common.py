from feature_flow import Flow
from feature_flow.model import Group

GROUP = "Thiên La"

__all__ = ["Flow", "Group", "GROUP", "color", "set_step"]


def color(f, nid, c):
    next((n for n in f.nodes if n.id == nid)).color = c


def set_step(f, nid, step):
    next((n for n in f.nodes if n.id == nid)).step = step
