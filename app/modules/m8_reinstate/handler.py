import json
from flask import Blueprint,request,jsonify,Response
from app.web import api,page
from app.errors import DomainError
from app import store
from app.modules.m8_reinstate.rules import normalize_certificate,adjudicate,BASES
from app.modules.m8_reinstate.service import view
from app.modules.m8_reinstate.export_out import bundle

bp=Blueprint('m8_reinstate',__name__)

@bp.get('/m8_reinstate')
def screen():return page(8,'m8_reinstate.html')

@bp.route('/api/m8_reinstate',methods=['GET','POST'])
def preview():return api(8)

def _body():
    data=request.get_json(silent=True)
    if not isinstance(data,dict):raise DomainError('PAYLOAD','请求必须是对象')
    return data

def _version(data):
    if not isinstance(data.get('version'),int):raise DomainError('VERSION','请提交案件版本')
    return data['version']

@bp.post('/api/reinstate')
def create():
    return jsonify(view(store.create_case(normalize_certificate(_body()))))

@bp.get('/api/reinstate/<case_id>')
def detail(case_id):
    return jsonify(view(store.get_case(case_id)))

@bp.post('/api/reinstate/<case_id>/ruling')
def ruling(case_id):
    data=_body();basis=data.get('basis');version=_version(data)
    if basis not in BASES:raise DomainError('BASIS','恢复基准无效')
    cert=json.loads(store.get_case(case_id)['certificate'])
    return jsonify(view(store.put_ruling(case_id,adjudicate(cert,basis),version)))

@bp.post('/api/reinstate/<case_id>/close')
def close(case_id):
    return jsonify(view(store.close_case(case_id,_version(_body()))))

@bp.get('/api/reinstate/<case_id>/export.csv')
def export(case_id):
    case=view(store.get_case(case_id))
    if case['status']!='已结案':raise DomainError('UNSETTLED','案件未结案，不能下载结案凭证')
    return Response(bundle(case),mimetype='text/csv; charset=utf-8',headers={'Content-Disposition':'attachment; filename=reinstate.csv'})
