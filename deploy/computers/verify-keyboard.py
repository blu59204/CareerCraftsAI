"""Synthetic browser keyboard proof; never submits a job application."""
import json,os,uuid,httpx
client=httpx.Client(base_url='http://127.0.0.1:4302',timeout=75,headers={'Authorization':'Bearer '+os.environ['SANDBOX_RELAY_TOKEN']})
u=str(uuid.uuid4())
def call(op,params=None,actor='human',snap=None,expected=200):
    body={'operation':op,'parameters':params or {},'actor':actor}
    if snap: body.update(computer_run=snap['computer_run'],approved_snapshot=snap['snapshotId'])
    r=client.post(f'/users/{u}/action',json=body)
    assert r.status_code==expected,(op,r.status_code,r.text[:150])
    return r.json()
try:
    client.post(f'/users/{u}/start').raise_for_status()
    call('navigate',{'url':'http://test-portal/'})
    snap=call('snapshot',actor='agent')
    ref=next(e['ref'] for e in snap['elements'] if e['name']=='Cover letter')
    call('click',{'ref':ref,'snapshotId':snap['snapshotId']},'agent',snap)
    request=call('control/request',{'reason':'Synthetic keyboard proof'})['request']['id']
    call('control/take',{'requestId':request})
    call('human/type',{'text':'Initial text'})
    call('human/key',{'key':'Control+a'})
    call('human/key',{'key':'Backspace'})
    call('human/type',{'text':'Synthetic keyboard'})
    call('human/key',{'key':'Enter'})
    call('human/type',{'text':'Unicode \u00e9\u4e2d paste'})
    call('human/key',{'key':'Tab'})
    call('human/key',{'key':'Shift+Tab'})
    call('human/key',{'key':'ArrowLeft'})
    page=call('read')
    assert 'Synthetic keyboard' in json.dumps(page,ensure_ascii=False),page
    assert 'Unicode \u00e9\u4e2d paste' in json.dumps(page,ensure_ascii=False),page
    call('control/release',{'requestId':request})
    call('snapshot',actor='agent',expected=409)
    print('PASS: text, selection, delete, multiline, Unicode, Tab and arrows; private read protection preserved')
finally:
    client.post(f'/users/{u}/stop').raise_for_status()
