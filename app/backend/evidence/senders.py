from app import db


def account_senders(context, kind, bank, account, limit, offset):
    query = "SELECT a.app_id,t.created_at,t.amount,t.transfer_id AS ordering FROM transfers t "
    query += "JOIN apps a ON a.phone=t.from_wallet WHERE t.to_id=? AND t.to_type=? "
    query += "AND (?::text='' OR UPPER(t.to_bank)=?) AND t.created_at<=? AND a.applied_at<=?"
    params = [account, kind, bank, bank, context.cutoff, context.cutoff]
    if db.has_table(context.store.db, "khach_transfers"):
        query += " UNION ALL SELECT a.app_id,t.ts AS created_at,t.amount::text,'KT'||t.tx_id::text AS ordering "
        query += (
            "FROM khach_transfers t JOIN apps a ON a.phone=t.phone WHERE t.to_id=? AND t.to_type=? "
        )
        query += "AND (?::text='' OR UPPER(t.to_bank)=?) AND t.ts<=? AND a.applied_at<=? AND t.status='done'"
        params += params[:]
    return context.store.q(
        "SELECT app_id,created_at,amount FROM ("
        + query
        + ") s ORDER BY created_at,ordering LIMIT ? OFFSET ?",
        *params,
        limit + 1,
        offset,
    )
