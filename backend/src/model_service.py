import json,os,pickle
from datetime import datetime,timezone
from fastapi import HTTPException
from sqlalchemy import select
from .models import Claim,Machine
from .model_models import ModelVersion,ClaimTriage
from .claim_service import audit
from . import risk_model
ARTIFACTS=os.getenv('ARTIFACTS_DIR','/artifacts')
def now():return datetime.now(timezone.utc).isoformat()
def view(v):
    return {'id':v.id,'name':v.name,'state':v.state,'algorithm':v.algorithm,'seed':v.seed,'metrics':json.loads(v.metrics),'samples':json.loads(v.samples),'encoder':json.loads(v.encoder),'trained_by':v.trained_by,'trained_at':v.trained_at,'reviewed_by':v.reviewed_by,'reviewed_at':v.reviewed_at,'review_note':v.review_note,'activated_by':v.activated_by,'activated_at':v.activated_at}
def active_version(s):return s.scalar(select(ModelVersion).where(ModelVersion.state=='active'))
def train_candidate(s,u):
    history=s.scalars(select(Claim).where(Claim.historical==True,Claim.disputed.isnot(None))).all()
    rows=[]
    for c in history:
        m=s.get(Machine,c.machine_id)
        rows.append({'code':c.code,'machine_id':c.machine_id,'serial':m.serial if m else str(c.machine_id),'x':[m.model if m else '',c.part,c.hours_at_failure,c.age_days,int(c.leak_flag)],'y':int(c.disputed)})
    try:model,metrics,manifest,encoder=risk_model.train(rows)
    except risk_model.TrainingRejected as e:raise HTTPException(409,str(e))
    v=ModelVersion(state='candidate',algorithm='OneHotEncoder + StandardScaler + LogisticRegression',seed=risk_model.SEED,metrics=json.dumps(metrics,ensure_ascii=False),samples=json.dumps(manifest,ensure_ascii=False),encoder=json.dumps(encoder,ensure_ascii=False),trained_by=u['email'],trained_at=now())
    s.add(v);s.flush()
    v.name=f'MV-{v.id:04d}'
    os.makedirs(ARTIFACTS,exist_ok=True)
    path=os.path.join(ARTIFACTS,f'model-{v.name}.pkl')
    with open(path,'wb') as f:pickle.dump(model,f)
    v.artifact=path
    audit(s,u,'model_trained',f'{v.name}：训练{metrics["training_rows"]}条/留出{metrics["holdout_rows"]}条，留出ROC AUC {metrics["roc_auc"]}')
    return v
def review(s,vid,note,u):
    v=s.get(ModelVersion,vid,with_for_update=True)
    if not v:raise HTTPException(404,'模型版本不存在')
    if v.state!='candidate':raise HTTPException(409,'版本状态已变化，请刷新后重试')
    v.state='reviewed';v.reviewed_by=u['email'];v.reviewed_at=now();v.review_note=note
    audit(s,u,'model_reviewed',f'{v.name}：{note}')
    return v
def switch(s,vid,expected_current_id,u,kind):
    versions=s.scalars(select(ModelVersion).order_by(ModelVersion.id).with_for_update()).all()
    current=next((x for x in versions if x.state=='active'),None)
    if (current.id if current else None)!=expected_current_id:raise HTTPException(409,f'当前在用版本已变为{current.name if current else "无"}，请刷新后基于最新版本操作')
    target=next((x for x in versions if x.id==vid),None)
    if not target:raise HTTPException(404,'模型版本不存在')
    if target.state!='reviewed':raise HTTPException(409,'仅已审核版本可启用或回退')
    if kind=='activate' and target.activated_at:raise HTTPException(409,'该版本曾启用过，如需恢复请使用回退')
    if kind=='rollback' and not target.activated_at:raise HTTPException(409,'该版本未曾启用，不能回退，请使用启用')
    try:
        with open(target.artifact,'rb') as f:pickle.load(f)
    except Exception:raise HTTPException(409,'模型构件缺失或损坏，切换已取消，保留在用旧版')
    if current:current.state='reviewed'
    target.state='active';target.activated_at=now();target.activated_by=u['email']
    audit(s,u,'model_activated' if kind=='activate' else 'model_rollback',f'{current.name if current else "无"} → {target.name}')
    return target
def bind(s,c,v):
    b=s.scalar(select(ClaimTriage).where(ClaimTriage.claim_id==c.id))
    if b:b.version_id=v.id;b.version_name=v.name;b.bound_at=now()
    else:s.add(ClaimTriage(claim_id=c.id,version_id=v.id,version_name=v.name,bound_at=now()))
_cache={}
def score_claim(s,c,m):
    b=s.scalar(select(ClaimTriage).where(ClaimTriage.claim_id==c.id))
    if not b:raise ValueError('索赔未绑定模型版本，无法分流')
    v=s.get(ModelVersion,b.version_id)
    if not v:raise ValueError('索赔绑定的模型版本不存在')
    model=_cache.get(v.id)
    if model is None:
        with open(v.artifact,'rb') as f:model=pickle.load(f)
        _cache[v.id]=model
    risk=risk_model.predict(model,[m.model,c.part,c.hours_at_failure,c.age_days,int(c.leak_flag)])
    mt=json.loads(v.metrics)
    basis={'version':v.name,'version_id':v.id,'probability':round(risk,4),'high_risk_threshold':mt['high_risk_threshold'],'seed':mt['seed'],'method':mt['method'],'split':mt['split'],'training_rows':mt['training_rows'],'holdout_rows':mt['holdout_rows'],'accuracy':mt['accuracy'],'roc_auc':mt['roc_auc'],'trained_at':v.trained_at,'bound_at':b.bound_at}
    return risk,basis
