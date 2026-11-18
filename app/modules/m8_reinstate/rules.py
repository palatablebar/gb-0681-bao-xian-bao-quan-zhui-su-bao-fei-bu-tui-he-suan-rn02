from datetime import date
from decimal import Decimal,ROUND_HALF_UP
from app.errors import DomainError
from app.modules.m2_mapping.coerce import day,number

BASES={'due':'按应缴日恢复','receipt':'按到账日恢复'}
CENT=Decimal('.01')
TEXT_FIELDS=('case_id','policy_id')
DATE_FIELDS=('due_date','grace_end','received_at','accident_at','period_end')
MONEY_FIELDS=('premium','claim_amount','interest_charged')

def _money(value,field):
    result=number(value).quantize(CENT,rounding=ROUND_HALF_UP)
    if result<0:raise DomainError('NUMBER',field+'不能为负')
    return str(result)

def normalize_certificate(raw):
    # 断缴凭证在登记时定形，之后任何接口不得改写
    if not isinstance(raw,dict):raise DomainError('PAYLOAD','请求必须是对象')
    cert={}
    for field in TEXT_FIELDS:
        value=str(raw.get(field,'')).strip()
        if not value:raise DomainError('MISSING','缺少'+field)
        cert[field]=value
    for field in DATE_FIELDS:
        value=raw.get(field)
        if value is None or str(value).strip()=='':raise DomainError('MISSING','缺少'+field)
        cert[field]=day(str(value))
    for field in MONEY_FIELDS:
        value=raw.get(field)
        if value is None or str(value).strip()=='':raise DomainError('MISSING','缺少'+field)
        cert[field]=_money(value,field)
    if Decimal(cert['premium'])<=0:raise DomainError('NUMBER','欠缴保费必须为正')
    due=date.fromisoformat(cert['due_date']);grace=date.fromisoformat(cert['grace_end'])
    received=date.fromisoformat(cert['received_at']);accident=date.fromisoformat(cert['accident_at'])
    end=date.fromisoformat(cert['period_end'])
    if not due<received:raise DomainError('RANGE','到账日须晚于应缴日')
    if not due<grace:raise DomainError('RANGE','宽限期末须晚于应缴日')
    if received>grace:raise DomainError('GRACE','补缴超出宽限期，不能按宽限期复效')
    if not due<=accident<received:raise DomainError('RANGE','报案事故须落在断缴窗口内（应缴日含至到账日不含）')
    if not received<end:raise DomainError('RANGE','保障期间末须晚于到账日')
    return cert

def adjudicate(cert,basis):
    # 同一凭证+同一基准=>同一裁决；赔款与补费由裁决唯一派生，重试不会新增
    if basis not in BASES:raise DomainError('BASIS','恢复基准无效')
    due=date.fromisoformat(cert['due_date']);received=date.fromisoformat(cert['received_at'])
    accident=date.fromisoformat(cert['accident_at']);end=date.fromisoformat(cert['period_end'])
    premium=Decimal(cert['premium']);claim=Decimal(cert['claim_amount'])
    total_days=Decimal((end-due).days)
    if basis=='due':
        start=due;premium_due=premium
    else:
        start=received
        premium_due=(premium*Decimal((end-received).days)/total_days).quantize(CENT,rounding=ROUND_HALF_UP)
    claim_payable=claim if start<=accident<end else Decimal(0)
    interest_refund=Decimal(cert['interest_charged']) if basis=='due' else Decimal(0)
    net=premium_due-claim_payable-interest_refund
    def q(v):return str(v.quantize(CENT,rounding=ROUND_HALF_UP))
    return {'basis':basis,'restore_from':start.isoformat(),'restore_end':end.isoformat(),
        'premium_due':q(premium_due),'claim_payable':q(claim_payable),
        'interest_refund':q(interest_refund),'net':q(net)}
