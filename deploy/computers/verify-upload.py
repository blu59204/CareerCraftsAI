import base64, json, os, uuid, httpx
client=httpx.Client(base_url='http://127.0.0.1:4302',timeout=75,headers={'Authorization':'Bearer '+os.environ['SANDBOX_RELAY_TOKEN']})
u=str(uuid.uuid4())
def act(op,params=None,snap=None,actor='agent',expected=200):
    body={'operation':op,'parameters':params or {},'actor':actor}
    if snap: body.update(computer_run=snap['computer_run'],approved_snapshot=snap['snapshotId'])
    r=client.post(f'/users/{u}/action',json=body)
    assert r.status_code==expected,(op,r.status_code,r.text[:300])
    return r.json()
try:
    client.post(f'/users/{u}/start').raise_for_status()
    act('navigate',{'url':'http://test-portal/'},actor='human')
    snap=act('snapshot')
    print('FIELDS',[(e['ref'],e['role'],e['name']) for e in snap['elements']])
    ref=next(e['ref'] for e in snap['elements'] if e['name']=='Resume')
    params={'ref':ref,'snapshotId':snap['snapshotId'],'filename':'fixture.txt','mimeType':'text/plain','base64':base64.b64encode(b'Synthetic Python developer resume').decode()}
    act('upload',params,{**snap,'computer_run':'stale'},expected=409)
    act('upload',params,snap)
    assert 'fixture.txt' in json.dumps(act('read'))
    act('upload',params,snap,expected=409)
    print('PASS: upload filename visible; stale run and snapshot rejected')
finally:
    client.post(f'/users/{u}/stop').raise_for_status()
