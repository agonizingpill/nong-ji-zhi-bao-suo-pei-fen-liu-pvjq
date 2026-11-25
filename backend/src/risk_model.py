from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder,StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.metrics import accuracy_score,roc_auc_score
import numpy as np
SEED=42
MIN_ROWS=40
class TrainingRejected(Exception):pass
def train(rows):
    # rows: {'code','machine_id','serial','x':[机型,部位,工时,机龄,渗漏],'y':0/1}
    if len(rows)<MIN_ROWS:raise TrainingRejected(f'已结案历史不足{MIN_ROWS}条（当前{len(rows)}条），不能训练分流模型；在用版本保持不变')
    serials={}
    for r in rows:serials.setdefault(r['machine_id'],r['serial'])
    if len(serials)<2:raise TrainingRejected('已结案历史仅涉及 1 台机具，无法按机具隔离训练集与留出集；在用版本保持不变')
    groups=np.array([r['machine_id'] for r in rows])
    y=np.array([r['y'] for r in rows])
    if len(set(y.tolist()))<2:raise TrainingRejected('已结案历史的争议类别单一，缺少对照类别样本，不能训练分流模型；在用版本保持不变')
    X=np.array([r['x'] for r in rows],dtype=object)
    n_splits=min(4,len(serials))
    try:folds=StratifiedGroupKFold(n_splits=n_splits,shuffle=True,random_state=SEED).split(X,y,groups)
    except ValueError as e:raise TrainingRejected(f'按机具隔离划分失败（{e}）；在用版本保持不变')
    a=b=None
    for ta,tb in folds:
        if set(groups[ta].tolist())&set(groups[tb].tolist()):continue
        if len(set(y[ta].tolist()))<2 or len(set(y[tb].tolist()))<2:continue
        a,b=ta,tb;break
    if a is None:raise TrainingRejected('按机具隔离后训练集或留出集争议类别单一，无法训练或评估 ROC AUC；请补充历史索赔，在用版本保持不变')
    pre=ColumnTransformer([('category',OneHotEncoder(handle_unknown='ignore'),[0,1]),('numeric',StandardScaler(),[2,3,4])])
    model=make_pipeline(pre,LogisticRegression(max_iter=1000,random_state=SEED))
    model.fit(X[a],y[a]);p=model.predict_proba(X[b])[:,1]
    metrics={'training_rows':int(len(a)),'holdout_rows':int(len(b)),'accuracy':round(float(accuracy_score(y[b],p>=.5)),4),'roc_auc':round(float(roc_auc_score(y[b],p)),4),'seed':SEED,'high_risk_threshold':.5,'method':'OneHotEncoder + StandardScaler + LogisticRegression','split':f'按机具隔离（StratifiedGroupKFold n_splits={n_splits}，同一机具仅属一侧）','train_disputed':int(y[a].sum()),'train_clear':int(len(a)-y[a].sum()),'holdout_disputed':int(y[b].sum()),'holdout_clear':int(len(b)-y[b].sum()),'coefficients':{str(k):round(float(v),4) for k,v in zip(model[0].get_feature_names_out(),model[1].coef_[0])}}
    manifest={'train_samples':sorted(rows[i]['code'] for i in a),'holdout_samples':sorted(rows[i]['code'] for i in b),'train_machines':sorted(serials[g] for g in set(groups[a].tolist())),'holdout_machines':sorted(serials[g] for g in set(groups[b].tolist()))}
    cats=model[0].named_transformers_['category'].categories_
    encoder={'机型':[str(x) for x in cats[0]],'故障部位':[str(x) for x in cats[1]],'feature_names':[str(x) for x in model[0].get_feature_names_out()]}
    return model,metrics,manifest,encoder
def predict(model,row):
    return float(model.predict_proba(np.array([row],dtype=object))[0,1])
