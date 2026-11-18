import json
from app import store
from app.modules.m8_reinstate.rules import BASES

def view(row):
    # 页面与结案下载共用的唯一口径：恢复期间、应补保费、赔款、最终净额都从这里出
    cert=json.loads(row['certificate'])
    ruling=json.loads(row['ruling']) if row['ruling'] else None
    return {'case_id':row['id'],'policy_id':cert['policy_id'],'status':row['status'],
        'version':row['version'],'certificate':cert,'ruling':ruling,
        'basis_label':BASES.get(ruling['basis']) if ruling else None,
        'restore_period':[ruling['restore_from'],ruling['restore_end']] if ruling else None,
        'premium_due':ruling['premium_due'] if ruling else None,
        'claim_payable':ruling['claim_payable'] if ruling else None,
        'interest_refund':ruling['interest_refund'] if ruling else None,
        'net':ruling['net'] if ruling else None,
        'ruled_at':ruling.get('ruled_at') if ruling else None,
        'created':row['created'],'updated':row['updated']}

def execute(state):
    state['reinstate']={'cases':[view(r) for r in store.list_cases()]}
    return state
