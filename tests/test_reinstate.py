CERT={'case_id':'R001','policy_id':'P900','due_date':'2026-03-01','grace_end':'2026-04-30',
    'received_at':'2026-04-30','accident_at':'2026-04-10','claim_amount':'20000',
    'premium':'3650','period_end':'2027-03-01','interest_charged':'45.50'}

def create(client,cert=None):return client.post('/api/reinstate',json=cert or CERT)
def rule(client,basis,version):return client.post('/api/reinstate/R001/ruling',json={'basis':basis,'version':version})

def test_rule_by_due_date_pays_claim_and_refunds_interest(client):
    create(client)
    d=rule(client,'due',0).get_json()
    assert d['status']=='已裁决' and d['version']==1
    assert d['restore_period']==['2026-03-01','2027-03-01']
    assert d['premium_due']=='3650.00'
    assert d['claim_payable']=='20000.00'
    assert d['interest_refund']=='45.50'
    assert d['net']=='-16395.50'

def test_rule_by_receipt_date_denies_claim(client):
    create(client)
    d=rule(client,'receipt',0).get_json()
    assert d['restore_period']==['2026-04-30','2027-03-01']
    assert d['premium_due']=='3050.00'
    assert d['claim_payable']=='0.00'
    assert d['interest_refund']=='0.00'
    assert d['net']=='3050.00'

def test_certificate_cannot_be_rewritten(client):
    create(client)
    r=create(client,dict(CERT,premium='9999'))
    assert r.status_code==409 and r.get_json()['code']=='CONFLICT'
    assert client.get('/api/reinstate/R001').get_json()['certificate']['premium']=='3650.00'

def test_create_retry_is_idempotent(client):
    a=create(client).get_json();b=create(client).get_json()
    assert a['version']==b['version']==0 and a['created']==b['created'] and a['status']=='待裁决'

def test_same_ruling_retry_adds_nothing(client):
    create(client)
    a=rule(client,'due',0).get_json()
    b=rule(client,'due',0).get_json()
    assert b['version']==1 and b['ruling']==a['ruling']

def test_replace_requires_current_version(client):
    create(client);rule(client,'due',0)
    r=rule(client,'receipt',0)
    assert r.status_code==409 and r.get_json()['code']=='STALE'
    d=client.get('/api/reinstate/R001').get_json()
    assert d['ruling']['basis']=='due' and d['version']==1
    ok=rule(client,'receipt',1)
    assert ok.status_code==200 and ok.get_json()['version']==2

def test_failed_replace_keeps_old_ruling(client):
    create(client);rule(client,'due',0)
    r=client.post('/api/reinstate/R001/ruling',json={'basis':'bogus','version':1})
    assert r.status_code==422 and r.get_json()['code']=='BASIS'
    d=client.get('/api/reinstate/R001').get_json()
    assert d['ruling']['basis']=='due' and d['net']=='-16395.50'

def test_close_requires_ruling_first(client):
    create(client)
    r=client.post('/api/reinstate/R001/close',json={'version':0})
    assert r.status_code==422 and r.get_json()['code']=='PENDING'

def test_close_locks_case(client):
    create(client);rule(client,'due',0)
    assert client.post('/api/reinstate/R001/close',json={'version':1}).get_json()['status']=='已结案'
    r=rule(client,'receipt',2)
    assert r.status_code==422 and r.get_json()['code']=='CLOSED'

def test_close_retry_safe(client):
    create(client);rule(client,'due',0)
    a=client.post('/api/reinstate/R001/close',json={'version':1}).get_json()
    b=client.post('/api/reinstate/R001/close',json={'version':1}).get_json()
    assert a['status']==b['status']=='已结案' and a['version']==b['version']

def test_export_requires_closed(client):
    create(client);rule(client,'due',0)
    assert client.get('/api/reinstate/R001/export.csv').status_code==422

def test_page_and_export_share_figures(client):
    create(client);rule(client,'due',0)
    client.post('/api/reinstate/R001/close',json={'version':1})
    page=client.get('/m8_reinstate').data.decode()
    text=client.get('/api/reinstate/R001/export.csv').data.decode('utf-8-sig')
    for figure in ('3650.00','20000.00','45.50','-16395.50','2026-03-01','2027-03-01'):
        assert figure in page and figure in text
    assert '断缴凭证' in text and '按应缴日恢复' in text

def test_grace_exceeded_rejected(client):
    r=create(client,dict(CERT,received_at='2026-05-01'))
    assert r.status_code==422 and r.get_json()['code']=='GRACE'

def test_accident_must_precede_payment(client):
    r=create(client,dict(CERT,accident_at='2026-05-01'))
    assert r.status_code==422 and r.get_json()['code']=='RANGE'

def test_missing_field_rejected(client):
    bad={k:v for k,v in CERT.items() if k!='premium'}
    r=create(client,bad)
    assert r.status_code==422 and r.get_json()['code']=='MISSING'

def test_unknown_case_404(client):
    assert client.get('/api/reinstate/none').status_code==404
