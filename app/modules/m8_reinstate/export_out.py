import io,csv,json

def bundle(case):
    # 结案下载与页面读取同一个 view(case)，数值口径一致；断缴凭证按登记原文输出
    out=io.StringIO(newline='');writer=csv.writer(out)
    writer.writerow(['记录类型','案件','项目','内容'])
    cid=case['case_id']
    writer.writerow(['断缴凭证',cid,'原文',json.dumps(case['certificate'],ensure_ascii=False,sort_keys=True)])
    writer.writerow(['断缴凭证',cid,'登记时间',case['created']])
    if case['ruling']:
        writer.writerow(['裁决',cid,'恢复基准',case['basis_label']])
        writer.writerow(['裁决',cid,'恢复期间',case['restore_period'][0]+' 至 '+case['restore_period'][1]])
        writer.writerow(['裁决',cid,'应补保费',case['premium_due']])
        writer.writerow(['裁决',cid,'赔款',case['claim_payable']])
        writer.writerow(['裁决',cid,'退还利息',case['interest_refund']])
        writer.writerow(['裁决',cid,'最终净额',case['net']])
        writer.writerow(['裁决',cid,'裁决时间',case['ruled_at']])
    writer.writerow(['状态',cid,'结案状态',case['status']])
    writer.writerow(['状态',cid,'结案时间',case['updated']])
    return '﻿'+out.getvalue()
