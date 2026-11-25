import json,time,os
from pathlib import Path
from redis import Redis
from .database import Session
from .models import Claim,Machine
from .model_service import score_claim
r=Redis.from_url(os.getenv('REDIS_URL','redis://redis:6379/0'),decode_responses=True)
while True:
    Path('/artifacts/worker-heartbeat').write_text(str(time.time()))
    item=r.blpop('claim-risk',timeout=2)
    if not item:continue
    cid=int(item[1])
    try:
        with Session.begin() as s:
            c=s.get(Claim,cid)
            if not c or c.status!='queued':continue
            m=s.get(Machine,c.machine_id)
            if c.hours_at_failure>m.warranty_hours:c.status='out_of_warranty';c.assessment_note='超出质保工时';continue
            c.risk,basis=score_claim(s,c,m);c.status='assessed';c.assessment_note=json.dumps(basis,ensure_ascii=False)
            Path(f'/artifacts/claim-{cid}-model.json').write_text(json.dumps(basis,ensure_ascii=False))
    except Exception as e:
        with Session.begin() as s:
            c=s.get(Claim,cid)
            if c:c.status='failed';c.assessment_note=str(e)
