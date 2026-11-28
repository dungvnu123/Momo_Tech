from app.graph.ai_store import AIStore
from .records import application


def persist_cluster(database, applications, summary, decision):
    with AIStore(database) as store:
        with store.connection:
            for row in applications:
                application(store, row)
        store.persist_cluster(summary, decision)
