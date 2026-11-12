from sqlalchemy import select
from fastapi import HTTPException
from src.models import TopicRun,TopicComparison
from src.constants.enums import RunStatus
from src.constants.comparison import RULE_VERSION
from src.utils.serialize import row
from .comparison import compare_runs
from .audit import record

def _succeeded_run(db,run_id):
 run=db.get(TopicRun,run_id)
 if not run:raise HTTPException(404,f'主题运行{run_id}不存在')
 if run.status!=RunStatus.SUCCEEDED:raise HTTPException(422,f'仅成功任务可对比：{run.name} 当前为 {run.status}')
 if not run.result or not run.result.get('replicates'):raise HTTPException(422,f'任务 {run.name} 缺少冻结分解结果')
 return run

def _serialize(db,obj):
 payload=row(obj)
 # 规则版本升级后，旧结论不再代表当前口径：显式标记 stale，前端不把旧匹配当现结论。
 payload['stale']=obj.rule_version!=RULE_VERSION
 left=db.get(TopicRun,obj.run_a_id);right=db.get(TopicRun,obj.run_b_id)
 payload['run_a']={'id':left.id,'name':left.name,'status':left.status,'k':left.config['k'],
                   'fingerprint':left.result.get('fingerprint'),'created_at':left.created_at.isoformat()} if left else None
 payload['run_b']={'id':right.id,'name':right.name,'status':right.status,'k':right.config['k'],
                   'fingerprint':right.result.get('fingerprint'),'created_at':right.created_at.isoformat()} if right else None
 return payload

def list_comparisons(db):
 return [_serialize(db,o) for o in db.scalars(select(TopicComparison).order_by(TopicComparison.id.desc()))]

def get_comparison(db,id):
 obj=db.get(TopicComparison,id)
 if not obj:raise HTTPException(404,'对比不存在')
 return _serialize(db,obj)

def create_or_recompute(db,data,user):
 if data.run_a_id==data.run_b_id:raise HTTPException(422,'请选择两个不同的任务')
 lo,hi=sorted((data.run_a_id,data.run_b_id))
 run_lo=_succeeded_run(db,lo);run_hi=_succeeded_run(db,hi)
 existing=db.scalar(select(TopicComparison).where(TopicComparison.run_a_id==lo,TopicComparison.run_b_id==hi))
 # 规则更新（rule_version 变化）或门槛调整都使旧匹配结论失效，按当前口径重算并覆盖。
 result=compare_runs(run_lo,run_hi,data.threshold)
 if existing:
  existing.name=data.name;existing.threshold=float(data.threshold);existing.rule_version=RULE_VERSION
  existing.result=result;payload=row(existing);action='comparison.recomputed'
  obj=existing
 else:
  obj=TopicComparison(run_a_id=lo,run_b_id=hi,name=data.name,threshold=float(data.threshold),
                      rule_version=RULE_VERSION,result=result,creator_id=user.id)
  db.add(obj);action='comparison.created'
 db.commit();record(db,user.email,action,{'comparison_id':obj.id,'run_a_id':lo,'run_b_id':hi,
                                          'threshold':float(data.threshold),'rule_version':RULE_VERSION,
                                          'matched':result['matched_count']})
 return _serialize(db,obj)

def refresh_stale(db,id,user):
 # 显式重算入口：规则更新后编辑可用当前版本与已保存门槛刷新结论。
 obj=db.get(TopicComparison,id)
 if not obj:raise HTTPException(404,'对比不存在')
 run_a=_succeeded_run(db,obj.run_a_id);run_b=_succeeded_run(db,obj.run_b_id)
 obj.result=compare_runs(run_a,run_b,obj.threshold);obj.rule_version=RULE_VERSION
 db.commit();record(db,user.email,'comparison.refreshed',{'comparison_id':id,'rule_version':RULE_VERSION})
 return _serialize(db,obj)
